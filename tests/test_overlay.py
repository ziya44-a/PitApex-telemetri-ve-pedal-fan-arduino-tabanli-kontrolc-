"""Overlay: saydamlik, araç gorseli ve hasar boyamasi.

Gercek Tk yoksa tests/fake_tk, ardindan overlays_page icindeki `tk` kayit tutan sahteyle degistirilir."""
import ctypes
import json
import os
import struct
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    import tkinter  # noqa: F401  (gercek Tk varsa onu kullan)
except ImportError:
    sys.path.insert(0, os.path.join(HERE, "fake_tk"))

from core.models import TelemetryFrame  # noqa: E402
from tests import rich_fake_tk as rtk  # noqa: E402
from tests.test_adapters import acc_bufs, setw  # noqa: E402
from telemetry.ac_family import ACAdapter, ACCAdapter  # noqa: E402
from telemetry.legacy_sources import Physics  # noqa: E402
from ui import car_view as cv  # noqa: E402
from ui import overlays_page as op  # noqa: E402

CAR_DIR = os.path.join(ROOT, "assets", "car")


class FakePrefs:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.sets = []

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.sets.append((k, json.loads(json.dumps(v))))
        self.data[k] = v


class FakeRoot(rtk._W):
    def __init__(self):
        super().__init__()
        self.jobs = []

    def after(self, ms, fn=None):
        self.jobs.append(fn)
        return "job%d" % len(self.jobs)

    def after_cancel(self, job):
        idx = int(str(job)[3:]) - 1
        self.jobs[idx] = None

    def run_jobs(self):
        jobs, self.jobs = self.jobs, []
        for j in jobs:
            if j:
                j()


class FakeApp:
    def __init__(self, prefs=None):
        self.root = FakeRoot()
        self.prefs = FakePrefs(prefs)


class OverlayBase(unittest.TestCase):
    def setUp(self):
        self._p1 = mock.patch.object(op, "tk", rtk)
        self._p2 = mock.patch.object(op.sys, "platform", "win32")
        self._p1.start()
        self._p2.start()
        self.app = FakeApp()
        self.mgr = op.OverlayManager(self.app)

    def tearDown(self):
        self._p2.stop()
        self._p1.stop()

    def open(self, key):
        self.mgr.open(key)
        return self.mgr.windows[key]

    @staticmethod
    def live_frame(**kw):
        f = TelemetryFrame(game="ACC", live=True, speed_kmh=120.0, tyre_temp_c=[80.0, 81.0, 82.0, 83.0],
                           tyre_press_kpa=[190.0] * 4, fuel_l=40.0)
        for k, v in kw.items():
            setattr(f, k, v)
        return f


# ---------------------------------------------------------------- saydamlik
class TransparencyTests(OverlayBase):
    def test_slider_value_is_transparency_and_old_prefs_stay_valid(self):
        # eski kayit: arka plan %70 gorunur -> arayuzde %30 saydamlik
        m = op.OverlayManager(FakeApp({"overlay_opacity": {"speed": 70}}))
        self.assertEqual(m.transparency("speed"), 30)
        self.assertEqual(m.transparency("lap"), 0)                 # kayit yok: tam opak (eski varsayilan)
        m.set_transparency("lap", 60)
        self.assertEqual(m.opacity["lap"], 40)                      # kayit anahtari eski anlamda kalir

    def test_transparency_is_clamped(self):
        self.mgr.set_transparency("speed", 100)
        self.assertEqual(self.mgr.transparency("speed"), op.MAX_TRANSPARENCY)   # pencere kaybolmaz
        self.mgr.set_transparency("speed", -20)
        self.assertEqual(self.mgr.transparency("speed"), 0)

    def test_corrupt_saved_value_does_not_crash(self):
        m = op.OverlayManager(FakeApp({"overlay_opacity": {"speed": "bozuk", "lap": 5000}}))
        self.assertEqual(m.opacity_of("speed"), 100)
        self.assertEqual(m.opacity_of("lap"), 100)

    def test_more_transparency_means_less_visible_background(self):
        w = self.open("speed")
        alphas = []
        for t in (0, 25, 50, 75, 90):
            self.mgr.set_transparency("speed", t)
            alphas.append(w.background.attrs["-alpha"])
        self.assertEqual(alphas[0], 1.0)
        self.assertEqual(alphas, sorted(alphas, reverse=True))      # saydamlik artinca alfa AZALIR
        self.assertAlmostEqual(alphas[-1], 0.1)

    def test_foreground_is_color_keyed_so_backdrop_shows_through(self):
        w = self.open("speed")
        self.assertTrue(w._background_supported)
        self.assertEqual(w.win.attrs["-transparentcolor"], op.TRANSPARENT_KEY)
        self.assertEqual(w.win.cfg["bg"], op.TRANSPARENT_KEY)
        self.assertEqual(w.label.cfg["bg"], op.TRANSPARENT_KEY)      # etiket opak degil: arka plan gorunur
        w.update(self.live_frame(), True)
        self.assertEqual(w.label.cfg["bg"], op.TRANSPARENT_KEY)      # guncellemeden sonra da
        self.assertEqual(w.background.cfg["bg"], op.BACKDROP_COLOR)
        self.assertEqual(op.TRANSPARENT_KEY, op.BACKDROP_COLOR)      # kenar halkasi olmasin

    def test_move_handle_is_available_in_transparent_mode(self):
        w = self.open("speed")
        self.assertTrue(w.handle.placed)                              # bos alanlar tiklamayi gecirir: tutamac sart

    def test_vehicle_canvas_has_no_opaque_fullscreen_fill(self):
        w = self.open("tyres")
        w.update(self.live_frame(), True)
        big = [i for i in w.canvas.kinds("rect") if i[2].get("fill") == "#101318"]
        self.assertEqual(big, [])                                     # eski tam ekran opak dolgu yok
        self.assertEqual(w.canvas.cfg["bg"], op.TRANSPARENT_KEY)
        cards = [i for i in w.canvas.kinds("rect") if i[2].get("outline") == "#3a424d"]
        self.assertTrue(cards and all(c[2]["fill"] == "" for c in cards))   # kartlarin ici saydam

    def test_vehicle_canvas_opaque_when_backdrop_unavailable(self):
        with mock.patch.object(op.sys, "platform", "linux"):
            w = self.open("tyres")
            w.update(self.live_frame(), True)
            self.assertFalse(w._background_supported)
            self.assertIsNone(w.background)
            self.assertTrue([i for i in w.canvas.kinds("rect") if i[2].get("fill") == "#101318"])

    def test_pedals_keep_old_opaque_path_at_zero_transparency(self):
        w = self.open("pedals")
        self.assertIsNone(w.background)                               # %0: eski, kanitlanmis tek pencere yolu
        self.assertEqual(w.canvas.cfg["bg"], op.OPAQUE_CANVAS)
        self.assertEqual(w.win.attrs.get("-alpha"), 1.0)
        self.assertFalse(w.handle.placed)

    def test_pedals_transparency_now_works_and_can_be_turned_off(self):
        w = self.open("pedals")
        self.mgr.set_transparency("pedals", 50)
        self.assertIsNotNone(w.background)
        self.assertAlmostEqual(w.background.attrs["-alpha"], 0.5)
        self.assertEqual(w.canvas.cfg["bg"], op.TRANSPARENT_KEY)
        self.assertEqual(w.win.attrs["-transparentcolor"], op.TRANSPARENT_KEY)
        self.assertTrue(w.handle.placed)
        self.mgr.set_transparency("pedals", 0)
        self.assertIsNone(w.background)                               # tekrar eski yola doner
        self.assertEqual(w.win.attrs["-transparentcolor"], "")
        self.assertEqual(w.canvas.cfg["bg"], op.OPAQUE_CANVAS)

    def test_pedal_telemetry_is_never_faded(self):
        w = self.open("pedals")
        self.mgr.set_transparency("pedals", 80)
        self.assertEqual(w.win.attrs.get("-alpha", 1.0), 1.0)         # on plan pencere ASLA soldurulmaz
        w.update(self.live_frame(throttle=0.5, brake=0.2), True)
        self.assertTrue(w.canvas.kinds("rect"))

    def test_saves_are_debounced_and_flushed_on_close(self):
        self.open("speed")
        for t in range(0, 60, 5):
            self.mgr.set_transparency("speed", t)
        self.assertEqual(self.app.prefs.sets, [])                     # surukleme sirasinda diske yazilmaz
        self.app.root.run_jobs()
        self.assertEqual(len(self.app.prefs.sets), 1)
        self.assertEqual(self.app.prefs.sets[0][1]["speed"], 100 - 55)
        self.mgr.set_transparency("speed", 20)
        self.mgr.close_all()                                          # kapanista bekleyen kayit yazilir
        self.assertEqual(self.app.prefs.sets[-1][1]["speed"], 80)

    def test_backdrop_destroyed_with_window(self):
        w = self.open("speed")
        bg = w.background
        self.mgr.close("speed")
        self.assertTrue(bg.destroyed and w.win.destroyed)


# ---------------------------------------------------------------- araç görseli ve hasar
class VehicleTests(OverlayBase):
    def images(self, w):
        return [os.path.basename(i[2]["image"].file) for i in w.canvas.kinds("image")]

    def test_car_image_is_drawn_and_unknown_damage_is_not_painted(self):
        w = self.open("tyres")
        w.update(self.live_frame(), True)                             # hasar verisi YOK
        names = self.images(w)
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith("_base.png"))
        self.assertFalse([n for n in names if not n.endswith("_base.png")])  # bilinmeyen bolge saglam gosterilmez
        self.assertIn("Oyun bölgesel hasar verisi vermiyor", [i[2]["text"] for i in w.canvas.kinds("text")])

    def test_damage_paints_gradient_from_green_to_red(self):
        w = self.open("tyres")
        dmg = {"front": cv.BODY_DAMAGE_FULL, "rear": 0.0, "left": cv.BODY_DAMAGE_FULL / 2, "right": 3.2, "center": 0.0}
        dmg["front"], dmg["right"] = 3.2, cv.BODY_DAMAGE_FULL * 5   # ham degerler: 3.2 ve tavanin ustu
        w.update(self.live_frame(body_damage=dmg), True)
        names = self.images(w)
        tint = {n.split("_", 2)[2][:-4] for n in names if not n.endswith("_base.png")}
        self.assertEqual(tint, {"front_s%d" % cv.damage_level(3.2), "rear_s0", "left_s4", "right_s8", "center_s0"})
        self.assertTrue(any("Ön 3.2" in i[2]["text"] for i in w.canvas.kinds("text")))   # ham deger, yuzde degil

    def test_wheel_outline_colors_follow_suspension_damage(self):
        w = self.open("tyres")
        full = cv.SUSP_DAMAGE_FULL
        w.update(self.live_frame(body_damage=dict.fromkeys(cv.ZONES, 0.0), wheel_damage=[0.0, full, 0.0, full / 2]), True)
        outlines = [i[2]["outline"] for i in w.canvas.kinds("rect") if i[2].get("width") == 3]
        self.assertEqual(outlines, [cv.GREEN, cv.RED, cv.GREEN, cv.level_color(4)])
        texts = [i[2]["text"] for i in w.canvas.kinds("text")]
        self.assertIn("SÜSP.  KIRIK", texts)
        self.assertIn("SÜSP.  HASARLI", texts)
        self.assertIn("SÜSP.  SAĞLAM", texts)

    def test_broken_front_wheel_shows_pull_warning_and_psi(self):
        w = self.open("tyres")
        full = cv.SUSP_DAMAGE_FULL
        w.update(self.live_frame(body_damage=dict.fromkeys(cv.ZONES, 0.0), wheel_damage=[0.0, full, 0.0, 0.0]), True)
        texts = [i[2]["text"] for i in w.canvas.kinds("text")]
        self.assertIn("⚠ KIRIK: SAĞA ÇEKER", texts)
        self.assertIn("⚠ SAĞ ÖN KIRIK · SAĞA ÇEKER", texts)
        self.assertIn("27.6 psi", texts)                              # 190 kPa -> psi
        self.assertFalse([t for t in texts if "kPa" in t])

    def test_no_pull_warning_for_healthy_wheels(self):
        w = self.open("tyres")
        w.update(self.live_frame(body_damage=dict.fromkeys(cv.ZONES, 0.0), wheel_damage=[0.0] * 4), True)
        self.assertFalse([i for i in w.canvas.kinds("text") if "ÇEKER" in i[2]["text"] or "HASARLI" in i[2]["text"] and "⚠" in i[2]["text"]])

    def test_no_telemetry_draws_neutral_car(self):
        w = self.open("tyres")
        w.update(None, True)
        self.assertEqual(len(self.images(w)), 1)
        self.assertIn("Veri yok", [i[2]["text"] for i in w.canvas.kinds("text")])

    def test_unreadable_assets_fall_back_to_polygon_car(self):
        w = self.open("tyres")
        self.mgr._car_assets_tried = True
        self.mgr._car_assets = None
        w.update(self.live_frame(), True)
        self.assertEqual(self.images(w), [])
        self.assertGreater(len(w.canvas.kinds("poly")), 5)            # arac yine cizilir

    def test_photo_open_failure_falls_back(self):
        with mock.patch.object(cv, "resource_path", lambda *p: os.path.join("/yok", *p)):
            m = op.OverlayManager(FakeApp())
            self.assertIsNone(m.car_assets())

    def test_unchanged_state_is_not_redrawn(self):
        w = self.open("tyres")
        f = self.live_frame(body_damage=dict.fromkeys(cv.ZONES, 0.0))
        w.update(f, True)
        n = w.canvas.delete_calls
        w.update(self.live_frame(body_damage=dict.fromkeys(cv.ZONES, 0.0)), True)
        self.assertEqual(w.canvas.delete_calls, n)                    # ayni veri: yeniden cizim yok
        w.update(self.live_frame(body_damage=dict(dict.fromkeys(cv.ZONES, 0.0), front=1.0)), True)
        self.assertEqual(w.canvas.delete_calls, n + 1)

    def test_larger_window_uses_larger_prescaled_image(self):
        w = self.open("tyres")
        w.update(self.live_frame(), True)
        small = w.canvas.kinds("image")[0][2]["image"].file
        w.canvas.w, w.canvas.h = 1520, 1300
        w.update(self.live_frame(speed_kmh=121.0, fuel_l=39.0), True)
        big = w.canvas.kinds("image")[0][2]["image"].file
        self.assertNotEqual(small, big)

    def test_parts_overlay_still_works_and_is_transparent(self):
        w = self.open("parts")
        w.update(self.live_frame(), True)
        self.assertEqual(w.canvas.cfg["bg"], op.TRANSPARENT_KEY)
        self.assertIn("Veri yok", [i[2]["text"] for i in w.canvas.kinds("text")])


class CarViewTests(unittest.TestCase):
    def test_damage_level_thresholds_and_scale(self):
        self.assertIsNone(cv.damage_level(None))
        self.assertIsNone(cv.damage_level(float("nan")))
        self.assertIsNone(cv.damage_level("x"))
        self.assertEqual(cv.damage_level(0), 0)
        self.assertEqual(cv.damage_level(cv.DAMAGE_EPS), 0)
        self.assertEqual(cv.damage_level(cv.DAMAGE_EPS + 0.01), 1)            # ilk hasar en az 1. kademe
        self.assertEqual(cv.damage_level(cv.BODY_DAMAGE_FULL / 2), (cv.STEPS - 1) // 2)
        self.assertEqual(cv.damage_level(cv.BODY_DAMAGE_FULL), cv.STEPS - 1)  # tamamen kirik = kirmizi
        self.assertEqual(cv.damage_level(cv.BODY_DAMAGE_FULL * 9), cv.STEPS - 1)
        levels = [cv.damage_level(v) for v in range(0, int(cv.BODY_DAMAGE_FULL) + 1, 5)]
        self.assertEqual(levels, sorted(levels))                              # hasar arttikca kademe azalmaz

    def test_gradient_endpoints_and_midpoint(self):
        self.assertEqual(cv.level_color(0), cv.GREEN)
        self.assertEqual(cv.level_color(cv.STEPS - 1), cv.RED)
        self.assertEqual(cv.level_color(None), cv.NEUTRAL)
        r, g, b = cv.gradient_rgb(0.5)
        self.assertTrue(r > 150 and g > 150 and b < 100)                      # orta: sari/turuncu, camur kahve degil

    def test_level_files_exist_for_every_zone_and_size(self):
        assets = cv.CarAssets(lambda p: p)
        for h, _w in assets.meta["sizes"]:
            for z in cv.ZONES:
                for k in range(cv.STEPS):
                    self.assertTrue(os.path.exists(os.path.join(assets.dir, "car_%d_%s_s%d.png" % (h, z, k))))

    def test_missing_zone_is_unknown_not_green(self):
        st = cv.zone_levels({"front": cv.BODY_DAMAGE_FULL})
        self.assertEqual(st["front"], cv.STEPS - 1)
        self.assertIsNone(st["rear"])
        self.assertEqual(cv.zone_levels("bozuk"), dict.fromkeys(cv.ZONES))
        self.assertEqual(cv.wheel_levels([0, 0, 0]), [None] * 4)

    def test_wheel_warning_logic(self):
        top = cv.STEPS - 1
        self.assertIsNone(cv.wheel_warning("fl", None))
        self.assertIsNone(cv.wheel_warning("fl", cv.PULL_WARN_LEVEL - 1))
        self.assertEqual(cv.wheel_warning("fl", cv.PULL_WARN_LEVEL), "SOLA ÇEKER")
        self.assertEqual(cv.wheel_warning("fr", top), "KIRIK: SAĞA ÇEKER")
        self.assertEqual(cv.wheel_warning("rr", cv.PULL_WARN_LEVEL), "ARKA KARARSIZ")
        self.assertIsNone(cv.pull_banner([0, 0, 0, 0]))
        self.assertEqual(cv.pull_banner([top, 0, 0, 0]), "SOL ÖN KIRIK · SOLA ÇEKER")
        self.assertEqual(cv.pull_banner([top, top, 0, None]), "2 TEKERLEK HASARLI")

    def test_kpa_to_psi(self):
        self.assertAlmostEqual(cv.kpa_to_psi(27.5 * 6.894757), 27.5, places=4)
        self.assertIsNone(cv.kpa_to_psi(None))
        self.assertIsNone(cv.kpa_to_psi("x"))

    def test_summary_text(self):
        self.assertIsNone(cv.summary_text(None))
        self.assertEqual(cv.summary_text({"front": 0, "rear": 3.2, "left": 0, "right": 0, "center": 0}),
                         "Ön 0.0 · Arka 3.2 · Sol 0.0 · Sağ 0.0 · Orta 0.0")


def png_info(path):
    with open(path, "rb") as f:
        head = f.read(26)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    w, h = struct.unpack(">II", head[16:24])
    return w, h, head[25]          # genislik, yukseklik, renk tipi (6 = RGBA)


class AssetIntegrityTests(unittest.TestCase):
    def test_meta_and_files_are_consistent(self):
        meta = json.load(open(os.path.join(CAR_DIR, "car_meta.json"), encoding="utf-8"))
        self.assertEqual(sorted(meta["zones"]), sorted(cv.ZONES))
        self.assertEqual(meta["steps"], cv.STEPS)
        for h, w in meta["sizes"]:
            names = ["base"] + ["%s_%s" % (z, c) for z in cv.ZONES for c in ["s%d" % k for k in range(cv.STEPS)]]
            for n in names:
                path = os.path.join(CAR_DIR, "car_%d_%s.png" % (h, n))
                self.assertTrue(os.path.isfile(path), path)
                pw, ph, ctype = png_info(path)
                self.assertEqual((pw, ph), (w, h), path)
                self.assertEqual(ctype, 6, "RGBA olmali: " + path)
        for k in cv.WHEEL_KEYS:
            a, b, c, d = meta["wheels"][k]
            self.assertTrue(0 <= a < c <= 1 and 0 <= b < d <= 1)

    def test_background_is_transparent_in_real_asset(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow yok")
        im = Image.open(os.path.join(CAR_DIR, "car_500_base.png")).convert("RGBA")
        self.assertEqual(im.getpixel((2, 2))[3], 0)                   # kose: siyah zemin saydam
        self.assertEqual(im.getpixel((im.width // 2, im.height // 2))[3], 255)   # arac govdesi opak


# ---------------------------------------------------------------- telemetri: hasar alanlari
class DamageTelemetryTests(unittest.TestCase):
    def test_acc_reads_body_and_suspension_damage(self):
        arr = (ctypes.c_float * 5)(3.2, 0.0, 0.0, 0.5, 0.0)
        susp = (ctypes.c_float * 4)(0.0, 1.5, 0.0, 0.0)
        f = ACCAdapter().parse(*acc_bufs(p__carDamage=arr, p__suspensionDamage=susp))
        self.assertEqual(f.body_damage, {"front": 3.2000000476837158, "rear": 0.0, "left": 0.0,
                                         "right": 0.5, "center": 0.0})
        self.assertEqual(f.wheel_damage, [0.0, 1.5, 0.0, 0.0])

    def test_acc_without_damage_is_all_zero_but_present(self):
        f = ACCAdapter().parse(*acc_bufs())
        self.assertEqual(set(f.body_damage), set(cv.ZONES))           # sifir = hasarsiz (gercek okuma)
        self.assertTrue(all(v == 0.0 for v in f.body_damage.values()))

    def test_invalid_damage_values_are_dropped_entirely(self):
        arr = (ctypes.c_float * 5)(1.0, float("nan"), 0.0, 0.0, 0.0)
        f = ACCAdapter().parse(*acc_bufs(p__carDamage=arr))
        self.assertIsNone(f.body_damage)                              # yarisi gosterilmez
        arr = (ctypes.c_float * 5)(1.0, -5.0, 0.0, 0.0, 0.0)
        self.assertIsNone(ACCAdapter().parse(*acc_bufs(p__carDamage=arr)).body_damage)

    def test_misaligned_physics_tail_hides_wheel_damage(self):
        f = ACCAdapter().parse(*acc_bufs(p__isEngineRunning=123456))
        self.assertIsNone(f.wheel_damage)

    def test_ac_reads_body_damage_only(self):
        p = Physics()
        p.packetId, p.speedKmh, p.rpms, p.gear, p.fuel = 5, 100.0, 5000, 2, 30.0
        p.carDamage[0], p.carDamage[2] = 4.0, 0.0
        for i in range(4):
            p.tyreCoreTemperature[i], p.wheelsPressure[i] = 70.0, 26.0
        from telemetry.ac_family import GraphicsAC, StaticAC
        g = GraphicsAC()
        g.status = 2
        s = StaticAC()
        setw(s.carModel, "ks_x")
        setw(s.track, "ks_y")
        s.sectorCount = 3
        f = ACAdapter().parse(bytes(p)[:Physics.localVelocity.offset + 12], bytes(g), bytes(s))
        self.assertEqual(f.body_damage["front"], 4.0)
        self.assertIsNone(f.wheel_damage)                              # AC'de suspansiyon hasari okunmuyor


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- lastik sicakligi: kuru/islak profil
from ui import tyre_temp as tt  # noqa: E402
from tests.test_adapters import lmu_mems  # noqa: E402
from telemetry.lmu import LMUAdapter as _LMU  # noqa: E402


class TyreTempLogicTests(unittest.TestCase):
    def setUp(self):
        self.dry, self.wet = tt.DEFAULT_RANGES["dry"], tt.DEFAULT_RANGES["wet"]

    def test_color_ramp_endpoints_and_ideal_window(self):
        r = self.dry
        self.assertEqual(tt.temp_color(r["cold"] - 20, r), "#%02x%02x%02x" % tt.COLD_RGB)
        self.assertEqual(tt.temp_color(r["opt_min"], r), "#%02x%02x%02x" % tt.OPT_RGB)
        self.assertEqual(tt.temp_color((r["opt_min"] + r["opt_max"]) / 2, r), "#%02x%02x%02x" % tt.OPT_RGB)
        self.assertEqual(tt.temp_color(r["opt_max"], r), "#%02x%02x%02x" % tt.OPT_RGB)
        self.assertEqual(tt.temp_color(r["hot"] + 30, r), "#%02x%02x%02x" % tt.HOT_RGB)
        self.assertEqual(tt.temp_color(None, r), tt.NEUTRAL)
        self.assertEqual(tt.temp_color(float("nan"), r), tt.NEUTRAL)
        self.assertEqual(tt.temp_color("x", r), tt.NEUTRAL)

    def test_same_temperature_has_different_color_for_dry_and_wet(self):
        t = 65.0                                                   # islak icin ideal, kuru icin soguk
        self.assertEqual(tt.temp_status(t, self.wet), "İDEAL")
        self.assertEqual(tt.temp_status(t, self.dry), "SOĞUK")
        self.assertNotEqual(tt.temp_color(t, self.wet), tt.temp_color(t, self.dry))

    def test_status_words(self):
        r = self.dry
        self.assertEqual(tt.temp_status(r["opt_min"] - 1, r), "SOĞUK")
        self.assertEqual(tt.temp_status(r["opt_max"] + 1, r), "SICAK")
        self.assertIsNone(tt.temp_status(None, r))

    def test_auto_profile_follows_game_and_never_guesses(self):
        cfg = tt.normalize_config(None)
        self.assertEqual(tt.resolve_profile(cfg, True), ("wet", True, True))
        self.assertEqual(tt.resolve_profile(cfg, False), ("dry", True, True))
        self.assertEqual(tt.resolve_profile(cfg, None), ("dry", True, False))   # bilgi yok -> yedek profil, "bilinmiyor" isaretli
        cfg["fallback"] = "wet"
        self.assertEqual(tt.resolve_profile(cfg, None), ("wet", True, False))
        cfg["mode"] = "dry"
        self.assertEqual(tt.resolve_profile(cfg, True)[0], "dry")               # elle mod oyunu yok sayar
        self.assertIn("oyun tipi vermiyor", tt.profile_label(tt.normalize_config(None), None))
        self.assertIn("(oto)", tt.profile_label(tt.normalize_config(None), True))

    def test_validate_rejects_bad_order_and_values(self):
        ok = {"cold": 60, "opt_min": 80, "opt_max": 95, "hot": 110}
        self.assertEqual(tt.validate(ok)["hot"], 110.0)
        for bad in ({**ok, "opt_min": 96}, {**ok, "cold": 80}, {**ok, "hot": 95}, {**ok, "hot": 999},
                    {**ok, "cold": "abc"}, {"cold": 1}, None):
            with self.assertRaises(ValueError):
                tt.validate(bad)

    def test_normalize_config_repairs_corrupt_saved_values(self):
        cfg = tt.normalize_config({"mode": "xx", "fallback": "yy", "ranges": {"dry": {"cold": 90, "opt_min": 1, "opt_max": 2, "hot": 3},
                                                                              "wet": {"cold": 30, "opt_min": 50, "opt_max": 70, "hot": 85}}})
        self.assertEqual((cfg["mode"], cfg["fallback"]), ("auto", "dry"))
        self.assertEqual(cfg["ranges"]["dry"], tt.DEFAULT_RANGES["dry"])       # bozuk -> varsayilan
        self.assertEqual(cfg["ranges"]["wet"]["opt_max"], 70.0)                 # saglam olan korunur


class TyreWetDetectionTests(unittest.TestCase):
    def test_compound_name_parsing(self):
        from core.models import compound_is_wet
        self.assertTrue(compound_is_wet("wet_compound"))
        self.assertFalse(compound_is_wet("dry_compound"))
        self.assertTrue(compound_is_wet("Wet"))
        self.assertTrue(compound_is_wet("Intermediate"))
        self.assertFalse(compound_is_wet("Medium"))
        self.assertIsNone(compound_is_wet(""))
        self.assertIsNone(compound_is_wet("   "))

    def test_acc_reads_compound_name_then_rain_flag(self):
        from telemetry.ac_family import ACCAdapter, GraphicsACC
        # bilesik adi
        for name, expect in (("wet_compound", True), ("dry_compound", False)):
            p, g, s = acc_bufs()
            gg = GraphicsACC.from_buffer_copy(g)
            setw(gg.tyreCompound, name)
            f = ACCAdapter().parse(p, bytes(gg), s)
            self.assertIs(f.tyre_wet, expect, name)
        # ad bos, yagmur lastigi bayragi var
        p, g, s = acc_bufs()
        gg = GraphicsACC.from_buffer_copy(g)
        gg.rainTyres = 1
        self.assertIs(ACCAdapter().parse(p, bytes(gg), s).tyre_wet, True)
        gg.rainTyres = 0
        self.assertIs(ACCAdapter().parse(p, bytes(gg), s).tyre_wet, False)
        gg.rainTyres = 7                                                   # gecersiz bayrak -> bilinmiyor
        self.assertIsNone(ACCAdapter().parse(p, bytes(gg), s).tyre_wet)

    def test_lmu_reads_front_compound_name(self):
        def edit(name):
            def _e(v):
                v.mFrontTireCompoundName = name
            return _e
        self.assertIs(_LMU(*lmu_mems(vehicle_edit=edit(b"Wet"))).read().tyre_wet, True)
        self.assertIs(_LMU(*lmu_mems(vehicle_edit=edit(b"Medium"))).read().tyre_wet, False)
        self.assertIsNone(_LMU(*lmu_mems()).read().tyre_wet)


class TyreTempOverlayTests(OverlayBase):
    def texts(self, w):
        return [(i[2]["text"], i[2].get("fill")) for i in w.canvas.kinds("text")]

    def temp_fill(self, w, label):
        return [fill for t, fill in self.texts(w) if t == label]

    def test_temperature_text_changes_color_with_dry_vs_wet(self):
        w = self.open("tyres")
        w.update(self.live_frame(tyre_temp_c=[65.0] * 4, tyre_wet=False), True)
        dry_col = self.temp_fill(w, "65°C")[0]
        w.update(self.live_frame(tyre_temp_c=[65.0] * 4, tyre_wet=True), True)
        wet_col = self.temp_fill(w, "65°C")[0]
        self.assertNotEqual(dry_col, wet_col)
        self.assertEqual(wet_col, tt.temp_color(65.0, tt.DEFAULT_RANGES["wet"]))
        self.assertEqual(dry_col, tt.temp_color(65.0, tt.DEFAULT_RANGES["dry"]))

    def test_label_shows_profile_and_unknown_state(self):
        w = self.open("tyres")
        w.update(self.live_frame(tyre_wet=True), True)
        self.assertTrue(any(t.startswith("LASTİK: ISLAK (oto)") for t, _ in self.texts(w)))
        w.update(self.live_frame(tyre_wet=None), True)
        self.assertTrue(any("KURU (oyun tipi vermiyor)" in t for t, _ in self.texts(w)))

    def hot_strips(self, w):
        hot = "#%02x%02x%02x" % tt.HOT_RGB
        return len([i for i in w.canvas.kinds("rect") if i[2].get("fill") == hot and i[2].get("outline") == ""])

    def test_wheel_strip_is_drawn_with_temperature_color(self):
        w = self.open("tyres")
        w.update(self.live_frame(tyre_temp_c=None, tyre_wet=False), True)
        base = self.hot_strips(w)                                   # gostergedeki kirmizi kutu vb.
        w.update(self.live_frame(tyre_temp_c=[130.0] * 4, tyre_wet=False), True)
        self.assertEqual(self.hot_strips(w) - base, 8)              # 4 tekerlek seridi + 4 kart ust cubugu

    def test_config_change_redraws_and_persists(self):
        w = self.open("tyres")
        w.update(self.live_frame(tyre_temp_c=[80.0] * 4, tyre_wet=False), True)
        before = self.temp_fill(w, "80°C")[0]
        cfg = tt.normalize_config(None)
        cfg["ranges"]["dry"] = {"cold": 20, "opt_min": 30, "opt_max": 40, "hot": 60}    # 80 artik cok sicak
        self.mgr.set_tyre_cfg(cfg)
        self.assertEqual(self.app.prefs.sets[-1][0], "tyre_temp")
        w.update(self.live_frame(tyre_temp_c=[80.0] * 4, tyre_wet=False), True)
        after = self.temp_fill(w, "80°C")[0]
        self.assertNotEqual(before, after)
        self.assertEqual(after, "#%02x%02x%02x" % tt.HOT_RGB)
        m2 = op.OverlayManager(FakeApp({"tyre_temp": self.app.prefs.sets[-1][1]}))      # yeniden acilista okunur
        self.assertEqual(m2.tyre_cfg["ranges"]["dry"]["hot"], 60.0)

    def test_invalid_config_is_rejected_not_saved(self):
        cfg = tt.normalize_config(None)
        cfg["ranges"]["wet"] = {"cold": 80, "opt_min": 50, "opt_max": 70, "hot": 85}
        n = len(self.app.prefs.sets)
        with self.assertRaises(ValueError):
            self.mgr.set_tyre_cfg(cfg)
        self.assertEqual(len(self.app.prefs.sets), n)
        self.assertEqual(self.mgr.tyre_cfg["ranges"]["wet"], tt.DEFAULT_RANGES["wet"])

    def test_no_temperature_stays_neutral(self):
        w = self.open("tyres")
        w.update(self.live_frame(tyre_temp_c=None), True)
        self.assertEqual(len([t for t, _ in self.texts(w) if t == "—"]) >= 4, True)
        self.assertFalse([t for t, _ in self.texts(w) if t in ("SOĞUK", "İDEAL", "SICAK")])   # veri yok -> durum yazilmaz


class TyreTempSettingsPanelLogicTests(OverlayBase):
    """Ayar paneli mantigi (Tk widget'i olmadan): alanlari okuma, dogrulama, kaydetme, varsayilana donme."""

    class V:
        def __init__(self, v): self.v = v
        def get(self): return self.v
        def set(self, v): self.v = v

    class L:
        def __init__(self): self.text = ""
        def config(self, **kw): self.text = kw.get("text", self.text)

    def page(self):
        P = op.OverlaysPage
        obj = type("FakePage", (), {})()
        obj.manager = self.mgr
        cfg = self.mgr.tyre_cfg
        obj.tyre_mode_var = self.V(tt.MODE_LABELS[cfg["mode"]])
        obj.tyre_fallback_var = self.V("Kuru")
        obj.tyre_vars = {(n, k): self.V("%g" % cfg["ranges"][n][k]) for n in ("dry", "wet") for k in tt.KEYS}
        obj.tyre_msg = self.L()
        for name in ("_tyre_cfg_from_ui", "apply_tyre_temp", "reset_tyre_temp"):
            setattr(obj, name, getattr(P, name).__get__(obj))
        return obj

    def test_apply_valid_values_with_decimal_comma(self):
        pg = self.page()
        pg.tyre_mode_var.set("Hep ıslak")
        pg.tyre_vars[("wet", "opt_max")].set("72,5")
        self.assertTrue(pg.apply_tyre_temp())
        self.assertEqual(self.mgr.tyre_cfg["mode"], "wet")
        self.assertEqual(self.mgr.tyre_cfg["ranges"]["wet"]["opt_max"], 72.5)
        self.assertEqual(pg.tyre_msg.text, "Kaydedildi.")

    def test_bad_input_is_reported_and_not_saved(self):
        pg = self.page()
        pg.tyre_vars[("dry", "opt_min")].set("200")                  # sira bozuk
        self.assertFalse(pg.apply_tyre_temp())
        self.assertTrue(pg.tyre_msg.text.startswith("Kaydedilmedi — Kuru:"))
        pg.tyre_vars[("dry", "opt_min")].set("80")
        pg.tyre_vars[("wet", "hot")].set("abc")
        self.assertFalse(pg.apply_tyre_temp())
        self.assertTrue(pg.tyre_msg.text.startswith("Kaydedilmedi — Islak:"))
        self.assertEqual(self.mgr.tyre_cfg["ranges"], tt.normalize_config(None)["ranges"])

    def test_reset_restores_defaults(self):
        pg = self.page()
        pg.tyre_mode_var.set("Hep kuru")
        pg.tyre_vars[("dry", "hot")].set("150")
        pg.apply_tyre_temp()
        pg.reset_tyre_temp()
        self.assertEqual(self.mgr.tyre_cfg, tt.normalize_config(None))
        self.assertEqual(pg.tyre_vars[("dry", "hot")].get(), "%g" % tt.DEFAULT_RANGES["dry"]["hot"])


class TransparencyKeepsImageTests(OverlayBase):
    """Saydamlik YALNIZCA arka plan penceresini etkiler: arac gorseli, renkler ve yazilar on planda, soldurulmaz."""

    def names(self, w):
        return [os.path.basename(i[2]["image"].file) for i in w.canvas.kinds("image")]

    def test_car_and_tints_are_identical_at_any_transparency(self):
        w = self.open("tyres")
        frame = self.live_frame(body_damage=dict(dict.fromkeys(cv.ZONES, 0.0), front=cv.BODY_DAMAGE_FULL / 2))
        w.update(frame, True)
        opaque = (self.names(w), w.win.attrs.get("-alpha", 1.0))
        for t in (30, 60, op.MAX_TRANSPARENCY):
            self.mgr.set_transparency("tyres", t)
            w.update(self.live_frame(body_damage=dict(dict.fromkeys(cv.ZONES, 0.0), front=cv.BODY_DAMAGE_FULL / 2)), True)
            self.assertEqual(self.names(w), opaque[0])                     # ayni gorsel ve ayni renk katmanlari
            self.assertEqual(w.win.attrs.get("-alpha", 1.0), 1.0)          # on plan ASLA soldurulmaz
            self.assertLess(w.background.attrs["-alpha"], 1.0)             # sadece arka plan soluklasir

    def test_body_and_wheels_leave_no_color_key_pixels(self):
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            self.skipTest("Pillow/numpy yok (yalniz gelistirme testi)")
        key = np.array((21, 21, 21))
        self.assertEqual(op.TRANSPARENT_KEY, "#151515")                    # test anahtar renge gore yazildi
        zones = [None] + list(cv.ZONES)
        for h in (280, 500, 800):
            base = Image.open(os.path.join(CAR_DIR, "car_%d_base.png" % h)).convert("RGBA")
            ba = np.array(base)[..., 3]
            for step in (0, 4, 8):
                im = Image.new("RGBA", base.size, tuple(key) + (255,))
                im.alpha_composite(base)
                for z in zones[1:]:
                    im.alpha_composite(Image.open(os.path.join(CAR_DIR, "car_%d_%s_s%d.png" % (h, z, step))).convert("RGBA"))
                holes = np.all(np.array(im.convert("RGB")) == key, axis=2) & (ba >= 50)
                self.assertEqual(int(holes.sum()), 0, "arac govdesinde saydam delik (h=%d, kademe=%d)" % (h, step))

    def test_gradient_formula_matches_asset_builder(self):
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import build_car_assets as b
        except ImportError:
            self.skipTest("Pillow/numpy/scipy yok (yalniz gelistirme testi)")
        for i in range(cv.STEPS):
            self.assertEqual("#%02x%02x%02x" % b.step_color(i), cv.level_color(i))
        self.assertEqual(b.STEPS, cv.STEPS)
