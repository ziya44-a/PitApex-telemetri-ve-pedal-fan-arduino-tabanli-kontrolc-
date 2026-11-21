import unittest

from tests.helpers import temp_dm
from core.models import TelemetryFrame
from core.session import SessionTracker
from storage.records import RecordStore
from storage.sessions import SessionStore

DT = 0.05


class Sim:
    """Oyunu taklit eder: tur/sektor sayaclari, son tur suresi (istege bagli gecikmeli)."""

    def __init__(self, laps, game="ACC", track="spa", car="fer", cumulative_s2=False, last_lap_delay=0,
                 clock=False, sector_update_early=False, start_ms=0, count0=0, sectors=True, report=None):
        self.laps = list(laps)               # [(s1,s2,s3) ms]
        self.game, self.track, self.car = game, track, car
        self.cum = cumulative_s2
        self.delay = last_lap_delay
        self.use_clock = clock
        self.t = 100.0
        self.count = count0
        self.cur = start_ms
        self.idx = 0
        self.last_sector = 0
        self.last_lap = 0
        self.pending = []                    # (kalan_kare, deger)
        self.valid = True
        self.in_pit = False
        self.suspect = None
        self.live = True
        self.lap_i = 0
        self.sectors = sectors
        self.report = report or (lambda total: total)

    def lap(self):
        return self.laps[min(self.lap_i, len(self.laps) - 1)]

    def frame(self):
        f = TelemetryFrame(game=self.game, t=self.t, live=self.live, track_id=self.track, track_name=self.track.title(),
                           car_id=self.car, car_name=self.car.title(), speed_kmh=150.0, rpm=7000, throttle=0.8, brake=0.0)
        f.lap_count = self.count
        f.lap_current_ms = self.cur
        f.lap_last_ms = self.last_lap or None
        f.sector_index = self.idx if self.sectors else None
        f.last_sector_ms = (self.last_sector or None) if self.sectors else None
        f.lap_valid = self.valid
        f.in_pit = self.in_pit
        f.lap_suspect = self.suspect
        f.clock_s = self.t if self.use_clock else None
        return f

    def step(self):
        self.t += DT
        self.cur += int(DT * 1000)
        s1, s2, s3 = self.lap()
        if self.idx == 0 and self.cur >= s1:
            self.idx, self.last_sector = 1, s1
        elif self.idx == 1 and self.cur >= s1 + s2:
            self.idx, self.last_sector = 2, (s1 + s2 if self.cum else s2)
        elif self.idx == 2 and self.cur >= s1 + s2 + s3:
            total = s1 + s2 + s3
            self.count += 1
            self.cur -= total
            self.idx = 0
            self.lap_i += 1
            self.valid = True
            self.in_pit = False
            self.pending.append([self.delay, self.report(total)])
        for p in self.pending[:]:
            if p[0] <= 0:
                self.last_lap = p[1]
                self.pending.remove(p)
            else:
                p[0] -= 1


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.dm = temp_dm()
        self.rec = RecordStore(self.dm)
        self.ses = SessionStore(self.dm)
        self.tr = SessionTracker(self.rec, self.ses, {"ACC": "Assetto Corsa Competizione", "AC": "Assetto Corsa",
                                                       "LMU": "Le Mans Ultimate", "iRacing": "iRacing"})

    def run_sim(self, sim, seconds, hook=None):
        n = int(seconds / DT)
        for i in range(n):
            sim.step()
            if hook:
                hook(sim, i)
            self.tr.update(sim.frame(), sim.t)

    def record(self, game="ACC", track="spa", car="fer"):
        return self.rec.get(game, track, car)

    # ---- temel akis ----
    def test_clean_laps_are_recorded_with_sectors_and_best_kept(self):
        sim = Sim([(40000, 50000, 30500), (39000, 50500, 30000), (41000, 51000, 31000)])
        self.run_sim(sim, 125 + 121 + 125)
        snap = self.tr.snapshot()
        self.assertEqual(snap["laps_completed"], 3)
        self.assertEqual(snap["valid_laps"], 3)
        r = self.record()
        self.assertEqual((r["lap_ms"], r["s1_ms"], r["s2_ms"], r["s3_ms"]), (119500, 39000, 50500, 30000))
        self.assertTrue(r["verified"])
        self.assertEqual(snap["best_sectors_ms"], [39000, 50000, 30000])        # oturum en iyi sektorleri
        self.assertEqual(snap["theoretical_best_ms"], 119000)                    # 39000+50000+30000
        self.assertEqual(snap["avg_lap_ms"], round((120500 + 119500 + 123000) / 3))

    def test_cumulative_s2_semantics_detected(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], cumulative_s2=True)
        self.run_sim(sim, 125)
        r = self.record()
        self.assertEqual((r["s1_ms"], r["s2_ms"], r["s3_ms"]), (40000, 50000, 30500))

    def test_delayed_lap_time_update_still_correct(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], last_lap_delay=6)
        self.run_sim(sim, 123)
        self.assertEqual(self.record()["lap_ms"], 120500)

    def test_lap_time_never_updating_means_no_record(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        sim.delay = 10 ** 6
        self.run_sim(sim, 130)
        self.assertIsNone(self.record())
        self.assertEqual(self.tr.snapshot()["laps_completed"], 1)

    # ---- gecerlilik ----
    def test_game_invalid_lap_not_recorded_but_counted(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)])

        def hook(s, i):
            if 1000 < i < 1010:                # ilk tur ortasinda gecersiz
                s.valid = False
        self.run_sim(sim, 124, hook)
        self.assertEqual(self.tr.snapshot()["laps_completed"], 1)
        self.assertIsNone(self.record())
        self.assertIn("geçersiz", self.tr.snapshot()["last_event"])
        self.run_sim(sim, 121)                    # ikinci tur temiz
        self.assertEqual(self.record()["lap_ms"], 120400)

    def test_pit_lap_not_recorded(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)])
        sim.in_pit = True                          # pit cikis turu
        self.run_sim(sim, 5)
        sim.in_pit = False
        self.run_sim(sim, 120)
        self.assertIsNone(self.record())
        self.run_sim(sim, 121)
        self.assertEqual(self.record()["lap_ms"], 120400)

    def test_suspect_lap_not_recorded(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)], game="AC")
        sim.valid = None                           # AC: gecerlilik bilgisi yok
        sim.suspect = False

        def hook(s, i):
            s.suspect = 500 < i < 520
        self.run_sim(sim, 124, hook)
        self.assertIsNone(self.record("AC"))

    def test_mid_lap_attach_first_lap_skipped(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)], start_ms=60000)
        sim.idx = 1
        self.run_sim(sim, 65)                      # kalan sure: tur biter
        self.assertEqual(self.tr.snapshot()["laps_completed"], 1)
        self.assertIsNone(self.record())           # yarim tur kaydedilmedi
        self.run_sim(sim, 121)
        self.assertEqual(self.record()["lap_ms"], 120400)

    def test_no_validity_info_marks_unverified(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], game="AC")
        sim.valid = None
        self.run_sim(sim, 125)
        r = self.record("AC")
        self.assertEqual(r["lap_ms"], 120500)
        self.assertFalse(r["verified"])

    # ---- sektor guvenligi ----
    def test_sector_value_stale_is_not_accepted(self):
        # oyun sektor alanini guncellemiyor (hep eski deger): sektorler None, tur suresi yine dogru
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        orig = sim.step

        def step():
            orig()
            sim.last_sector = 123456
        sim.step = step
        self.run_sim(sim, 125)
        r = self.record()
        self.assertEqual(r["lap_ms"], 120500)
        self.assertEqual((r["s1_ms"], r["s2_ms"], r["s3_ms"]), (None, None, None))

    def test_no_sector_data_games_record_lap_only(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], game="iRacing", sectors=False, clock=True)
        sim.valid = None
        self.run_sim(sim, 125)
        r = self.record("iRacing")
        self.assertEqual((r["lap_ms"], r["s1_ms"]), (120500, None))

    # ---- oyun saati capraz dogrulama ----
    def test_game_clock_crosscheck_accepts_consistent_laps(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)], game="iRacing", sectors=False, clock=True)
        sim.valid = None
        self.run_sim(sim, 245)
        self.assertEqual(self.tr.snapshot()["valid_laps"], 2)

    def test_game_clock_mismatch_rejects_lap(self):
        # oyun 2. turda oyun saatiyle uyumsuz (95 sn) sure bildiriyor: kaydedilmemeli
        totals = iter([None, 95000, 95000])
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)], game="iRacing",
                  sectors=False, clock=True,
                  report=lambda total: (lambda x: total if x is None else x)(next(totals)))
        sim.valid = None
        self.run_sim(sim, 245)
        self.assertEqual(self.record("iRacing")["lap_ms"], 120500)             # sadece ilk (dogru) tur
        self.assertIn("doğrulanamadı", self.tr.snapshot()["last_event"])
        self.assertEqual(self.tr.snapshot()["valid_laps"], 1)

    def test_game_provided_sectors_lmu_style(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], game="LMU", sectors=False, clock=True)
        sim.valid = None
        orig = sim.frame

        def frame():
            f = orig()
            if sim.last_lap:
                f.last_lap_sectors = (40000, 50000, 30500)
            return f
        sim.frame = frame
        self.run_sim(sim, 125)
        r = self.record("LMU")
        self.assertEqual((r["lap_ms"], r["s1_ms"], r["s2_ms"], r["s3_ms"]), (120500, 40000, 50000, 30500))

    def test_game_provided_sectors_inconsistent_are_dropped(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], game="LMU", sectors=False, clock=True)
        sim.valid = None
        orig = sim.frame

        def frame():
            f = orig()
            if sim.last_lap:
                f.last_lap_sectors = (40000, 50000, 33333)     # toplam tur suresine uymuyor
            return f
        sim.frame = frame
        self.run_sim(sim, 125)
        r = self.record("LMU")
        self.assertEqual((r["lap_ms"], r["s1_ms"]), (120500, None))

    # ---- baglam ----
    def test_car_change_starts_new_session_and_keeps_records_separate(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 125)
        sim2 = Sim([(41000, 50000, 31000)] * 2, car="por")
        self.run_sim(sim2, 125)
        self.assertEqual(self.record(car="fer")["lap_ms"], 120500)
        self.assertEqual(self.record(car="por")["lap_ms"], 122000)
        snap = self.tr.snapshot()
        self.assertEqual(snap["car_name"], "Por")
        self.assertEqual(snap["laps_completed"], 1)                            # yeni oturum sifirdan
        sessions = self.ses.recent()
        self.assertEqual({s["car_id"] for s in sessions}, {"fer", "por"})      # eski oturum silinmedi

    def test_track_change_keeps_previous_track_records(self):
        self.run_sim(Sim([(40000, 50000, 30500), (40000, 50000, 30400)]), 125)
        self.run_sim(Sim([(30000, 40000, 20000)] * 2, track="monza"), 95)
        self.assertEqual(self.record(track="spa")["lap_ms"], 120500)
        self.assertEqual(self.record(track="monza")["lap_ms"], 90000)

    def test_sessions_persist_and_previous_session_is_found_next_time(self):
        self.run_sim(Sim([(40000, 50000, 30500), (40000, 50000, 30400)]), 125)
        self.tr.end()
        tr2 = SessionTracker(self.rec, SessionStore(self.dm), {"ACC": "ACC"})
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        sim.step()
        tr2.update(sim.frame(), sim.t)
        prev = tr2.snapshot()["prev_session"]
        self.assertIsNotNone(prev)
        self.assertEqual(prev["laps_completed"], 1)
        self.assertEqual(prev["best_lap_ms"], 120500)

    # ---- veri yokken ----
    def test_no_data_never_creates_records_or_crashes(self):
        for _ in range(100):
            self.tr.update(None)
        f = TelemetryFrame(game="ACC", live=True)         # pist/arac bilinmiyor
        self.tr.update(f)
        self.assertEqual(self.rec.all_records(), [])
        self.assertFalse(self.tr.snapshot()["has_session"])

    def test_not_live_frames_are_ignored(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        sim.live = False
        self.run_sim(sim, 125)
        self.assertIsNone(self.record())
        self.assertFalse(self.tr.snapshot()["has_session"])

    def test_lap_counter_reset_resyncs_without_false_record(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300), (40000, 50000, 30200)])
        self.run_sim(sim, 125)
        sim.count = 0                                # oyun oturumu yeniden basladi
        sim.cur = 1000
        sim.idx = 0
        self.run_sim(sim, 3)
        self.assertEqual(self.record()["lap_ms"], 120500)
        self.assertEqual(len(self.rec.all_records()), 1)

    # ---- tur olaylari: baslangic / tamamlanma / sifirlama ----
    def test_lap_counter_before_timer_reset_keeps_clock_check_working(self):
        # oyun tur sayacini artirir ama tur saati 4 kare daha eski degeri gosterir
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)], game="iRacing",
                  sectors=False, clock=True)
        sim.valid = None
        orig = sim.frame
        state = {"count": 0, "stale": 0, "val": 0}

        def frame():
            f = orig()
            if sim.count != state["count"]:
                state["count"], state["stale"], state["val"] = sim.count, 4, 120400
            if state["stale"] > 0:
                f.lap_current_ms = state["val"]
                state["stale"] -= 1
            return f
        sim.frame = frame
        self.run_sim(sim, 245)
        self.assertEqual(self.tr.snapshot()["valid_laps"], 2)
        self.assertEqual(self.record("iRacing")["lap_ms"], 120400)

    def test_timer_reset_before_lap_counter_still_a_normal_lap(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)], game="iRacing", sectors=False, clock=True)
        sim.valid = None
        orig = sim.frame
        seen = {"n": 0}

        def frame():
            f = orig()
            # tur saati bitisten 3 kare once sifirlanir, sayac sonra artar
            if sim.cur >= 120500 - 3 * 50 and sim.count == 0:
                f.lap_current_ms = sim.cur - 120500 + 3 * 50 + 10
                if f.lap_current_ms < 0:
                    f.lap_current_ms = 5
                seen["n"] += 1
            return f
        sim.frame = frame
        self.run_sim(sim, 125)
        self.assertEqual(self.tr.snapshot()["valid_laps"], 1)
        self.assertEqual(self.record("iRacing")["lap_ms"], 120500)

    def test_timer_rewind_without_count_resets_lap_and_does_not_carry_flags(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)])
        self.run_sim(sim, 30)
        sim.valid = False                           # tur gecersiz oldu
        self.run_sim(sim, 5)
        sim.cur = 0                                 # pite donus / tur yeniden baslatma: sayac ayni, saat basa dondu
        sim.idx = 0
        sim.valid = True
        self.run_sim(sim, 125)
        snap = self.tr.snapshot()
        self.assertEqual(snap["laps_completed"], 1)
        # yeniden baslatilan tam tur temiz sayilir: eski turun 'gecersiz' bayragi tasinmamali
        self.assertIsNotNone(self.record())
        self.assertNotIn("kaydedilmedi", snap["last_event"])

    def test_aborted_lap_never_recorded_when_counter_not_advancing(self):
        sim = Sim([(40000, 50000, 30500)] * 3)
        self.run_sim(sim, 60)
        sim.cur = 0
        sim.idx = 0
        self.run_sim(sim, 20)                      # tur ortasinda sifirlandi, tamamlanmadi
        self.assertEqual(self.tr.snapshot()["laps_completed"], 0)
        self.assertIsNone(self.record())
        self.assertIn("sıfırlandı", self.tr.snapshot()["last_event"])

    def test_counter_decrease_discards_pending_lap(self):
        sim = Sim([(40000, 50000, 30500)] * 4, last_lap_delay=10 ** 6)
        self.run_sim(sim, 122)                     # tur bitti, sure oyundan hic gelmedi (beklemede)
        sim.count = 0
        sim.cur = 500
        sim.idx = 0
        sim.last_lap = 120500                      # sifirlamadan sonra eski sure gorunur olsa bile
        self.run_sim(sim, 3)
        self.assertIsNone(self.record())

    def test_never_resetting_lap_timer_is_not_recorded(self):
        # tur sayaci/saati sonsuza kadar buyur: oyun tur bitirmiyor
        sim = Sim([(600000, 600000, 600000)])
        self.run_sim(sim, 1300)
        self.assertEqual(self.tr.snapshot()["laps_completed"], 0)
        self.assertIsNone(self.record())
        self.assertIn("sıfırlanmıyor", self.tr.snapshot()["last_event"])

    def test_overlong_lap_is_never_recorded_even_if_game_reports_it(self):
        sim = Sim([(600000, 600000, 600000), (40000, 50000, 30400)])
        self.run_sim(sim, 1805)
        self.assertEqual(self.tr.snapshot()["laps_completed"], 1)
        self.assertIsNone(self.record())

    def test_lap_time_not_matching_lap_timer_is_rejected(self):
        # oyun 2. turda 100 sn bildiriyor ama tur saati ~120 sn gosterdi (eski/yanlis deger tasinmis)
        totals = iter([None, 100000, 100000])
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)],
                  report=lambda total: (lambda x: total if x is None else x)(next(totals)))
        self.run_sim(sim, 245)
        self.assertEqual(self.record()["lap_ms"], 120500)
        self.assertEqual(self.tr.snapshot()["valid_laps"], 1)
        self.assertIn("tur saatiyle", self.tr.snapshot()["last_event"])

    def test_previous_lap_time_is_not_attached_to_new_lap(self):
        # 2. turun son-tur alani hic guncellenmiyor: 1. turun suresi 2. tura yazilmamali
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 122)
        self.assertEqual(self.record()["lap_ms"], 120500)
        sim.delay = 10 ** 6
        sim.pending = []
        self.run_sim(sim, 125)
        self.assertEqual(self.tr.snapshot()["valid_laps"], 1)
        self.assertEqual(self.record()["lap_ms"], 120500)

    def test_late_sector_indicator_after_lap_start_keeps_sectors(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400), (40000, 50000, 30300)])
        orig = sim.frame
        st = {"count": 0, "stale": 0}

        def frame():
            f = orig()
            if sim.count != st["count"]:
                st["count"], st["stale"] = sim.count, 3
            if st["stale"] > 0:
                f.sector_index = 2                 # sektor gostergesi geriden geliyor
                st["stale"] -= 1
            return f
        sim.frame = frame
        self.run_sim(sim, 245)
        r = self.record()
        self.assertEqual((r["lap_ms"], r["s1_ms"], r["s2_ms"], r["s3_ms"]), (120400, 40000, 50000, 30400))

    # ---- oturum yonetimi: baglanti kesilmesi != oturum bitmesi ----
    def _sim_with_state(self, laps, **kw):
        sim = Sim(laps, **kw)
        orig = sim.frame

        def frame():
            f = orig()
            f.fuel_l = 41.5
            f.tyre_temp_c = [80.0, 81.0, 82.0, 83.0]
            f.water_c = 90.0
            f.gear = 4
            return f
        sim.frame = frame
        return sim

    def test_game_close_keeps_all_session_data_on_screen(self):
        sim = self._sim_with_state([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 125)
        before = self.tr.snapshot()
        self.tr.end()                                   # oyun kapandi
        after = self.tr.snapshot()
        self.assertTrue(after["has_session"])
        self.assertTrue(after["ended"])
        self.assertFalse(after["live"])
        for k in ("car_name", "track_name", "laps_completed", "valid_laps", "best_lap_ms", "avg_lap_ms",
                  "best_sectors_ms", "max_speed_kmh", "avg_speed_kmh", "max_rpm", "lap_times_ms"):
            self.assertEqual(after[k], before[k], k)
        ls = after["last_state"]
        self.assertEqual((ls["fuel_l"], ls["tyre_temp_c"], ls["gear"], ls["speed_kmh"]), (41.5, [80.0, 81.0, 82.0, 83.0], 4, 150.0))
        self.assertEqual(self.record()["lap_ms"], 120500)          # rekor silinmedi

    def test_telemetry_cut_does_not_end_session_or_clear_state(self):
        sim = self._sim_with_state([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 125)
        sim.live = False
        self.run_sim(sim, 30)                           # veri kesildi (UDP / paylasimli bellek)
        snap = self.tr.snapshot()
        self.assertTrue(snap["has_session"])
        self.assertFalse(snap["ended"])
        self.assertFalse(snap["live"])
        self.assertEqual((snap["laps_completed"], snap["best_lap_ms"]), (1, 120500))
        self.assertEqual(snap["last_state"]["fuel_l"], 41.5)
        sim.live = True                                  # veri geri geldi: AYNI oturum surer
        self.run_sim(sim, 5)
        self.assertEqual(len(self.ses.recent()), 1)
        self.assertEqual(self.tr.snapshot()["laps_completed"], 1)

    def test_new_session_archives_old_and_starts_separate(self):
        sim = self._sim_with_state([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 125)
        self.tr.end()
        old_id = self.tr.sess["id"]
        sim2 = self._sim_with_state([(41000, 51000, 31000)] * 2)       # yeni oyun acildi, ayni arac/pist
        self.run_sim(sim2, 5)
        snap = self.tr.snapshot()
        self.assertFalse(snap["ended"])
        self.assertEqual((snap["laps_completed"], snap["best_lap_ms"]), (0, None))     # ayri veri alani
        self.assertNotEqual(self.tr.sess["id"], old_id)
        archived = {s["id"]: s for s in self.ses.recent()}
        self.assertIn(old_id, archived)                                                  # eski silinmedi
        self.assertEqual(archived[old_id]["best_lap_ms"], 120500)
        self.assertEqual(snap["prev_session"]["id"], old_id)

    def test_last_session_shown_after_app_restart_until_new_session(self):
        sim = self._sim_with_state([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 125)
        self.tr.end()
        tr2 = SessionTracker(self.rec, SessionStore(self.dm), {"ACC": "ACC"})      # uygulama yeniden acildi
        snap = tr2.snapshot()
        self.assertTrue(snap["has_session"])
        self.assertTrue(snap["ended"])
        self.assertEqual((snap["laps_completed"], snap["best_lap_ms"], snap["car_name"]), (1, 120500, "Fer"))
        self.assertEqual(snap["last_state"]["fuel_l"], 41.5)
        sim2 = self._sim_with_state([(41000, 51000, 31000)] * 2)                   # yeni oturum eskiyi degistirir
        sim2.step()
        tr2.update(sim2.frame(), sim2.t)
        self.assertFalse(tr2.snapshot()["ended"])

    def test_reset_all_clears_displayed_session(self):
        self.run_sim(self._sim_with_state([(40000, 50000, 30500)] * 2), 125)
        self.tr.end()
        self.tr.reset_all()
        snap = self.tr.snapshot()
        self.assertFalse(snap["has_session"])
        self.assertIsNone(snap["last_state"])

    # ---- istatistik tanimlari ----
    def test_stats_definitions(self):
        sim = Sim([(40000, 50000, 30500), (40000, 50000, 30400)])
        self.run_sim(sim, 30)
        s = self.tr.snapshot()
        self.assertAlmostEqual(s["avg_speed_kmh"], 150.0, places=1)       # hareket halindeyken zaman agirlikli
        self.assertAlmostEqual(s["throttle_avg_pct"], 80.0, places=1)     # oturum ortalamasi
        self.assertAlmostEqual(s["brake_avg_pct"], 0.0, places=1)
        self.assertEqual(s["max_rpm"], 7000)


if __name__ == "__main__":
    unittest.main()
