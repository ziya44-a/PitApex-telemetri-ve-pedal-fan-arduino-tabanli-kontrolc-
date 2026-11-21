"""Kalici rekorlar: Oyun -> Pist -> Arac modeli. Yalnizca DAHA IYI tur yazilir."""
import threading
import time

from storage.atomic import atomic_write_json, read_json

MIN_LAP_MS = 5_000
MAX_LAP_MS = 1_200_000          # 20 dk: bundan uzun "tur" gercek tur degil (sayac sifirlanmamis)


def _valid_structure(d):
    return isinstance(d, dict) and isinstance(d.get("games"), dict)


def _clean_sectors(lap_ms, sectors):
    """Sektorler ancak hepsi pozitifse ve toplami tur suresine (+-2 ms) uyuyorsa saklanir.
    Aksi halde None: yanlis sektor saklamaktansa bos birak."""
    if not sectors or len(sectors) != 3:
        return (None, None, None)
    try:
        s = [int(x) for x in sectors]
    except (TypeError, ValueError):
        return (None, None, None)
    if any(x <= 0 for x in s) or abs(sum(s) - lap_ms) > 2:
        return (None, None, None)
    return tuple(s)


class RecordStore:
    def __init__(self, dm):
        self.dm = dm
        self.path = dm.path("records", "lap_records.json")
        self.lock = threading.RLock()
        self.version = 0
        self.status = "ok"
        self.data = {"version": 1, "games": {}}
        self.load()

    def load(self):
        with self.lock:
            data, self.status = read_json(self.path, self.dm.backup_dir, None, _valid_structure)
            self.data = data if data is not None else {"version": 1, "games": {}}
            self.version += 1

    def reset(self):
        with self.lock:
            self.data = {"version": 1, "games": {}}
            self.version += 1

    def _save(self):
        atomic_write_json(self.path, self.data, self.dm.backup_dir)

    @staticmethod
    def _id(x):
        return (x or "").strip()

    def get(self, game_id, track_id, car_id):
        with self.lock:
            try:
                rec = self.data["games"][game_id]["tracks"][track_id]["cars"][car_id]
            except KeyError:
                return None
            return dict(rec)

    def submit(self, game_id, game_name, track_id, track_name, car_id, car_name,
               lap_ms, sectors=None, verified=False, when=None):
        """Donus: 'rejected' | 'first' | 'improved' | 'not_better'."""
        game_id, track_id, car_id = self._id(game_id), self._id(track_id), self._id(car_id)
        if not (game_id and track_id and car_id):
            return "rejected"           # anahtar eksikse kaydetme (karismasin)
        try:
            lap_ms = int(lap_ms)
        except (TypeError, ValueError):
            return "rejected"
        if not (MIN_LAP_MS <= lap_ms <= MAX_LAP_MS):
            return "rejected"
        s1, s2, s3 = _clean_sectors(lap_ms, sectors)
        with self.lock:
            g = self.data["games"].setdefault(game_id, {"name": game_name or game_id, "tracks": {}})
            g["name"] = game_name or g.get("name") or game_id
            t = g["tracks"].setdefault(track_id, {"name": track_name or track_id, "cars": {}})
            cars = t["cars"]
            old = cars.get(car_id)
            if old is not None and old.get("lap_ms") is not None and lap_ms >= old["lap_ms"]:
                return "not_better"
            status = "first" if old is None else "improved"
            t["name"] = track_name or t.get("name") or track_id
            new_record = {
                "name": car_name or car_id,
                "lap_ms": lap_ms, "s1_ms": s1, "s2_ms": s2, "s3_ms": s3,
                "date": when or time.strftime("%Y-%m-%d %H:%M:%S"),
                "verified": bool(verified),
            }
            cars[car_id] = new_record
            try:
                self._save()
            except OSError:
                if old is None:
                    del cars[car_id]
                else:
                    cars[car_id] = old
                self.status = "write_error"
                return "write_error"
            self.status = "ok"
            self.version += 1
            return status

    def all_records(self):
        """[(oyun_adi, pist_adi, arac_adi, kayit_dict)] oyun/pist/arac sirali."""
        out = []
        with self.lock:
            for gid, g in self.data["games"].items():
                for tid, t in g.get("tracks", {}).items():
                    for cid, rec in t.get("cars", {}).items():
                        out.append((g.get("name", gid), t.get("name", tid), rec.get("name", cid), dict(rec)))
        out.sort(key=lambda r: (r[0].lower(), r[1].lower(), r[2].lower()))
        return out
