"""M1-M4 cikis secimi: efekt basina coklu motor, 2 fan yuvasi, cakisma uyarilari, Arduino v4 kodu (simulasyonla)."""
import copy
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

from tests.helpers import temp_dm  # noqa: F401  (sys.path ayari)
from core import outputs as O
from core.engine import DEFAULT_MOTORS, DEFAULTS, EFFECTS, Engine, effect_motors
from hardware.fan import (DEFAULT_OUTPUTS, FanController, default_fans, normalize_fans, normalized)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_engine(**over):
    cfg = copy.deepcopy(DEFAULTS)
    for k in cfg:
        cfg[k]["enabled"] = False
    for k, d in over.items():
        cfg[k].update(d)
    return Engine(cfg, None)


def T(**kw):
    t = {"packetId": 1, "gas": 0.0, "brake": 0.0, "abs": 0.0, "tc": 0.0, "speed": 100.0,
         "slipRatio": [0.0] * 4, "valid": True, "gear": 3, "rpm_ratio": 0.0}
    t.update(kw)
    return t


# ---------------------------------------------------------------- efekt -> motor listesi
class EffectMotorsTests(unittest.TestCase):
    def test_defaults_are_lists_and_keep_old_assignment(self):
        self.assertEqual(effect_motors(DEFAULTS["abs"], "abs"), [0])
        self.assertEqual(effect_motors(DEFAULTS["tc"], "tc"), [1])
        for k in EFFECTS:
            self.assertIsInstance(DEFAULTS[k]["motors"], list)
            self.assertNotIn("motor", DEFAULTS[k])

    def test_legacy_motor_values_still_work(self):
        self.assertEqual(effect_motors({"motor": 0}, "abs"), [0])
        self.assertEqual(effect_motors({"motor": 1}, "abs"), [1])
        self.assertEqual(effect_motors({"motor": 2}, "abs"), [0, 1])             # eski "ikisi birden"
        self.assertEqual(effect_motors({"motor": 9}, "abs"), [0])                # bozuk: efekt varsayilani
        self.assertEqual(effect_motors({"motor": "x"}, "tc"), [1])

    def test_list_is_sanitized(self):
        self.assertEqual(effect_motors({"motors": [2, 0, 2, 1]}, "abs"), [0, 1, 2])
        self.assertEqual(effect_motors({"motors": [3]}, "abs"), [3])
        self.assertEqual(effect_motors({"motors": [7, -1, "a"]}, "abs"), [0])    # hepsi gecersiz -> varsayilan
        self.assertEqual(effect_motors({"motors": []}, "tc"), [1])
        self.assertEqual(effect_motors({"motors": "M1"}, "tc"), [1])
        self.assertEqual(effect_motors({}, "gup"), [1])
        self.assertEqual(effect_motors({"motors": ["2", 3.0]}, "abs"), [2, 3])

    def test_four_motors_have_power_settings(self):
        for i in range(1, 5):
            self.assertEqual((DEFAULT_MOTORS["min%d" % i], DEFAULT_MOTORS["max%d" % i]), (0, 100))


# ---------------------------------------------------------------- hesap: coklu motor
class ComputeTests(unittest.TestCase):
    def test_output_has_four_motors(self):
        e = make_engine()
        self.assertEqual(len(e.compute(T(), 1.0)), 4)

    def test_one_effect_drives_several_motors(self):
        e = make_engine(abs=dict(enabled=True, motors=[0, 1, 2], intensity=100, freq=12, hold=60))
        out = e.compute(T(abs=1.0), 1.0)
        for m in (0, 1, 2):
            self.assertEqual(out[m], (e.motor_pwm(m, 100), 120, 50))
        self.assertEqual(out[3], (0, 0, 50))

    def test_m3_and_m4_can_be_pedal_motors(self):
        e = make_engine(abs=dict(enabled=True, motors=[2], intensity=100), tc=dict(enabled=True, motors=[3], intensity=100))
        out = e.compute(T(abs=1.0, tc=1.0), 1.0)
        self.assertEqual((out[0][0], out[1][0]), (0, 0))
        self.assertGreater(out[2][0], 0)
        self.assertGreater(out[3][0], 0)

    def test_strongest_effect_wins_on_shared_motor(self):
        e = make_engine(abs=dict(enabled=True, motors=[2], intensity=40, freq=12),
                        tc=dict(enabled=True, motors=[2], intensity=90, freq=5))
        out = e.compute(T(abs=1.0, tc=1.0), 1.0)
        self.assertEqual(out[2], (e.motor_pwm(2, 90), 50, 50))

    def test_per_motor_power_limits_apply_to_m3_m4(self):
        e = make_engine()
        e.mcfg["max3"] = 50
        e.mcfg["min4"] = 100
        self.assertEqual(e.motor_pwm(2, 100), int(round(255 * 0.5)))
        self.assertGreaterEqual(e.motor_pwm(3, 1), 100)

    def test_legacy_motor_key_in_config_still_routes(self):
        e = make_engine(abs=dict(enabled=True, intensity=100))
        e.cfg["abs"]["motor"] = 2                                                # eski profil: ikisi birden
        out = e.compute(T(abs=1.0), 1.0)
        self.assertGreater(out[0][0], 0)
        self.assertGreater(out[1][0], 0)
        self.assertEqual((out[2][0], out[3][0]), (0, 0))


# ---------------------------------------------------------------- seri yazma: firmware surumune gore
class FakeSerial:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


class FakeLink:
    def __init__(self, fw):
        self.ser, self.ready_at, self.lock, self.fw_version = FakeSerial(), 0.0, threading.Lock(), fw
        self.failed = None

    def service_locked(self, ser, now):
        pass

    def fail(self, e):
        self.failed = e


class SendTests(unittest.TestCase):
    def lines(self, fw):
        e = Engine(copy.deepcopy(DEFAULTS), FakeLink(fw))
        out = [(10, 120, 50), (0, 0, 50), (30, 0, 50), (40, 100, 50)]
        e.send(out, time.perf_counter())
        return [l for l in e.link.ser.data.decode().split("\n") if l]

    def test_v4_sends_all_four_motors(self):
        ls = self.lines(4)
        self.assertEqual([l for l in ls if l.startswith("M")],
                         ["M1,10,120,50", "M2,0,0,50", "M3,30,0,50", "M4,40,100,50"])

    def test_old_firmware_only_m1_m2(self):
        ls = self.lines(3)
        self.assertEqual([l for l in ls if l.startswith("M")], ["M1,10,120,50", "M2,0,0,50"])
        self.assertEqual(self.lines(2), ["Q0", "M1,10,120,50", "M2,0,0,50"])

    def test_unknown_firmware_yet_is_treated_as_old(self):
        self.assertEqual([l for l in self.lines(None) if l.startswith("M")], ["M1,10,120,50", "M2,0,0,50"])

    def test_unchanged_commands_are_not_resent_immediately(self):
        e = Engine(copy.deepcopy(DEFAULTS), FakeLink(4))
        out = [(10, 120, 50), (0, 0, 50), (0, 0, 50), (0, 0, 50)]
        t = time.perf_counter()
        e.send(out, t)
        n1 = len(e.link.ser.data)
        e.send(out, t + 0.01)
        self.assertEqual(len(e.link.ser.data), n1)
        e.send(out, t + 0.06)                                                    # 50 ms canli tutma
        self.assertGreater(len(e.link.ser.data), n1)


# ---------------------------------------------------------------- cikis cakismalari
class OutputsTests(unittest.TestCase):
    def cfg(self, **over):
        c = copy.deepcopy(DEFAULTS)
        for k, d in over.items():
            c[k].update(d)
        return c

    def test_names(self):
        self.assertEqual([O.out_name(i) for i in (1, 2, 3, 4)], ["M1", "M2", "M3", "M4"])
        self.assertEqual(O.out_name(0), O.NONE_LABEL)
        self.assertEqual(O.out_name(None), O.NONE_LABEL)

    def test_pedal_outputs_only_enabled(self):
        c = self.cfg(abs=dict(motors=[0, 2]))
        used = O.pedal_outputs(c)
        self.assertEqual(sorted(used), [1, 2, 3])                                # abs: M1+M3, tc/slip: M2
        self.assertIn("abs", used[3])
        c["abs"]["enabled"] = False
        self.assertNotIn(3, O.pedal_outputs(c))
        self.assertIn(3, O.pedal_outputs(c, only_enabled=False))

    def test_pedal_vs_fan_conflict(self):
        c = self.cfg(abs=dict(motors=[2]))
        fans = [{"enabled": True, "output": 3}, {"enabled": True, "output": 4}]
        cf = O.conflicts(c, fans)
        self.assertEqual([(n, k) for n, k, _t in cf], [(3, "pedal+fan")])
        self.assertIn("Fan 1", cf[0][2])

    def test_disabled_fan_does_not_conflict(self):
        c = self.cfg(abs=dict(motors=[2]))
        self.assertEqual(O.conflicts(c, [{"enabled": False, "output": 3}]), [])
        self.assertEqual(len(O.conflicts(c, [{"enabled": False, "output": 3}], only_enabled=False)), 1)   # kapalilar da sayilirsa cakisir

    def test_two_fans_same_output_conflict(self):
        fans = [{"enabled": True, "output": 4}, {"enabled": True, "output": 4}]
        c = O.conflicts(self.cfg(), fans)
        self.assertEqual([(n, k) for n, k, _t in c], [(4, "fan+fan")])

    def test_fan_fan_conflict_reported_even_when_pedal_also_uses_output(self):
        c = self.cfg(abs=dict(motors=[2]))
        fans = [{"enabled": True, "output": 3}, {"enabled": True, "output": 3}]
        self.assertEqual(sorted(k for _n, k, _t in O.conflicts(c, fans)), ["fan+fan", "pedal+fan"])

    def test_needs_v4(self):
        self.assertEqual(O.needs_v4(self.cfg(), []), [])
        self.assertTrue(O.needs_v4(self.cfg(abs=dict(motors=[3])), []))
        self.assertTrue(O.needs_v4(self.cfg(), [{"enabled": True, "output": 3}, {"enabled": True, "output": 4}]))


# ---------------------------------------------------------------- iki fan
class FakeFanLink:
    def __init__(self, fw=4, connected=True, ready=True):
        self.connected, self.ready, self.fw_version = connected, ready, fw
        self.sent = []

    @property
    def fan_supported(self):
        return self.fw_version is not None and self.fw_version >= 3

    @property
    def multi_output(self):
        return self.fw_version is not None and self.fw_version >= 4

    def write_line(self, s):
        self.sent.append(s)
        return True


class FakeEngine:
    def __init__(self, speed=250.0, cfg=None):
        self.snap = {"t": {"speed": speed}, "live": True, "valid": True}
        self.cfg = cfg


FAST = dict(kick_ms=0, ramp_up=1000, ramp_down=1000)


def fans_cfg(f1=None, f2=None):
    a = dict(FAST, enabled=True, output=3)
    b = dict(FAST, enabled=False, output=4)
    a.update(f1 or {})
    b.update(f2 or {})
    return {"fans": [a, b]}


def run(fc, n=40, step=0.05):
    t = time.monotonic()
    for i in range(n):
        fc.tick(t + i * step)


class FanSlotTests(unittest.TestCase):
    def test_defaults_two_slots_m3_m4_both_off(self):
        d = default_fans()
        self.assertEqual([f["output"] for f in d], list(DEFAULT_OUTPUTS))
        self.assertEqual([f["enabled"] for f in d], [False, False])

    def test_output_is_clamped_and_none_allowed(self):
        self.assertEqual(normalized({"output": 9})["output"], 3)
        self.assertEqual(normalized({"output": "x"})["output"], 3)
        self.assertEqual(normalized({"output": 0})["output"], 0)
        self.assertEqual(normalized({"output": 4})["output"], 4)
        self.assertEqual(normalized({}, 4)["output"], 4)

    def test_legacy_single_fan_prefs_migrate_to_fan_1(self):
        old = {"enabled": True, "idle_pct": 30, "max_speed": 280, "no_data": "idle"}
        f = normalize_fans(old)
        self.assertEqual((f[0]["enabled"], f[0]["idle_pct"], f[0]["max_speed"], f[0]["no_data"], f[0]["output"]),
                         (True, 30, 280, "idle", 3))
        self.assertFalse(f[1]["enabled"])
        self.assertEqual(f[1]["output"], 4)

    def test_legacy_merged_with_new_defaults_keeps_user_values(self):
        # eski dosya + yeni varsayilanlar birlesince hem duz anahtarlar hem varsayilan "fans" olur: kullanici degerleri kazanir
        merged = dict(old := {"enabled": True, "idle_pct": 41}, fans=default_fans())
        f = normalize_fans(merged)
        self.assertEqual((f[0]["enabled"], f[0]["idle_pct"]), (True, 41))

    def test_new_format_roundtrip_and_garbage(self):
        raw = {"fans": [{"enabled": True, "output": 1, "idle_pct": 10}, {"enabled": True, "output": 2}]}
        f = normalize_fans(raw)
        self.assertEqual([x["output"] for x in f], [1, 2])
        self.assertEqual(f[0]["idle_pct"], 10)
        for bad in (None, {}, [], "x", {"fans": "x"}, {"fans": [1, None]}, {"fans": []}):
            f = normalize_fans(bad)
            self.assertEqual(len(f), 2)
            self.assertEqual([x["output"] for x in f], [3, 4])
        self.assertEqual(len(normalize_fans({"fans": [{}, {}, {}, {}]})), 2)

    def test_v4_commands_go_to_selected_outputs(self):
        link = FakeFanLink(fw=4)
        fc = FanController(link, FakeEngine(300.0), lambda: fans_cfg({"output": 1}, {"enabled": True, "output": 4}))
        run(fc, 60)
        self.assertIn("F1,255", link.sent)
        self.assertIn("F4,255", link.sent)
        self.assertNotIn("F,255", link.sent)

    def test_each_fan_has_own_curve_and_enable(self):
        link = FakeFanLink(fw=4)
        cfg = fans_cfg({"output": 3, "max_speed": 300}, {"enabled": True, "output": 4, "idle_pct": 0, "mid_pct": 0,
                                                       "max_speed": 600, "max_pct": 100})
        fc = FanController(link, FakeEngine(300.0), lambda: cfg)
        run(fc, 80)
        last = {}
        for l in link.sent:
            last[l.split(",")[0]] = int(l.split(",")[1])
        self.assertEqual(last["F3"], 255)                                        # Fan 1: 300 km/h = tam guc
        self.assertLess(last["F4"], 255)                                         # Fan 2: ayni hizda daha az (kendi egrisi)

    def test_disabled_second_fan_sends_zero_only_on_its_output(self):
        link = FakeFanLink(fw=4)
        fc = FanController(link, FakeEngine(250.0), lambda: fans_cfg({"enabled": True}, {"enabled": False}))
        run(fc, 30)
        self.assertIn("F4,0", link.sent)                                         # kapali Fan 2 kendi cikisini sifirda tutar
        self.assertFalse([l for l in link.sent if l.startswith("F4,") and l != "F4,0"])
        self.assertFalse([l for l in link.sent if l[1] in "12"])                 # kullanilmayan cikislara komut gitmez

    def test_no_output_selected_sends_nothing_and_says_so(self):
        link = FakeFanLink(fw=4)
        fc = FanController(link, FakeEngine(250.0), lambda: fans_cfg({"enabled": True, "output": 0}))
        run(fc, 20)
        self.assertFalse([l for l in link.sent if l.startswith("F3") or l.startswith("F1") or l.startswith("F2")])
        self.assertIn("Çıkış seçilmedi", fc.channels[0].status["text"])

    def test_changing_output_zeroes_old_output(self):
        link = FakeFanLink(fw=4)
        cfg = fans_cfg()
        fc = FanController(link, FakeEngine(250.0), lambda: cfg)
        run(fc, 20)
        self.assertTrue([l for l in link.sent if l.startswith("F3,") and l != "F3,0"])
        cfg["fans"][0]["output"] = 2                                             # fan M3'ten M2'ye tasindi
        link.sent.clear()
        run(fc, 20)
        self.assertEqual(link.sent[0], "F3,0")                                   # eski cikis hemen durdu
        self.assertTrue([l for l in link.sent if l.startswith("F2,") and l != "F2,0"])

    def test_same_output_for_two_fans_blocks_the_second(self):
        link = FakeFanLink(fw=4)
        fc = FanController(link, FakeEngine(250.0), lambda: fans_cfg({"enabled": True, "output": 3},
                                                                     {"enabled": True, "output": 3}))
        run(fc, 30)
        self.assertEqual(fc.channels[1].status["level"], "bad")
        self.assertIn("Aynı çıkış", fc.channels[1].status["text"])
        self.assertEqual(fc.channels[0].status["level"], "ok")
        self.assertTrue([l for l in link.sent if l.startswith("F3,") and l != "F3,0"])

    def test_pedal_effect_on_same_output_warns_but_fan_keeps_running(self):
        link = FakeFanLink(fw=4)
        pedal = copy.deepcopy(DEFAULTS)
        pedal["abs"]["motors"] = [2]
        fc = FanController(link, FakeEngine(250.0, cfg=pedal), lambda: fans_cfg({"enabled": True}))
        run(fc, 30)
        st = fc.channels[0].status
        self.assertEqual(st["level"], "warn")
        self.assertIn("M3", st["text"])
        self.assertTrue([l for l in link.sent if l.startswith("F3,") and l != "F3,0"])

    def test_v3_firmware_fan_1_legacy_command_and_fan_2_never_sends(self):
        link = FakeFanLink(fw=3)
        fc = FanController(link, FakeEngine(300.0), lambda: fans_cfg({"enabled": True}, {"enabled": True, "output": 4}))
        run(fc, 60)
        self.assertEqual(set(link.sent), {"F,255"} | {l for l in link.sent if l.startswith("F,")})
        self.assertIn("F,255", link.sent)
        self.assertIn("v4", fc.channels[1].status["text"])
        self.assertEqual(fc.channels[1].status["level"], "bad")

    def test_v3_disabled_second_fan_cannot_zero_the_first(self):
        link = FakeFanLink(fw=3)
        fc = FanController(link, FakeEngine(300.0), lambda: fans_cfg({"enabled": True}, {"enabled": False}))
        run(fc, 60)
        self.assertEqual(link.sent[-1], "F,255")
        self.assertEqual(fc.channels[1].status["level"], "off")                  # kapali ikinci fan v3'te uyari gostermez

    def test_old_api_still_points_to_fan_1(self):
        fc = FanController(FakeFanLink(fw=4), FakeEngine(250.0), lambda: fans_cfg())
        run(fc, 10)
        self.assertIs(fc.status, fc.channels[0].status)
        fc.status = {"text": "x", "level": "ok", "speed": None, "pct": 0, "pwm": 0}
        self.assertEqual(fc.channels[0].status["text"], "x")
        self.assertEqual(len(fc.statuses), 2)

    def test_test_mode_per_fan(self):
        link = FakeFanLink(fw=4)
        fc = FanController(link, FakeEngine(None), lambda: fans_cfg({"enabled": False}, {"enabled": False}))
        fc.start_test(60, 5, index=1)
        run(fc, 30)
        self.assertTrue([l for l in link.sent if l.startswith("F4,") and l != "F4,0"])
        self.assertFalse([l for l in link.sent if l.startswith("F3,") and l != "F3,0"])
        fc.stop_test(1)
        self.assertIsNone(fc.channels[1].test)


# ---------------------------------------------------------------- Arduino kodu (ana makinede derlenip simule edilir)
@unittest.skipUnless(shutil.which("g++"), "g++ yok: firmware simulasyonu atlandi")
class FirmwareSimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.exe = os.path.join(cls.dir, "fw_sim")
        r = subprocess.run(["g++", "-std=c++14", "-I", os.path.join(ROOT, "tests", "firmware_sim"), "-o", cls.exe,
                            os.path.join(ROOT, "tests", "firmware_sim", "harness.cpp")], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("firmware derlenemedi:\n" + r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def sim(self, script):
        r = subprocess.run([self.exe], input="\n".join(script) + "\n", capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()

    def test_version_is_4(self):
        out = self.sim(["feed V", "loop", "out"])
        self.assertEqual(out[0], "OUT:V4")

    def test_each_of_four_outputs_is_independently_addressable(self):
        for n in range(1, 5):
            out = self.sim(["time 10", "feed M%d,200,0,50" % n, "loop", "speeds"])
            speeds = [int(x) for x in out[-1].split()]
            self.assertEqual(speeds[n - 1], 200, "M%d" % n)
            self.assertEqual(sum(1 for i, s in enumerate(speeds) if i != n - 1 and s > 0), 0)

    def test_vibration_motor_times_out_after_150ms_per_motor(self):
        out = self.sim(["time 10", "feed M3,200,0,50", "feed M1,100,0,50", "loop", "speeds",
                        "time 120", "feed M1,100,0,50", "loop", "speeds",          # yalnizca M1 tazelendi
                        "time 200", "loop", "speeds"])
        a, b, c = [[int(x) for x in l.split()] for l in out if l and l[0] in "-0123456789"]
        self.assertEqual((a[0], a[2]), (100, 200))
        self.assertEqual((b[0], b[2]), (100, 200))                               # 110 ms: M3 daha dolmadi
        self.assertEqual((c[0], c[2]), (100, 0))                                 # M3 160 ms sonra durdu, M1 tazeydi

    def test_fan_commands_select_output_and_have_own_timeout(self):
        out = self.sim(["time 10", "feed F4,128", "loop", "speeds", "time 1900", "loop", "speeds", "time 2100", "loop", "speeds"])
        v = [[int(x) for x in l.split()] for l in out if l and l[0] in "-0123456789"]
        self.assertEqual(v[0][3], 128)
        self.assertEqual(v[1][3], 128)                                           # 1.9 sn: fan hala doner (2 sn zaman asimi)
        self.assertEqual(v[2][3], 0)

    def test_legacy_fan_command_goes_to_legacy_output(self):
        out = self.sim(["time 10", "feed F,100", "loop", "speeds"])
        self.assertEqual([int(x) for x in out[-1].split()], [0, 0, 100, 0])

    def test_invalid_fan_or_motor_numbers_are_ignored(self):
        out = self.sim(["time 10", "feed F9,200", "feed F0,200", "feed M5,200,0,50", "feed M0,200,0,50", "loop", "speeds"])
        self.assertEqual([int(x) for x in out[-1].split()], [0, 0, 0, 0])

    def test_fan_and_vibration_on_one_output_use_the_faster(self):
        out = self.sim(["time 10", "feed F3,120", "feed M3,200,0,50", "loop", "speeds",
                        "time 20", "feed F3,250", "feed M3,200,0,50", "loop", "speeds"])
        v = [[int(x) for x in l.split()] for l in out if l and l[0] in "-0123456789"]
        self.assertEqual(v[0][2], 200)
        self.assertEqual(v[1][2], 250)

    def test_pulsing_vibration_on_m3(self):
        # 10 Hz, %50: periyot 100 ms, ilk 50 ms acik
        out = self.sim(["time 10", "feed M3,200,100,50", "loop", "speeds",
                        "time 40", "feed M3,200,100,50", "loop", "speeds",
                        "time 70", "feed M3,200,100,50", "loop", "speeds"])
        v = [[int(x) for x in l.split()][2] for l in out if l and l[0] in "-0123456789"]
        self.assertEqual(v, [200, 200, 0])

    def test_everything_starts_stopped(self):
        out = self.sim(["loop", "speeds"])
        self.assertEqual([int(x) for x in out[-1].split()], [0, 0, 0, 0])

    def test_firmware_file_documents_v4_protocol(self):
        with open(os.path.join(ROOT, "firmware", "PedalHaptic", "PedalHaptic.ino"), encoding="utf-8") as fh:
            src = fh.read()
        for token in ("FW_VERSION 4", "NMOTORS 4", "AF_DCMotor(3, MOTOR34_1KHZ)", "AF_DCMotor(4, MOTOR34_1KHZ)"):
            self.assertIn(token, src)
        self.assertNotIn("MOTOR34_8KHZ", src.replace("// ", "").split("#include")[1])      # M3/M4'te 8/64 kHz yok


if __name__ == "__main__":
    unittest.main()
