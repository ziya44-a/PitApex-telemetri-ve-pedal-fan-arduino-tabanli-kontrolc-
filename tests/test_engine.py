import copy
import unittest

from core.engine import DEFAULTS, EFFECTS, Engine, norm_gear


def make(src="LMU", **over):
    cfg = copy.deepcopy(DEFAULTS)
    for k in cfg:
        cfg[k]["enabled"] = False
    for k, d in over.items():
        cfg[k].update(d)
    e = Engine(cfg, None)
    e.src.NAME = src
    return e


def T(**kw):
    t = {"packetId": 1, "gas": 0.0, "brake": 0.0, "abs": 0.0, "tc": 0.0, "speed": 100.0,
         "slipRatio": [0.0] * 4, "valid": True, "gear": 3, "rpm_ratio": 0.0}
    t.update(kw)
    return t


class Clock:
    def __init__(self):
        self.t = 1000.0

    def tick(self, e, t, dt=0.01):
        self.t += dt
        return e.compute(t, self.t)


class BrakeLimiterTests(unittest.TestCase):
    def setUp(self):
        self.c = Clock()

    def test_no_vibration_below_threshold_and_starts_at_threshold(self):
        e = make(blim=dict(enabled=True, thr=80, full=100, hyst=5, hold=0, intensity=60))
        for b in (0.0, 0.5, 0.79):
            self.assertEqual(self.c.tick(e, T(brake=b))[0][0], 0)
        self.assertGreater(self.c.tick(e, T(brake=0.80))[0][0], 0)
        self.assertEqual(self.c.tick(e, T(brake=0.80))[1][0], 0)          # gaz motoru etkilenmez

    def test_never_exceeds_intensity_and_max_power(self):
        e = make(blim=dict(enabled=True, thr=80, intensity=50, hold=0))
        out = self.c.tick(e, T(brake=1.0))[0][0]
        self.assertEqual(out, e.motor_pwm(0, 50))
        e2 = make(blim=dict(enabled=True, thr=80, intensity=100, max_pct=40, hold=0))
        self.assertEqual(self.c.tick(e2, T(brake=1.0))[0][0], e2.motor_pwm(0, 40))

    def test_hysteresis_prevents_chatter_around_threshold(self):
        e = make(blim=dict(enabled=True, thr=80, hyst=5, hold=0))
        states = []
        for b in (0.81, 0.79, 0.81, 0.78, 0.80, 0.77, 0.76):    # esik civarinda titreyen pedal
            states.append(self.c.tick(e, T(brake=b))[0][0] > 0)
        self.assertEqual(states, [True] * 7)                      # 0.75 altina inmeden kapanmaz
        self.assertEqual(self.c.tick(e, T(brake=0.74))[0][0], 0)
        self.assertEqual(self.c.tick(e, T(brake=0.79))[0][0], 0)  # tekrar acilmasi icin esige cikmali
        self.assertGreater(self.c.tick(e, T(brake=0.80))[0][0], 0)

    def test_independent_of_abs_and_lock(self):
        e = make(blim=dict(enabled=True, thr=80, hold=0), abs=dict(enabled=False))
        self.assertEqual(self.c.tick(e, T(brake=0.3, abs=1.0))[0][0], 0)      # ABS kapali, limiter esik altinda
        e = make(abs=dict(enabled=True, hold=60, intensity=80))
        e.cfg["blim"]["enabled"] = False
        self.assertEqual(self.c.tick(e, T(brake=1.0))[0][0], 0)               # limiter kapaliyken fren tek basina yok
        self.assertGreater(self.c.tick(e, T(brake=0.2, abs=1.0))[0][0], 0)

    def test_disabled_clears_output_immediately(self):
        e = make(blim=dict(enabled=True, thr=80, hold=200))
        self.assertGreater(self.c.tick(e, T(brake=1.0))[0][0], 0)
        e.cfg["blim"]["enabled"] = False
        self.assertEqual(self.c.tick(e, T(brake=1.0))[0][0], 0)
        e.cfg["blim"]["enabled"] = True
        self.assertGreater(self.c.tick(e, T(brake=1.0))[0][0], 0)


class GearTests(unittest.TestCase):
    def setUp(self):
        self.c = Clock()

    def run_gears(self, e, gears, dt=0.01):
        outs = []
        for g in gears:
            out = self.c.tick(e, T(gear=g), dt)
            outs.append(out[1][0] > 0)
        return outs

    def test_gear_up_triggers_once_per_shift(self):
        e = make(gup=dict(enabled=True, hold=50, sens=100, motor=1))
        outs = self.run_gears(e, [3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4])
        self.assertTrue(any(outs[2:5]))
        self.assertFalse(any(outs[9:]))                       # sure bitti, tekrar titresmez
        # olay sayisi: aktif -> pasif gecisleri
        edges = sum(1 for a, b in zip([False] + outs, outs) if b and not a)
        self.assertEqual(edges, 1)

    def test_gear_down_does_not_trigger_gear_up_and_vice_versa(self):
        e = make(gup=dict(enabled=True, hold=50, sens=100), gdown=dict(enabled=True, hold=50, sens=100, motor=0))
        self.c.tick(e, T(gear=4))
        out = self.c.tick(e, T(gear=3))
        self.assertGreater(out[0][0], 0)                      # gdown -> M1
        self.assertEqual(out[1][0], 0)                        # gup yok
        for _ in range(20):
            out = self.c.tick(e, T(gear=3))
        self.c.tick(e, T(gear=4))
        out = self.c.tick(e, T(gear=4))
        self.assertGreater(out[1][0], 0)                      # gup -> M2
        self.assertEqual(out[0][0], 0)

    def test_same_gear_no_effect(self):
        e = make(gup=dict(enabled=True, sens=100), gdown=dict(enabled=True, sens=100))
        for _ in range(50):
            out = self.c.tick(e, T(gear=3))
            self.assertEqual(out, [(0, 0, 50)] * 4)

    def test_neutral_flicker_is_one_event_with_low_sensitivity(self):
        e = make(gup=dict(enabled=True, hold=30, sens=40), gdown=dict(enabled=True, hold=30, sens=40, motor=0))
        seq = [2] * 5 + [0] * 3 + [3] * 30            # (LMU: 0=N) 2 -> N (24 ms) -> 3, esik 90 ms
        ups, downs = 0, 0
        prev_u = prev_d = False
        for g in seq:
            out = self.c.tick(e, T(gear=g))
            u, d = out[1][0] > 0, out[0][0] > 0
            ups += u and not prev_u
            downs += d and not prev_d
            prev_u, prev_d = u, d
        self.assertEqual((ups, downs), (1, 0))

    def test_reverse_and_neutral_transitions_are_not_events(self):
        e = make(gup=dict(enabled=True, sens=100), gdown=dict(enabled=True, sens=100))
        for g in (0, 0, -1, -1, 0, 0, 1, 1):
            out = self.c.tick(e, T(gear=g))
            self.assertEqual(out, [(0, 0, 50)] * 4)

    def test_acc_gear_numbering_is_normalised(self):
        self.assertEqual((norm_gear("ACC", 0), norm_gear("ACC", 1), norm_gear("ACC", 2)), (-1, 0, 1))
        self.assertEqual((norm_gear("LMU", -1), norm_gear("LMU", 0), norm_gear("LMU", 1)), (-1, 0, 1))
        e = make(src="ACC", gup=dict(enabled=True, hold=50, sens=100))
        self.c.tick(e, T(gear=2))                              # ACC: 1. vites
        self.assertGreater(self.c.tick(e, T(gear=3))[1][0], 0)  # 2. vites -> yukselti

    def test_disabled_gear_effect_silent_and_state_resets(self):
        e = make(gup=dict(enabled=False, hold=200, sens=100))
        self.c.tick(e, T(gear=3))
        self.assertEqual(self.c.tick(e, T(gear=4)), [(0, 0, 50)] * 4)

    def test_no_telemetry_resets_detectors(self):
        e = make(gup=dict(enabled=True, hold=50, sens=100))
        self.c.tick(e, T(gear=3))
        self.c.tick(e, None)
        self.assertEqual(self.c.tick(e, T(gear=4)), [(0, 0, 50)] * 4)   # yeniden esleme, olay yok


class LegacyBehaviourTests(unittest.TestCase):
    def test_defaults_keep_old_effect_output(self):
        e = make(abs=dict(enabled=True, intensity=80, hold=60), lock=dict(enabled=True))
        out = e.compute(T(abs=1.0), 5.0)
        self.assertEqual(out[0], (e.motor_pwm(0, 80), 120, 50))

    def test_lock_ramp_unchanged_at_default_sensitivity(self):
        e = make(lock=dict(enabled=True, intensity=100, thr=0.25, hold=0))
        e.cfg["lock"]["hold"] = 50
        out = e.compute(T(brake=0.5, slipRatio=[-0.5, -0.5, 0, 0]), 5.0)
        # eski formul: 0.5 + 0.5*min(1,(0.5-0.25)/0.5) = 0.75 siddet
        self.assertEqual(out[0][0], e.motor_pwm(0, 75))
        e.cfg["lock"]["sens"] = 100                            # daha hassas: tam guce daha cabuk cikar
        self.assertEqual(e.compute(T(brake=0.5, slipRatio=[-0.5, -0.5, 0, 0]), 6.0)[0][0], e.motor_pwm(0, 100))

    def test_each_effect_has_defaults_and_names(self):
        self.assertEqual(set(EFFECTS), set(DEFAULTS))
        for k in ("blim", "gup", "gdown"):
            self.assertIn(k, EFFECTS)


if __name__ == "__main__":
    unittest.main()
