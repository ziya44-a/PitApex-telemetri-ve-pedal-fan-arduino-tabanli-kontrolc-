import time
import unittest

from tests.helpers import temp_dm  # noqa: F401  (sys.path ayari)
from hardware.fan import FanController, curve_pct, normalized, pct_to_pwm


class FakeLink:
    def __init__(self, connected=True, ready=True, fw=3):
        self.connected, self.ready, self.fw_version = connected, ready, fw
        self.sent = []

    @property
    def fan_supported(self):
        return self.fw_version is not None and self.fw_version >= 3

    def write_line(self, s):
        self.sent.append(s)
        return True


class FakeEngine:
    def __init__(self, speed=None, live=True):
        self.snap = {"t": {"speed": speed} if speed is not None else None, "live": live, "valid": True}


def make(link, engine, **cfg):
    base = {"enabled": True}
    base.update(cfg)
    return FanController(link, engine, lambda: base)


class CurveTests(unittest.TestCase):
    def test_user_example_points(self):
        c = {"idle_pct": 25, "mid_speed": 150, "mid_pct": 50, "max_speed": 300}
        self.assertAlmostEqual(curve_pct(0, c), 25)
        self.assertAlmostEqual(curve_pct(150, c), 50)
        self.assertAlmostEqual(curve_pct(300, c), 100)
        self.assertAlmostEqual(curve_pct(400, c), 100)
        self.assertAlmostEqual(curve_pct(75, c), 37.5)

    def test_power_cap(self):
        c = {"max_pct": 80}
        self.assertLessEqual(curve_pct(500, c), 80)

    def test_bad_values_are_clamped_not_crash(self):
        c = normalized({"mid_speed": "abc", "max_speed": -5, "idle_pct": 999})
        self.assertGreaterEqual(c["max_speed"], 50)
        self.assertLessEqual(c["idle_pct"], 100)

    def test_pwm_mapping(self):
        self.assertEqual(pct_to_pwm(0, {}), 0)
        self.assertEqual(pct_to_pwm(100, {"min_pwm": 60}), 255)
        self.assertGreaterEqual(pct_to_pwm(1, {"min_pwm": 60}), 60)


class ControllerTests(unittest.TestCase):
    def run_ticks(self, fc, n=60, step=0.05):
        t = time.monotonic()
        for i in range(n):
            fc.tick(t + i * step)

    def test_follows_speed_and_sends_commands(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=300), kick_ms=0)
        self.run_ticks(fc, 200)
        self.assertEqual(link.sent[-1], "F,255")
        self.assertEqual(fc.status["level"], "ok")

    def test_no_telemetry_default_stops_fan(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=None), kick_ms=0)
        self.run_ticks(fc, 40)
        self.assertEqual(link.sent[-1], "F,0")
        self.assertIn("Telemetri yok", fc.status["text"])

    def test_no_telemetry_idle_option(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=None), no_data="idle", kick_ms=0)
        self.run_ticks(fc, 200)
        self.assertNotEqual(link.sent[-1], "F,0")
        self.assertIn("rölanti", fc.status["text"])

    def test_not_live_means_no_data_even_if_speed_present(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=250, live=False), kick_ms=0)
        self.run_ticks(fc, 40)
        self.assertEqual(link.sent[-1], "F,0")

    def test_disabled_sends_zero(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=250), enabled=False)
        self.run_ticks(fc, 20)
        self.assertEqual(set(link.sent), {"F,0"})
        self.assertEqual(fc.status["text"], "Kapalı")

    def test_old_firmware_never_sends_and_explains(self):
        link = FakeLink(fw=2)
        fc = make(link, FakeEngine(speed=250))
        self.run_ticks(fc, 20)
        self.assertEqual(link.sent, [])
        self.assertIn("eski", fc.status["text"])

    def test_disconnected_never_sends(self):
        link = FakeLink(connected=False, ready=False)
        fc = make(link, FakeEngine(speed=250))
        self.run_ticks(fc, 20)
        self.assertEqual(link.sent, [])
        self.assertIn("bağlı değil", fc.status["text"])

    def test_smoothing_no_instant_jump(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=300), kick_ms=0)
        t = time.monotonic()
        fc.tick(t)
        fc.tick(t + 0.05)
        self.assertLess(fc.status["pct"], 20)       # 0.05 sn'de %100'e atlamaz

    def test_kick_start_gives_full_power_briefly(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=0), idle_pct=25, kick_ms=400, ramp_up=1000)
        t = time.monotonic()
        fc.tick(t)
        fc.tick(t + 0.05)
        self.assertEqual(link.sent[-1], "F,255")      # kalkis darbesi
        fc.tick(t + 1.0)
        self.assertNotEqual(link.sent[-1], "F,255")   # sonra rolanti gucune iner

    def test_test_mode(self):
        link = FakeLink()
        fc = make(link, FakeEngine(speed=None), enabled=False, kick_ms=0, ramp_up=1000)
        fc.start_test(60, 5)
        self.run_ticks(fc, 30)
        self.assertNotEqual(link.sent[-1], "F,0")
        self.assertIn("Test", fc.status["text"])


if __name__ == "__main__":
    unittest.main()
