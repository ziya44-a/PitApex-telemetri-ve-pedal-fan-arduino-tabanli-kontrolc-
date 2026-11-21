import json
import os
import unittest

from tests.helpers import temp_dm
from storage import atomic
from storage.data_manager import DataManager, SUBDIRS
from storage.records import RecordStore
from storage.sessions import SessionStore
from storage.settings import Preferences, Profiles


class AtomicTests(unittest.TestCase):
    def test_write_read_roundtrip_and_no_tmp_left(self):
        dm = temp_dm()
        p = dm.path("settings", "x.json")
        atomic.atomic_write_json(p, {"a": 1, "tr": "şğüİ"}, dm.backup_dir)
        data, st = atomic.read_json(p, dm.backup_dir)
        self.assertEqual((data, st), ({"a": 1, "tr": "şğüİ"}, "ok"))
        self.assertFalse([f for f in os.listdir(dm.path("settings")) if f.endswith(".tmp")])

    def test_second_write_makes_backup_and_corrupt_file_is_restored(self):
        dm = temp_dm()
        p = dm.path("settings", "x.json")
        atomic.atomic_write_json(p, {"v": 1}, dm.backup_dir)
        atomic.atomic_write_json(p, {"v": 2}, dm.backup_dir)      # onceki surum yedeklenir
        self.assertTrue(os.listdir(dm.backup_dir))
        with open(p, "w") as f:
            f.write("{bozuk json")                                  # yarim kalmis dosya
        data, st = atomic.read_json(p, dm.backup_dir, default=None)
        self.assertEqual(st, "restored")
        self.assertEqual(data, {"v": 1})
        self.assertTrue([f for f in os.listdir(dm.path("settings")) if ".corrupt-" in f])  # bozuk dosya silinmedi

    def test_corrupt_without_backup_returns_default(self):
        dm = temp_dm()
        p = dm.path("settings", "y.json")
        with open(p, "w") as f:
            f.write("???")
        data, st = atomic.read_json(p, dm.backup_dir, default={"d": 1})
        self.assertEqual((data, st), ({"d": 1}, "reset"))

    def test_failed_write_keeps_old_file(self):
        dm = temp_dm()
        p = dm.path("settings", "z.json")
        atomic.atomic_write_json(p, {"ok": True}, dm.backup_dir)
        with self.assertRaises(TypeError):
            atomic.atomic_write_json(p, {"bad": object()}, dm.backup_dir)
        self.assertEqual(json.load(open(p, encoding="utf-8")), {"ok": True})


class DataManagerTests(unittest.TestCase):
    def test_structure_created(self):
        dm = temp_dm()
        for s in SUBDIRS:
            self.assertTrue(os.path.isdir(dm.path(s)))

    def test_migration_copies_once_and_does_not_delete(self):
        dm = temp_dm()
        legacy = os.path.join(os.path.dirname(dm.root), "legacy")
        os.makedirs(os.path.join(legacy, "profiller"))
        json.dump({"abs": {}}, open(os.path.join(legacy, "ayarlar.json"), "w"))
        json.dump({"x": 1}, open(os.path.join(legacy, "profiller", "GT3.json"), "w"))
        done = dm.migrate_legacy(legacy)
        self.assertIn("ayarlar.json", done)
        self.assertTrue(os.path.exists(dm.path("settings", "pedal_settings.json")))
        self.assertTrue(os.path.exists(dm.path("profiles", "GT3.json")))
        self.assertTrue(os.path.exists(os.path.join(legacy, "ayarlar.json")))   # eski dosya duruyor
        self.assertEqual(dm.migrate_legacy(legacy), [])                        # ikinci kez yapmaz

    def test_wipe_removes_user_data_but_not_outside_and_not_reimported(self):
        dm = temp_dm()
        legacy = os.path.join(os.path.dirname(dm.root), "legacy")
        os.makedirs(legacy)
        json.dump({"a": 1}, open(os.path.join(legacy, "ayarlar.json"), "w"))
        outside = os.path.join(os.path.dirname(dm.root), "baska_dosya.txt")
        open(outside, "w").write("dokunma")
        rs = RecordStore(dm)
        rs.submit("ACC", "ACC", "spa", "Spa", "car", "Car", 140000, None)
        SessionStore(dm).upsert({"id": "s1", "laps_completed": 3})
        Preferences(dm).set("theme", "light")
        removed, errors = dm.wipe_user_data()
        self.assertGreater(removed, 0)
        self.assertEqual(errors, [])
        for s in SUBDIRS:
            self.assertTrue(os.path.isdir(dm.path(s)))
            self.assertEqual(os.listdir(dm.path(s)), [])
        self.assertTrue(os.path.exists(outside))                     # klasor disina dokunulmadi
        self.assertEqual(dm.migrate_legacy(legacy), [])              # eski ayarlar geri gelmez
        # temiz veriyle normal calisir
        rs2 = RecordStore(dm)
        self.assertEqual(rs2.all_records(), [])
        self.assertEqual(Preferences(dm).get("theme"), "dark")

    def test_wipe_refuses_unmarked_folder(self):
        dm = temp_dm()
        os.remove(dm.marker_path)
        with self.assertRaises(RuntimeError):
            dm.wipe_user_data()


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.dm = temp_dm()
        self.rs = RecordStore(self.dm)

    def sub(self, car="fer", lap=141222, sec=(40000, 60000, 41222), track="spa", game="ACC"):
        return self.rs.submit(game, game, track, track.title(), car, car.title(), lap, sec, True)

    def test_first_improved_and_worse(self):
        self.assertEqual(self.sub(), "first")
        self.assertEqual(self.sub(lap=142000, sec=(40000, 60000, 42000)), "not_better")
        self.assertEqual(self.rs.get("ACC", "spa", "fer")["lap_ms"], 141222)    # eski rekor korundu
        self.assertEqual(self.sub(lap=140500, sec=(39500, 60000, 41000)), "improved")
        self.assertEqual(self.rs.get("ACC", "spa", "fer")["s1_ms"], 39500)

    def test_equal_time_does_not_overwrite(self):
        self.sub()
        self.assertEqual(self.sub(), "not_better")

    def test_cars_tracks_games_never_mix(self):
        self.sub(car="fer", lap=141000, sec=None)
        self.sub(car="por", lap=142000, sec=None)
        self.sub(car="fer", lap=100000, track="monza", sec=None)
        self.sub(car="fer", lap=120000, game="AC", sec=None)
        self.assertEqual(self.rs.get("ACC", "spa", "fer")["lap_ms"], 141000)
        self.assertEqual(self.rs.get("ACC", "spa", "por")["lap_ms"], 142000)
        self.assertEqual(self.rs.get("ACC", "monza", "fer")["lap_ms"], 100000)
        self.assertEqual(self.rs.get("AC", "spa", "fer")["lap_ms"], 120000)
        self.assertEqual(len(self.rs.all_records()), 4)

    def test_inconsistent_sectors_are_dropped_not_guessed(self):
        self.sub(sec=(40000, 60000, 99999))            # toplam tur suresine uymuyor
        r = self.rs.get("ACC", "spa", "fer")
        self.assertEqual((r["s1_ms"], r["s2_ms"], r["s3_ms"]), (None, None, None))
        self.assertEqual(r["lap_ms"], 141222)

    def test_better_lap_without_sectors_does_not_inherit_old_sectors(self):
        self.sub()
        self.sub(lap=140000, sec=None)
        r = self.rs.get("ACC", "spa", "fer")
        self.assertEqual((r["lap_ms"], r["s1_ms"]), (140000, None))

    def test_rejects_missing_keys_and_absurd_times(self):
        self.assertEqual(self.rs.submit("ACC", "ACC", "", "x", "c", "c", 100000), "rejected")
        self.assertEqual(self.rs.submit("ACC", "ACC", "t", "t", "", "", 100000), "rejected")
        self.assertEqual(self.rs.submit("ACC", "ACC", "t", "t", "c", "c", 100), "rejected")
        self.assertEqual(self.rs.submit("ACC", "ACC", "t", "t", "c", "c", 99999999), "rejected")
        self.assertEqual(self.rs.all_records(), [])

    def test_persistence_across_restart(self):
        self.sub()
        rs2 = RecordStore(self.dm)
        self.assertEqual(rs2.get("ACC", "spa", "fer")["lap_ms"], 141222)
        self.assertEqual(rs2.get("ACC", "spa", "fer")["verified"], True)

    def test_corrupt_records_file_recovers_from_backup(self):
        self.sub()
        self.sub(lap=140000, sec=None)                   # ikinci yazim: oncekinin yedegi alinir
        with open(self.rs.path, "w") as f:
            f.write("bozuk")
        rs2 = RecordStore(self.dm)
        self.assertEqual(rs2.status, "restored")
        self.assertEqual(rs2.get("ACC", "spa", "fer")["lap_ms"], 141222)


class PrefTests(unittest.TestCase):
    def test_theme_persists_and_defaults_merge(self):
        dm = temp_dm()
        p = Preferences(dm)
        self.assertEqual(p.get("theme"), "dark")
        p.set("theme", "light")
        self.assertEqual(Preferences(dm).get("theme"), "light")
        self.assertIn("idle_pct", Preferences(dm).get("fan")["fans"][0])

    def test_profiles_safe_name_and_roundtrip(self):
        dm = temp_dm()
        pr = Profiles(dm)
        name = pr.save("GT3/../x", {"a": 1})
        self.assertNotIn("/", name)
        self.assertEqual(pr.load(name), {"a": 1})
        self.assertIn(name, pr.names())


if __name__ == "__main__":
    unittest.main()
