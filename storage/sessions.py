"""Oturum istatistikleri (kalici). Her oturum (oyun+pist+arac) tek kayittir; ayni id ile guncellenir."""
import threading

from storage.atomic import atomic_write_json, read_json

MAX_SESSIONS = 500


def _valid(d):
    return isinstance(d, dict) and isinstance(d.get("sessions"), list)


class SessionStore:
    def __init__(self, dm):
        self.dm = dm
        self.path = dm.path("sessions", "session_data.json")
        self.lock = threading.RLock()
        self.version = 0
        self.status = "ok"
        self.data = {"version": 1, "sessions": []}
        self.load()

    def load(self):
        with self.lock:
            data, self.status = read_json(self.path, self.dm.backup_dir, None, _valid)
            self.data = data if data is not None else {"version": 1, "sessions": []}
            self.version += 1

    def reset(self):
        with self.lock:
            self.data = {"version": 1, "sessions": []}
            self.version += 1

    def upsert(self, session):
        sid = session.get("id")
        if not sid:
            return
        with self.lock:
            lst = self.data["sessions"]
            for i, s in enumerate(lst):
                if s.get("id") == sid:
                    lst[i] = session
                    break
            else:
                lst.append(session)
            if len(lst) > MAX_SESSIONS:
                lst.sort(key=lambda s: s.get("started", ""))
                del lst[:len(lst) - MAX_SESSIONS]
            self.version += 1
            try:
                atomic_write_json(self.path, self.data, self.dm.backup_dir)
            except OSError:
                self.status = "write_error"

    def latest_for(self, game_id, track_id, car_id, exclude_id=None):
        with self.lock:
            best = None
            for s in self.data["sessions"]:
                if (s.get("game_id") == game_id and s.get("track_id") == track_id
                        and s.get("car_id") == car_id and s.get("id") != exclude_id):
                    if best is None or s.get("started", "") > best.get("started", ""):
                        best = s
            return dict(best) if best else None

    def recent(self, n=20):
        with self.lock:
            lst = sorted(self.data["sessions"], key=lambda s: s.get("started", ""), reverse=True)
            return [dict(s) for s in lst[:n]]
