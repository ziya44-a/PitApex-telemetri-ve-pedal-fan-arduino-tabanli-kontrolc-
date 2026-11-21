import ctypes
import struct
import unittest

from tests.helpers import temp_dm  # noqa: F401
from telemetry import iracing, lmu
from telemetry.ac_family import (ACAdapter, ACCAdapter, GraphicsAC, GraphicsACC, PhysicsACC, StaticAC)
from telemetry.legacy_sources import Physics
from telemetry.lmu import (LMUAdapter, RF2ScoringInfo, RF2Vehicle, RF2VehicleScoring)
from telemetry.naming import pretty_id


def setw(arr, s):
    for i, ch in enumerate(s):
        arr[i] = ord(ch)


class FakeMem:
    def __init__(self, data):
        self.data = data

    def read_at(self, off, size):
        return bytes(self.data[off:off + size])

    def close(self):
        pass


# ---------------------------------------------------------------- ACC / AC
def acc_bufs(status=2, **kw):
    p = PhysicsACC()
    p.packetId, p.gas, p.brake, p.fuel, p.gear, p.rpms, p.speedKmh = 1000, 0.8, 0.0, 42.5, 4, 7200, 187.0
    p.abs, p.tc = 0.0, 0.3
    for i in range(4):
        p.tyreCoreTemperature[i] = 80.0 + i
        p.wheelsPressure[i] = 27.5
    p.waterTemp, p.isEngineRunning, p.ignitionOn = 92.0, 1, 1
    g = GraphicsACC()
    g.packetId, g.status, g.session = 500, status, 2
    g.completedLaps, g.iCurrentTime, g.iLastTime, g.iBestTime = 3, 12345, 141222, 140500
    g.currentSectorIndex, g.lastSectorTime, g.isValidLap, g.TC, g.ABS = 1, 40100, 1, 3, 4
    s = StaticAC()
    setw(s.carModel, "ferrari_296_gt3")
    setw(s.track, "spa")
    s.sectorCount = 3
    for k, v in kw.items():
        obj, name = k.split("__")
        setattr({"p": p, "g": g, "s": s}[obj], name, v)
    return bytes(p), bytes(g), bytes(s)


class ACCTests(unittest.TestCase):
    def parse(self, **kw):
        a = ACCAdapter()
        return a.parse(*acc_bufs(**kw))

    def test_live_frame_fields(self):
        f = self.parse()
        self.assertTrue(f.live)
        self.assertEqual((f.track_id, f.track_name), ("spa", "Spa-Francorchamps"))
        self.assertEqual((f.car_id, f.car_name), ("ferrari_296_gt3", "Ferrari 296 GT3"))
        self.assertAlmostEqual(f.speed_kmh, 187.0, places=3)
        self.assertEqual(f.gear, 3)                         # ACC 4 -> 3. vites
        self.assertAlmostEqual(f.tyre_press_kpa[0], 27.5 * 6.894757, places=2)
        self.assertEqual(f.tyre_temp_c, [80.0, 81.0, 82.0, 83.0])
        self.assertAlmostEqual(f.water_c, 92.0)
        self.assertTrue(f.engine_running)
        self.assertIsNone(f.oil_c)                          # ACC'de yok -> None
        self.assertEqual((f.abs_level, f.tc_level), (4.0, 3.0))
        self.assertAlmostEqual(f.tc_active, 0.3, places=3)
        self.assertEqual((f.lap_count, f.lap_last_ms, f.lap_best_ms, f.sector_index), (3, 141222, 140500, 1))
        self.assertTrue(f.lap_valid)

    def test_garbage_status_gives_no_values(self):
        f = self.parse(g__status=77)
        self.assertFalse(f.live)
        self.assertIn("uyuşmuyor", f.state)
        self.assertIsNone(f.speed_kmh)
        self.assertIsNone(f.track_id)

    def test_paused_has_context_but_no_live_values(self):
        f = self.parse(g__status=3)
        self.assertFalse(f.live)
        self.assertEqual(f.track_id, "spa")
        self.assertIsNone(f.speed_kmh)
        self.assertIsNone(f.lap_count)

    def test_zero_means_unavailable(self):
        p = PhysicsACC.from_buffer_copy(acc_bufs()[0])
        for i in range(4):
            p.tyreCoreTemperature[i] = 0.0
            p.wheelsPressure[i] = 0.0
        p.waterTemp = 0.0
        f = ACCAdapter().parse(bytes(p), acc_bufs()[1], acc_bufs()[2])
        self.assertIsNone(f.tyre_temp_c)
        self.assertIsNone(f.tyre_press_kpa)
        self.assertIsNone(f.water_c)

    def test_implausible_values_are_dropped(self):
        f = self.parse(p__speedKmh=9999.0, p__waterTemp=5000.0, p__fuel=-3.0)
        self.assertIsNone(f.speed_kmh)
        self.assertIsNone(f.water_c)
        self.assertIsNone(f.fuel_l)

    def test_misaligned_physics_tail_disables_engine_and_water(self):
        f = self.parse(p__isEngineRunning=123456)           # yapi uyusmuyor belirtisi
        self.assertIsNone(f.water_c)
        self.assertEqual(f.engine_running, f.rpm > 100)     # gercek devirden turetilir, bayrak kullanilmaz

    def test_bad_graphics_tail_disables_lap_tracking(self):
        f = self.parse(g__isValidLap=9)
        self.assertIsNone(f.lap_count)
        self.assertTrue(any("tur takibi kapalı" in n for n in f.notes))

    def test_int_max_laptimes_are_none(self):
        f = self.parse(g__iLastTime=2147483647, g__iBestTime=2147483647)
        self.assertIsNone(f.lap_last_ms)
        self.assertIsNone(f.lap_best_ms)

    def test_short_buffers_are_untrusted_not_zero_filled(self):
        p, g, s = acc_bufs()
        f = ACCAdapter().parse(p[:100], g, s)                 # fizik kisa: hicbir deger gosterilmez
        self.assertFalse(f.live)
        self.assertIn("uyuşmuyor", f.state)
        f = ACCAdapter().parse(p, g[:50], s)                  # grafik kisa
        self.assertFalse(f.live)
        self.assertIsNone(f.speed_kmh)
        f = ACCAdapter().parse(p, g[:ctypes.sizeof(GraphicsAC)], s)   # ACC'ye ozel kisim eksik: tur takibi kapali
        self.assertTrue(f.live)
        self.assertIsNone(f.lap_count)
        f = ACCAdapter().parse(p[:ctypes.sizeof(Physics)], g, s)      # fizik devami eksik: su/motor yok
        self.assertIsNone(f.water_c)
        f = ACCAdapter().parse(p, g, s[:100])                          # static kisa: pist/arac yok -> kayit yok
        self.assertIsNone(f.track_id)


class ACTests(unittest.TestCase):
    def bufs(self, **kw):
        p = Physics()
        p.packetId, p.gas, p.brake, p.fuel, p.gear, p.rpms, p.speedKmh = 5, 0.5, 0.0, 30.0, 2, 5000, 100.0
        p.abs, p.tc = 0.0, 0.0
        for i in range(4):
            p.tyreCoreTemperature[i] = 70.0
            p.wheelsPressure[i] = 26.0
        p.numberOfTyresOut = kw.pop("tyres_out", 0)
        g = GraphicsAC()
        g.status, g.completedLaps, g.iCurrentTime, g.iLastTime, g.currentSectorIndex = 2, 1, 5000, 100000, 0
        g.lastSectorTime = 33000
        s = StaticAC()
        setw(s.carModel, "ks_ferrari_488_gt3")
        setw(s.track, "ks_brands_hatch")
        setw(s.trackConfiguration, "indy")
        s.sectorCount = kw.pop("sectors", 3)
        return bytes(p)[:Physics.localVelocity.offset + 12], bytes(g), bytes(s)

    def test_fields_and_limits(self):
        f = ACAdapter().parse(*self.bufs())
        self.assertTrue(f.live)
        self.assertEqual(f.gear, 1)
        self.assertEqual(f.car_name, "Ferrari 488 GT3")
        self.assertEqual(f.track_id, "ks_brands_hatch|indy")
        self.assertIsNone(f.water_c)            # AC'de yok
        self.assertIsNone(f.oil_c)
        self.assertIsNone(f.abs_level)
        self.assertIsNone(f.lap_valid)          # AC gecerlilik vermez
        self.assertFalse(f.lap_suspect)

    def test_tyres_out_marks_suspect_only(self):
        f = ACAdapter().parse(*self.bufs(tyres_out=4))
        self.assertTrue(f.lap_suspect)
        self.assertIsNone(f.lap_valid)

    def test_non_three_sector_track_has_no_sector_data(self):
        f = ACAdapter().parse(*self.bufs(sectors=2))
        self.assertIsNone(f.sector_index)
        self.assertIsNone(f.last_sector_ms)

    def test_pretty_names(self):
        self.assertEqual(pretty_id("porsche_992_gt3_r"), "Porsche 992 GT3 R")
        self.assertEqual(pretty_id("amr_v8_vantage_gt3"), "Aston Martin V8 Vantage GT3")


# ---------------------------------------------------------------- iRacing
YAML = """---
WeekendInfo:
 TrackName: spa up
 TrackDisplayName: Circuit de Spa-Francorchamps
 TrackConfigName: Grand Prix Pits
 TrackCity: Stavelot
DriverInfo:
 DriverCarIdx: 7
 Drivers:
 - CarIdx: 0
   UserName: Biri Baska
   CarPath: mercedesamgevogt3
   CarScreenName: Mercedes-AMG GT3 2020
 - CarIdx: 7
   UserName: Ben
   CarPath: ferrari296gt3
   CarScreenName: 'Ferrari 296 GT3'
 - CarIdx: 8
   CarPath: porsche992rgt3
   CarScreenName: Porsche 911 GT3 R (992)
SessionInfo:
 Sessions:
 - SessionNum: 0
...
"""


def ir_memory(values, yaml_text=YAML, status=1, drop=()):
    vars_ = [("Speed", 4, 0), ("RPM", 4, 4), ("Gear", 2, 8), ("Throttle", 4, 12), ("Brake", 4, 16),
             ("BrakeABSactive", 1, 20), ("FuelLevel", 4, 24), ("WaterTemp", 4, 28), ("OilTemp", 4, 32),
             ("LapCompleted", 2, 36), ("LapLastLapTime", 4, 40), ("LapBestLapTime", 4, 44),
             ("LapCurrentLapTime", 4, 48), ("OnPitRoad", 1, 52), ("IsOnTrack", 1, 53),
             ("IsReplayPlaying", 1, 54), ("SessionTime", 5, 56), ("LFtempL", 4, 64), ("LFtempM", 4, 68),
             ("LFtempR", 4, 72), ("LFpressure", 4, 76), ("RFtempL", 4, 80), ("RFtempM", 4, 84),
             ("RFtempR", 4, 88), ("RFpressure", 4, 92), ("LRtempL", 4, 96), ("LRtempM", 4, 100),
             ("LRtempR", 4, 104), ("LRpressure", 4, 108), ("RRtempL", 4, 112), ("RRtempM", 4, 116),
             ("RRtempR", 4, 120), ("RRpressure", 4, 124)]
    vars_ = [v for v in vars_ if v[0] not in drop]
    n = len(vars_)
    voff = 112
    soff = voff + n * 144
    yb = yaml_text.encode("cp1252") + b"\0"
    boff = soff + len(yb)
    blen = 136
    buf = bytearray(boff + blen)
    struct.pack_into("<10i", buf, 0, 2, status, 60, 1, len(yb), soff, n, voff, 1, blen)
    struct.pack_into("<4i", buf, 48, 777, boff, 0, 0)
    buf[soff:soff + len(yb)] = yb
    fm = {1: "<?", 2: "<i", 4: "<f", 5: "<d"}
    for i, (name, vt, off) in enumerate(vars_):
        struct.pack_into("<3i", buf, voff + i * 144, vt, off, 1)
        buf[voff + i * 144 + 16:voff + i * 144 + 16 + len(name)] = name.encode()
        if name in values:
            struct.pack_into(fm[vt], buf, boff + off, values[name])
    return FakeMem(buf)


BASE = {"Speed": 50.0, "RPM": 7000.0, "Gear": 4, "Throttle": 0.9, "Brake": 0.0, "BrakeABSactive": False,
        "FuelLevel": 55.5, "WaterTemp": 88.0, "OilTemp": 101.0, "LapCompleted": 2, "LapLastLapTime": 141.222,
        "LapBestLapTime": 140.5, "LapCurrentLapTime": 33.3, "OnPitRoad": False, "IsOnTrack": True,
        "IsReplayPlaying": False, "SessionTime": 1234.5,
        "LFtempL": 80.0, "LFtempM": 82.0, "LFtempR": 84.0, "LFpressure": 190.0,
        "RFtempL": 80.0, "RFtempM": 82.0, "RFtempR": 84.0, "RFpressure": 190.0,
        "LRtempL": 80.0, "LRtempM": 82.0, "LRtempR": 84.0, "LRpressure": 190.0,
        "RRtempL": 80.0, "RRtempM": 82.0, "RRtempR": 84.0, "RRpressure": 190.0}


class IRacingTests(unittest.TestCase):
    def read(self, **over):
        vals = dict(BASE)
        drop = over.pop("drop", ())
        status = over.pop("status", 1)
        vals.update(over)
        return iracing.IRacingAdapter(ir_memory(vals, status=status, drop=drop)).read()

    def test_yaml_parse(self):
        r = iracing.parse_session_yaml(YAML)
        self.assertEqual(r["track_name"], "spa up")
        self.assertEqual(r["track_display"], "Circuit de Spa-Francorchamps")
        self.assertEqual(r["track_config"], "Grand Prix Pits")
        self.assertEqual((r["car_path"], r["car_screen"]), ("ferrari296gt3", "Ferrari 296 GT3"))   # DriverCarIdx=7

    def test_live_frame(self):
        f = self.read()
        self.assertTrue(f.live)
        self.assertAlmostEqual(f.speed_kmh, 180.0, places=2)
        self.assertEqual(f.gear, 4)
        self.assertEqual(f.car_name, "Ferrari 296 GT3")
        self.assertEqual(f.track_id, "spa up|Grand Prix Pits")
        self.assertAlmostEqual(f.fuel_l, 55.5, places=2)
        self.assertEqual((f.lap_count, f.lap_last_ms, f.lap_best_ms), (2, 141222, 140500))
        self.assertEqual(f.last_lap_sectors, None)
        self.assertIsNone(f.sector_index)                   # iRacing sektor vermez
        self.assertIsNone(f.tc_active)                      # TC yok, tahmin edilmez
        self.assertEqual(f.abs_active, 0.0)

    def test_abs_flag_real(self):
        self.assertEqual(self.read(BrakeABSactive=True).abs_active, 1.0)

    def test_tyres_only_in_pit(self):
        self.assertIsNone(self.read(OnPitRoad=False).tyre_temp_c)
        self.assertIsNone(self.read(OnPitRoad=False).tyre_press_kpa)
        f = self.read(OnPitRoad=True)
        self.assertAlmostEqual(f.tyre_temp_c[0], 82.0, places=3)
        self.assertAlmostEqual(f.tyre_press_kpa[3], 190.0, places=2)

    def test_garage_and_replay_not_live(self):
        self.assertFalse(self.read(IsOnTrack=False).live)
        self.assertIn("Garaj", self.read(IsOnTrack=False).state)
        f = self.read(IsReplayPlaying=True)
        self.assertFalse(f.live)
        self.assertIsNone(f.speed_kmh)

    def test_sim_not_running(self):
        f = self.read(status=0)
        self.assertFalse(f.live)
        self.assertIn("bağlı değil", f.state)

    def test_missing_core_var_means_no_data(self):
        f = self.read(drop=("IsOnTrack",))
        self.assertFalse(f.live)
        self.assertIn("uyuşmuyor", f.state)

    def test_invalid_last_lap_is_none(self):
        self.assertIsNone(self.read(LapLastLapTime=-1.0).lap_last_ms)

    def test_garbage_values_dropped(self):
        f = self.read(Speed=1e9, RPM=-5.0, WaterTemp=0.0, FuelLevel=float("nan"))
        self.assertIsNone(f.speed_kmh)
        self.assertIsNone(f.rpm)
        self.assertIsNone(f.water_c)
        self.assertIsNone(f.fuel_l)

    def test_no_yaml_means_no_track_or_car(self):
        a = iracing.IRacingAdapter(ir_memory(BASE, yaml_text=""))
        f = a.read()
        self.assertIsNone(f.track_id)
        self.assertIsNone(f.car_id)


# ---------------------------------------------------------------- LMU
def lmu_mems(vehicle_edit=None, scoring_edit=None, nveh=1, with_scoring=True, realtime=True,
             last_lap=0.0, lap_start=0.0, total_laps=0, s1=0.0, s2=0.0, elapsed=10.0):
    v = RF2Vehicle()
    v.mID = 5
    v.mElapsedTime, v.mLapStartET, v.mLapNumber = elapsed, lap_start, total_laps + 1
    v.mVehicleName, v.mTrackName = b"Ferrari AF Corse #51:HY", b"Circuit de la Sarthe"
    v.mLocalVel[2] = -60.0
    v.mEngineRPM, v.mEngineMaxRPM, v.mGear = 7000.0, 9000.0, 3
    v.mUnfilteredThrottle, v.mUnfilteredBrake = 0.7, 0.0
    v.mFuel, v.mEngineWaterTemp, v.mEngineOilTemp = 60.0, 90.0, 0.0
    for w in v.mWheels:
        for i in range(3):
            w.mTemperature[i] = 350.0
        w.mPressure = 160.0
    if vehicle_edit:
        vehicle_edit(v)
    tel = bytearray(16 + 1888 * nveh)
    struct.pack_into("<IIii", tel, 0, 1, 1, 0, nveh)
    tel[16:16 + 1888] = bytes(v)
    for k in range(1, nveh):
        o = RF2Vehicle()
        o.mID = 100 + k
        tel[16 + 1888 * k:16 + 1888 * (k + 1)] = bytes(o)
    if not with_scoring:
        return FakeMem(tel), FakeMem(bytes(16))
    info = RF2ScoringInfo()
    info.mNumVehicles = nveh
    info.mInRealtime = realtime
    sv = RF2VehicleScoring()
    sv.mID, sv.mIsPlayer, sv.mTotalLaps = 5, True, total_laps
    sv.mLastLapTime, sv.mLastSector1, sv.mLastSector2, sv.mBestLapTime = last_lap, s1, s2, last_lap
    if scoring_edit:
        scoring_edit(sv)
    sc = bytearray(12 + 548 + 584 * nveh)
    struct.pack_into("<IIi", sc, 0, 1, 1, 0)
    sc[12:12 + 548] = bytes(info)
    sc[560:560 + 584] = bytes(sv)
    for k in range(1, nveh):
        o = RF2VehicleScoring()
        o.mID = 100 + k
        sc[560 + 584 * k:560 + 584 * (k + 1)] = bytes(o)
    return FakeMem(tel), FakeMem(sc)


class LMUTests(unittest.TestCase):
    def test_structs_validated(self):
        self.assertTrue(lmu.STRUCTS_OK)

    def test_live_frame_no_estimates(self):
        a = LMUAdapter(*lmu_mems())
        f = a.read()
        self.assertTrue(f.live)
        self.assertAlmostEqual(f.speed_kmh, 216.0, places=2)
        self.assertEqual(f.gear, 3)
        self.assertEqual((f.track_name, f.car_name), ("Circuit de la Sarthe", "Ferrari AF Corse"))   # #51:HY atildi
        self.assertAlmostEqual(f.tyre_temp_c[0], 350.0 - 273.15, places=2)
        self.assertAlmostEqual(f.tyre_press_kpa[0], 160.0)
        self.assertAlmostEqual(f.water_c, 90.0)
        self.assertIsNone(f.oil_c)                         # 0 = veri yok
        self.assertIsNone(f.abs_active)                    # tahmin edilmez
        self.assertIsNone(f.tc_active)

    def test_not_in_realtime_not_live(self):
        f = LMUAdapter(*lmu_mems(realtime=False)).read()
        self.assertFalse(f.live)
        self.assertIsNone(f.speed_kmh)

    def test_lap_cross_check_accepts_matching_sources(self):
        a = LMUAdapter(*lmu_mems(lap_start=0.0, elapsed=5.0))
        a.read()
        f = a.__class__(*lmu_mems(lap_start=0.0))   # yeni nesne degil; ayni adaptore ikinci okuma:
        a.m_tel, a.m_sco = lmu_mems(lap_start=120.5, elapsed=125.0, total_laps=1,
                                    last_lap=120.5, s1=40.0, s2=90.0)
        f = a.read()
        self.assertEqual(f.lap_count, 1)
        self.assertEqual(f.lap_last_ms, 120500)
        self.assertEqual(f.last_lap_sectors, (40000, 50000, 30500))

    def test_lap_cross_check_rejects_mismatch(self):
        a = LMUAdapter(*lmu_mems(lap_start=0.0, elapsed=5.0))
        a.read()
        a.m_tel, a.m_sco = lmu_mems(lap_start=120.5, elapsed=125.0, total_laps=1,
                                    last_lap=118.0, s1=40.0, s2=90.0)     # skor tablosu telemetriyle celisiyor
        f = a.read()
        self.assertIsNone(f.lap_last_ms)
        self.assertIsNone(f.last_lap_sectors)

    def test_scoring_unreadable_single_vehicle_falls_back_without_laps(self):
        f = LMUAdapter(*lmu_mems(with_scoring=False)).read()
        self.assertIsNotNone(f)
        self.assertIsNone(f.lap_count)
        self.assertTrue(f.notes)

    def test_scoring_unreadable_multiple_vehicles_refuses(self):
        f = LMUAdapter(*lmu_mems(with_scoring=False, nveh=3)).read()
        self.assertFalse(f.live)
        self.assertIsNone(f.speed_kmh)

    def test_player_is_found_by_id_not_index(self):
        def edit(sv):
            sv.mID = 5
        tel, sco = lmu_mems(nveh=3)
        # oyuncu telemetri dizisinde ilk degil: 2. siraya tasi
        data = tel.data
        a, b = bytes(data[16:16 + 1888]), bytes(data[16 + 1888:16 + 2 * 1888])
        data[16:16 + 1888], data[16 + 1888:16 + 2 * 1888] = b, a
        f = LMUAdapter(tel, sco).read()
        self.assertEqual(f.car_name, "Ferrari AF Corse")


if __name__ == "__main__":
    unittest.main()
