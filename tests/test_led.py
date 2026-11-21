"""MAX7219 8x8 LED matris: font, yon donusumu, ayarlar, vites mantigi, kontrolcu ve Arduino kodu (simulasyonla)."""
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

from tests.helpers import temp_dm  # noqa: F401  (sys.path ayari)
from core import led_matrix as M
from hardware.arduino import ArduinoLink, LedLink
from hardware.led import LedController

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def art(rows):
    return ["".join("#" if (r >> (7 - c)) & 1 else "." for c in range(8)) for r in rows]


# ---------------------------------------------------------------- font ve donusum
class FontTests(unittest.TestCase):
    def test_all_gear_characters_have_glyphs(self):
        for ch in "RN0123456789-+":
            g = M.glyph(ch)
            self.assertEqual(len(g), 8)
            self.assertTrue(any(g), ch)
            self.assertTrue(all(0 <= v <= 255 for v in g))

    def test_glyphs_are_distinct(self):
        chars = "RN0123456789-+"
        self.assertEqual(len({M.glyph(c) for c in chars}), len(chars))

    def test_unknown_and_space_are_blank(self):
        self.assertEqual(M.glyph("?"), M.BLANK)
        self.assertEqual(M.glyph(" "), M.BLANK)

    def test_glyph_is_vertically_centered_in_rows_1_to_7(self):
        for ch in "RN0123456789":
            self.assertEqual(M.glyph(ch)[0], 0, ch)
            self.assertTrue(any(M.glyph(ch)[1:]), ch)

    def test_digit_looks_like_digit(self):
        self.assertEqual(art(M.glyph("1"))[1:3], ["...##...", "..###..."])
        self.assertEqual(art(M.glyph("-"))[4], ".######.")

    def test_hex_roundtrip_and_validation(self):
        rows = M.glyph("R")
        self.assertEqual(M.parse_hex(M.to_hex(rows)), rows)
        self.assertEqual(M.to_hex(M.BLANK), "0" * 16)
        for bad in (None, "", "ZZ" * 8, "00" * 7, "00" * 9, 5):
            self.assertIsNone(M.parse_hex(bad))


class TransformTests(unittest.TestCase):
    def test_identity(self):
        for ch in "R3":
            self.assertEqual(M.transform(M.glyph(ch)), M.glyph(ch))

    def test_four_rotations_are_identity(self):
        g = M.glyph("R")
        x = g
        for _ in range(4):
            x = M.transform(x, 90)
        self.assertEqual(x, g)
        self.assertEqual(M.transform(M.transform(g, 180), 180), g)
        self.assertEqual(M.transform(M.transform(g, 90), 270), g)

    def test_rotation_90_clockwise_known_pixel(self):
        rows = (0x80,) + (0,) * 7                      # sol ust piksel
        self.assertEqual(art(M.transform(rows, 90))[0], ".......#")      # saat yonunde 90: sag ust
        self.assertEqual(art(M.transform(rows, 180))[7], ".......#")     # sag alt
        self.assertEqual(art(M.transform(rows, 270))[7], "#.......")     # sol alt

    def test_flips(self):
        rows = (0x80,) + (0,) * 7
        self.assertEqual(art(M.transform(rows, 0, flip_h=True))[0], ".......#")
        self.assertEqual(art(M.transform(rows, 0, flip_v=True))[7], "#.......")
        g = M.glyph("R")
        self.assertEqual(M.transform(M.transform(g, 0, True, True), 180), g)       # iki ayna = 180 derece

    def test_pixel_count_preserved(self):
        g = M.glyph("8")
        for r in (0, 90, 180, 270):
            for fh in (False, True):
                t = M.transform(g, r, fh, False)
                self.assertEqual(sum(bin(v).count("1") for v in t), sum(bin(v).count("1") for v in g))

    def test_all_on_stays_all_on(self):
        self.assertEqual(M.transform(M.all_on(), 90, True, True), M.all_on())


# ---------------------------------------------------------------- ayarlar
class ConfigTests(unittest.TestCase):
    def test_defaults_stable(self):
        d = M.normalized({})
        self.assertEqual(M.normalized(d), d)
        self.assertFalse(d["enabled"])
        self.assertEqual(d["feature"], "gear")

    def test_garbage_is_repaired(self):
        c = M.normalized({"brightness": 99, "rotation": 45, "enabled": 1, "port": 5, "feature": "x",
                          "gear": {"neutral": "Z", "no_data": "q"}, "flip_h": "evet"})
        self.assertEqual(c["brightness"], 15)
        self.assertEqual(c["rotation"], 0)
        self.assertEqual(c["port"], "")
        self.assertEqual(c["feature"], "gear")
        self.assertEqual(c["gear"], {"neutral": "N", "no_data": "blank"})
        for bad in (None, [], "x", {"gear": "x"}):
            self.assertEqual(M.normalized(bad)["gear"]["neutral"], "N")
        self.assertEqual(M.normalized({"brightness": float("nan")})["brightness"], 4)
        self.assertEqual(M.normalized({"brightness": -5})["brightness"], 0)
        self.assertEqual(M.normalized({"rotation": 270})["rotation"], 270)


class GearTests(unittest.TestCase):
    def test_gear_chars(self):
        self.assertEqual([M.gear_char(g) for g in (-1, 0, 1, 5, 9, 10, 12)], ["R", "N", "1", "5", "9", "+", "+"])
        self.assertEqual(M.gear_char(0, "0"), "0")
        self.assertEqual(M.gear_char(0, "x"), "N")
        self.assertIsNone(M.gear_char(None))

    def snap(self, gear, live=True, valid=True):
        return {"t": {"gear": gear}, "live": live, "valid": valid}

    def test_live_gear_normalizes_per_game(self):
        self.assertEqual(M.live_gear(self.snap(0), "ACC"), -1)       # ACC/AC: 0=R, 1=N, 2=1. vites
        self.assertEqual(M.live_gear(self.snap(1), "ACC"), 0)
        self.assertEqual(M.live_gear(self.snap(2), "AC"), 1)
        self.assertEqual(M.live_gear(self.snap(-1), "iRacing"), -1)  # digerlerinde -1=R, 0=N
        self.assertEqual(M.live_gear(self.snap(3), "LMU"), 3)

    def test_no_data_returns_none_never_invents(self):
        for s in (None, {}, self.snap(2, live=False), self.snap(2, valid=False), {"t": None, "live": True},
                  {"t": {}, "live": True}, {"t": {"gear": "x"}, "live": True}):
            self.assertIsNone(M.live_gear(s, "ACC"), s)

    def test_feature_image(self):
        cfg = M.normalized({})
        rows, info = M.feature_image(cfg, 3)
        self.assertEqual(rows, M.glyph("3"))
        self.assertIn("3", info)
        self.assertEqual(M.feature_image(cfg, None)[0], M.BLANK)
        cfg = M.normalized({"gear": {"no_data": "dash", "neutral": "0"}})
        self.assertEqual(M.feature_image(cfg, None)[0], M.glyph("-"))
        self.assertEqual(M.feature_image(cfg, 0)[0], M.glyph("0"))


# ---------------------------------------------------------------- kontrolcu
class FakeLink:
    def __init__(self, connected=True, ready=True, led_version=1, fw_version=None):
        self.connected, self.ready = connected, ready
        self.led_version, self.fw_version = led_version, fw_version
        self.sent = []

    @property
    def led_ok(self):
        return self.led_version is not None and self.led_version >= 1

    def write_line(self, s):
        self.sent.append(s)
        return True


class FakeSrc:
    NAME = "LMU"


class FakeEngine:
    def __init__(self, gear=None, live=True):
        self.src = FakeSrc()
        self.snap = {"t": {"gear": gear} if gear is not None else None, "live": live, "valid": True}


def ctl(link, engine, **cfg):
    base = {"enabled": True}
    base.update(cfg)
    return LedController(link, engine, lambda: base)


class ControllerTests(unittest.TestCase):
    def test_sends_brightness_then_gear_image(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=3), brightness=7)
        c.tick(100.0)
        self.assertEqual(link.sent, ["B,7", "D,%s" % M.to_hex(M.glyph("3"))])
        self.assertEqual(c.status["level"], "ok")
        self.assertEqual(c.status["gear"], 3)

    def test_gear_change_is_sent_immediately_and_unchanged_is_not_resent(self):
        link, eng = FakeLink(), FakeEngine(gear=3)
        c = ctl(link, eng)
        c.tick(100.0)
        n = len(link.sent)
        c.tick(100.1)
        self.assertEqual(len(link.sent), n)                         # ayni goruntu: tekrar yok
        eng.snap["t"]["gear"] = 4
        c.tick(100.15)
        self.assertEqual(link.sent[-1], "D,%s" % M.to_hex(M.glyph("4")))

    def test_keepalive_resends_same_image(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=2))
        c.tick(100.0)
        n = len(link.sent)
        c.tick(101.2)
        self.assertEqual(len(link.sent), n + 1)

    def test_orientation_applies_to_sent_data_not_preview(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=3), rotation=90, flip_h=True)
        c.tick(100.0)
        self.assertEqual(link.sent[-1], "D,%s" % M.to_hex(M.transform(M.glyph("3"), 90, True, False)))
        self.assertEqual(c.status["rows"], M.glyph("3"))            # onizleme dogal yonde

    def test_reverse_and_neutral(self):
        link, eng = FakeLink(), FakeEngine(gear=-1)
        c = ctl(link, eng)
        c.tick(100.0)
        self.assertEqual(link.sent[-1], "D,%s" % M.to_hex(M.glyph("R")))
        eng.snap["t"]["gear"] = 0
        c.tick(100.1)
        self.assertEqual(link.sent[-1], "D,%s" % M.to_hex(M.glyph("N")))

    def test_acc_gear_offset_is_applied(self):
        link = FakeLink()
        eng = FakeEngine(gear=2)
        eng.src.NAME = "ACC"                                         # ACC'de 2 = 1. vites
        FakeSrc.NAME = "LMU"
        c = ctl(link, eng)
        c.engine.src = type("S", (), {"NAME": "ACC"})()
        c.tick(100.0)
        self.assertEqual(link.sent[-1], "D,%s" % M.to_hex(M.glyph("1")))

    def test_no_game_data_blank_or_dash_never_a_fake_gear(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=None))
        c.tick(100.0)
        self.assertEqual(link.sent[-1], "D,%s" % ("0" * 16))
        link2 = FakeLink()
        c2 = ctl(link2, FakeEngine(gear=3, live=False), gear={"no_data": "dash"})
        c2.tick(100.0)
        self.assertEqual(link2.sent[-1], "D,%s" % M.to_hex(M.glyph("-")))

    def test_disabled_shows_blank(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=5), enabled=False)
        c.tick(100.0)
        self.assertEqual(link.sent[-1], "D,%s" % ("0" * 16))
        self.assertEqual(c.status["level"], "off")

    def test_not_connected_sends_nothing(self):
        link = FakeLink(connected=False)
        c = ctl(link, FakeEngine(gear=3))
        c.tick(100.0)
        self.assertEqual(link.sent, [])
        self.assertIn("bağlı değil", c.status["text"])

    def test_not_ready_sends_nothing(self):
        link = FakeLink(ready=False)
        c = ctl(link, FakeEngine(gear=3))
        c.tick(100.0)
        self.assertEqual(link.sent, [])

    def test_asks_version_until_led_board_answers(self):
        link = FakeLink(led_version=None)
        c = ctl(link, FakeEngine(gear=3))
        c.tick(100.0)
        c.tick(100.5)
        c.tick(101.2)
        self.assertEqual(link.sent, ["V", "V"])                      # 1 sn arayla sorar, goruntu GONDERMEZ
        self.assertEqual(c.status["level"], "warn")

    def test_silent_board_gets_a_clear_message(self):
        link = FakeLink(led_version=None)
        c = ctl(link, FakeEngine(gear=3))
        c.tick(100.0)
        c.tick(105.0)
        self.assertEqual(c.status["level"], "bad")
        self.assertIn("LedMatrix.ino", c.status["text"])
        self.assertFalse([s for s in link.sent if s.startswith("D,")])

    def test_pedal_arduino_on_led_port_is_detected(self):
        link = FakeLink(led_version=None, fw_version=4)
        c = ctl(link, FakeEngine(gear=3))
        c.tick(100.0)
        self.assertEqual(c.status["level"], "bad")
        self.assertIn("pedal/fan", c.status["text"])
        self.assertFalse([s for s in link.sent if s.startswith("D,") or s.startswith("B,")])

    def test_reconnect_resends_brightness_and_image(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=3), brightness=9)
        c.tick(100.0)
        link.connected = False
        c.tick(100.1)
        link.connected = True
        link.sent.clear()
        c.tick(100.2)
        self.assertEqual(link.sent, ["B,9", "D,%s" % M.to_hex(M.glyph("3"))])

    def test_test_pattern_overrides_and_expires(self):
        link = FakeLink()
        c = ctl(link, FakeEngine(gear=3), enabled=False)
        c.start_test(M.all_on(), 4.0)
        t = time.monotonic()
        c.tick(t)
        self.assertEqual(link.sent[-1], "D,%s" % ("FF" * 8))
        self.assertEqual(c.status["level"], "ok")
        c.tick(t + 5.0)
        self.assertEqual(link.sent[-1], "D,%s" % ("0" * 16))
        self.assertIsNone(c.test)

    def test_brightness_change_is_sent(self):
        link = FakeLink()
        cfg = {"enabled": True, "brightness": 3}
        c = LedController(link, FakeEngine(gear=3), lambda: cfg)
        c.tick(100.0)
        cfg["brightness"] = 12
        c.tick(100.1)
        self.assertIn("B,12", link.sent)

    def test_garbage_config_does_not_crash(self):
        link = FakeLink()
        c = LedController(link, FakeEngine(gear=3), lambda: {"brightness": "x", "rotation": 7, "enabled": True})
        c.tick(100.0)
        self.assertTrue(link.sent)

    def test_does_not_modify_engine_snapshot(self):
        eng = FakeEngine(gear=3)
        before = repr(eng.snap)
        ctl(FakeLink(), eng).tick(100.0)
        self.assertEqual(repr(eng.snap), before)


# ---------------------------------------------------------------- baglanti: LED tanima
class FakeSer:
    def __init__(self, link, lines):
        self.link, self.lines = link, list(lines)

    def readline(self):
        if self.lines:
            return self.lines.pop(0)
        self.link.ser = None                                          # okuyucu iplik cikis yapsin
        return b""


class LinkTests(unittest.TestCase):
    def read(self, link, lines):
        ser = FakeSer(link, lines)
        link.ser = ser
        link._reader(ser)

    def test_led_board_identification(self):
        link = LedLink()
        self.read(link, [b"LED1\r\n"])
        self.assertTrue(link.led_ok)
        self.assertEqual(link.led_version, 1)
        self.assertIsNone(link.fw_version)

    def test_pedal_board_is_not_a_led_board(self):
        link = LedLink()
        self.read(link, [b"V4\r\n"])
        self.assertFalse(link.led_ok)
        self.assertEqual(link.fw_version, 4)

    def test_garbage_version_marks_unknown(self):
        link = LedLink()
        self.read(link, [b"LEDx\r\n"])
        self.assertEqual(link.led_version, 0)
        self.assertFalse(link.led_ok)

    def test_farewell_clears_led_and_pedal_stops_everything(self):
        self.assertEqual(LedLink.FAREWELL, b"C\n")
        self.assertIn(b"M4,0,0", ArduinoLink.FAREWELL)
        self.assertIn(b"F4,0", ArduinoLink.FAREWELL)

    def test_pedal_link_has_no_led_identity(self):
        self.assertIsNone(ArduinoLink().led_version)


# ---------------------------------------------------------------- Arduino kodu (ana makinede derlenip simule edilir)
@unittest.skipUnless(shutil.which("g++"), "g++ yok: firmware simulasyonu atlandi")
class LedFirmwareSimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.exe = os.path.join(cls.dir, "led_sim")
        r = subprocess.run(["g++", "-std=c++14", "-I", os.path.join(ROOT, "tests", "firmware_sim"), "-o", cls.exe,
                            os.path.join(ROOT, "tests", "firmware_sim", "harness_led.cpp")], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("LED firmware derlenemedi:\n" + r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def sim(self, script):
        r = subprocess.run([self.exe], input="\n".join(script) + "\n", capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()

    def test_identifies_itself_as_led_board(self):
        self.assertEqual(self.sim(["feed V", "loop", "out"])[0], "OUT:LED1")

    def test_pedal_firmware_does_not_identify_as_led(self):
        with open(os.path.join(ROOT, "firmware", "PedalHaptic", "PedalHaptic.ino"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn('"LED"', src)

    def test_starts_awake_and_blank(self):
        out = self.sim(["rows", "bright"])
        self.assertEqual(out[0], "0" * 16)
        self.assertEqual(out[1], "4 0")                              # parlaklik 4, uyku modunda DEGIL

    def test_every_glyph_arrives_intact(self):
        for ch in "RN0123456789-+":
            hx = M.to_hex(M.glyph(ch))
            out = self.sim(["time 10", "feed D,%s" % hx, "loop", "rows"])
            self.assertEqual(out[-1], hx, ch)

    def test_lowercase_hex_accepted(self):
        out = self.sim(["time 10", "feed D,3c66666666663c00", "loop", "rows"])
        self.assertEqual(out[-1], "3C66666666663C00")

    def test_invalid_images_are_ignored(self):
        good = "3C66666666663C00"
        out = self.sim(["time 10", "feed D,%s" % good, "loop",
                        "feed D,3C66", "feed D,%sFF" % good, "feed D,ZZ66666666663C00", "feed D", "feed D9,%s" % good,
                        "loop", "rows"])
        self.assertEqual(out[-1], good)                              # bozuk komutlar mevcut goruntuyu bozmaz

    def test_brightness_range(self):
        self.assertEqual(self.sim(["feed B,9", "loop", "bright"])[-1], "9 0")
        self.assertEqual(self.sim(["feed B,99", "loop", "bright"])[-1], "15 0")
        self.assertEqual(self.sim(["feed B,-3", "loop", "bright"])[-1], "0 0")

    def test_clear_command(self):
        out = self.sim(["time 10", "feed D,FFFFFFFFFFFFFFFF", "loop", "feed C", "loop", "rows"])
        self.assertEqual(out[-1], "0" * 16)

    def test_screen_clears_after_3_seconds_without_commands(self):
        out = self.sim(["time 10", "feed D,FFFFFFFFFFFFFFFF", "loop", "rows",
                        "time 2900", "loop", "rows", "time 3100", "loop", "rows"])
        self.assertEqual(out[0], "FF" * 8)
        self.assertEqual(out[1], "FF" * 8)                           # 2.9 sn: hala yaniyor
        self.assertEqual(out[2], "0" * 16)                           # 3.1 sn: temizlendi

    def test_keepalive_refresh_keeps_screen(self):
        out = self.sim(["time 10", "feed D,FFFFFFFFFFFFFFFF", "loop",
                        "time 2500", "feed D,FFFFFFFFFFFFFFFF", "loop", "time 5000", "loop", "rows"])
        self.assertEqual(out[-1], "FF" * 8)                          # 2.5 sn'de tazelendi, 5.0'da 2.5 sn gecmis

    def test_ping(self):
        self.assertEqual(self.sim(["feed P", "loop", "out"])[0], "OUT:P")

    def test_firmware_documents_wiring_and_library(self):
        with open(os.path.join(ROOT, "firmware", "LedMatrix", "LedMatrix.ino"), encoding="utf-8") as fh:
            src = fh.read()
        for token in ("#include <LedControl.h>", "PIN_DIN 12", "PIN_CLK 11", "PIN_CS 10", "LED_FW_VERSION 1"):
            self.assertIn(token, src)


if __name__ == "__main__":
    unittest.main()
