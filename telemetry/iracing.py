"""iRacing Oyun Bilgileri okuyucusu (resmi irsdk paylasimli bellegi).

Tur/sektor notu: iRacing paylasimli bellekte SEKTOR SURESI vermez; bu yuzden iRacing'de sektor
sureleri hesaplanmaz/uydurulmaz (None). Sadece tur sureleri takip edilir."""
import re
import struct

from core.models import four, ms_or_none, num, num_nz, pedal
from core.winmem import SharedMap
from telemetry.base import GameAdapter, derive_engine_running
from telemetry.naming import clean_text

NEEDED = ("Speed", "RPM", "Gear", "Throttle", "Brake", "BrakeABSactive", "FuelLevel", "WaterTemp",
          "OilTemp", "LapCompleted", "LapLastLapTime", "LapBestLapTime", "LapCurrentLapTime",
          "OnPitRoad", "IsOnTrack", "IsReplayPlaying", "SessionTime", "dcABS", "dcTractionControl",
          "LFtempL", "LFtempM", "LFtempR", "RFtempL", "RFtempM", "RFtempR",
          "LRtempL", "LRtempM", "LRtempR", "RRtempL", "RRtempM", "RRtempR",
          "LFpressure", "RFpressure", "LRpressure", "RRpressure")

_FMT = {0: "<b", 1: "<?", 2: "<i", 3: "<I", 4: "<f", 5: "<d"}


# ---------------- oturum bilgisi (YAML) ----------------
def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    return v.strip()


def _sections(text):
    """Ust duzey anahtarlara gore bolumler: {"WeekendInfo": "...", ...}"""
    out, key, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z]\w*):\s*$", line)
        if m:
            if key:
                out[key] = "\n".join(buf)
            key, buf = m.group(1), []
        elif key is not None:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf)
    return out


def _scalar(block, name):
    m = re.search(r"^[ \t-]*%s:[ \t]*(.*)$" % re.escape(name), block, re.M)
    return _unquote(m.group(1)) if m else None


def parse_session_yaml(text):
    """{'track_name','track_display','track_config','car_path','car_screen'} (yoksa None alanlar)."""
    res = {"track_name": None, "track_display": None, "track_config": None,
           "car_path": None, "car_screen": None}
    if not text:
        return res
    sec = _sections(text)
    wk = sec.get("WeekendInfo", "")
    res["track_name"] = _scalar(wk, "TrackName")
    res["track_display"] = _scalar(wk, "TrackDisplayName")
    cfg = _scalar(wk, "TrackConfigName")
    res["track_config"] = cfg if cfg and cfg.lower() not in ("null", "~", "n/a", "none") else None
    di = sec.get("DriverInfo", "")
    idx = _scalar(di, "DriverCarIdx")
    if idx is not None and idx.lstrip("-").isdigit():
        parts = re.split(r"^[ \t]*-[ \t]*CarIdx:[ \t]*", di, flags=re.M)
        # parts[0] = oncesi; sonrakiler "<idx>\n   ..." ile baslar
        for blk in parts[1:]:
            first = blk.split("\n", 1)[0].strip()
            if first == idx:
                res["car_path"] = _scalar(blk, "CarPath")
                res["car_screen"] = _scalar(blk, "CarScreenName")
                break
    return res


class IRacingAdapter(GameAdapter):
    ID = "iRacing"
    NAME = "iRacing"

    def __init__(self, mem=None):
        self.mem = mem or SharedMap("Local\\IRSDKMemMapFileName", 0)
        self.vars = None
        self.vars_key = None
        self.sess_update = None
        self.sess = None

    def close(self):
        self.mem.close()
        self.vars = None
        self.sess_update = None

    # --- bellek ---
    def _header(self):
        h = self.mem.read_at(0, 112)
        if h is None or len(h) < 112:
            return None
        (_ver, status, _tr, siu, sil, sio, nvars, voff, nbuf, blen) = struct.unpack_from("<10i", h, 0)
        bufs = [struct.unpack_from("<4i", h, 48 + 16 * i) for i in range(max(0, min(nbuf, 4)))]
        return {"status": status, "siu": siu, "sil": sil, "sio": sio, "nvars": nvars, "voff": voff,
                "nbuf": nbuf, "blen": blen, "bufs": bufs}

    def _parse_vars(self, nvars, voff):
        raw = self.mem.read_at(voff, nvars * 144)
        if raw is None or len(raw) < nvars * 144:
            return None
        out = {}
        for i in range(nvars):
            vtype, off, cnt = struct.unpack_from("<3i", raw, i * 144)
            name = raw[i * 144 + 16:i * 144 + 48].split(b"\0", 1)[0].decode("ascii", "ignore")
            if name in NEEDED and vtype in _FMT and cnt >= 1:
                out[name] = (vtype, off)
        return out

    def read(self):
        for _ in range(4):
            h = self._header()
            if h is None:
                return None
            f = self.new_frame(self.ID)
            if not (h["status"] & 1):
                f.state = "iRacing bağlı değil / simülasyon çalışmıyor"
                return f
            if not (1 <= h["nbuf"] <= 4 and 0 < h["nvars"] < 5000 and 0 < h["blen"] < 1_000_000):
                f.state = "Veri yapısı uyuşmuyor (okunan değerler güvenilmez)"
                return f
            tick, boff = max((b[0], b[1]) for b in h["bufs"])
            key = (h["nvars"], h["voff"])
            if self.vars is None or self.vars_key != key:
                self.vars = self._parse_vars(h["nvars"], h["voff"])
                self.vars_key = key
                if self.vars is None:
                    return None
            data = self.mem.read_at(boff, h["blen"])
            h2 = self._header()
            if data is None or h2 is None or len(data) < h["blen"]:
                return None
            if max(b[0] for b in h2["bufs"]) != tick:
                continue            # okuma sirasinda degisti: tekrar dene
            if h["siu"] != self.sess_update:
                raw = self.mem.read_at(h["sio"], h["sil"])
                if raw:
                    self.sess = parse_session_yaml(raw.split(b"\0", 1)[0].decode("cp1252", "replace"))
                    self.sess_update = h["siu"]
            return self.parse(tick, data)
        return None

    # --- cozumleme ---
    def _val(self, data, name):
        v = self.vars.get(name) if self.vars else None
        if not v:
            return None
        fmt = _FMT[v[0]]
        if v[1] + struct.calcsize(fmt) > len(data):
            return None
        return struct.unpack_from(fmt, data, v[1])[0]

    def parse(self, tick, data):
        val = lambda n: self._val(data, n)
        f = self.new_frame(self.ID)
        f.tick = tick
        sess = self.sess or {}
        trk, disp, cfg = clean_text(sess.get("track_name")), clean_text(sess.get("track_display")), sess.get("track_config")
        car, car_name = clean_text(sess.get("car_path")), clean_text(sess.get("car_screen"))
        if trk and disp and car and car_name:
            f.track_id = trk + ("|" + cfg if cfg else "")
            f.track_name = disp + (" - " + cfg if cfg else "")
            f.car_id, f.car_name = car, car_name

        on_track, replay = val("IsOnTrack"), val("IsReplayPlaying")
        if on_track is None:
            f.state = "Veri yapısı uyuşmuyor (okunan değerler güvenilmez)"
            return f
        if replay:
            f.state = "Tekrar (replay) izleniyor"
            return f
        if not on_track:
            f.state = "Garajda / pistte değil"
            return f
        f.state, f.live = "Canlı", True

        sp = num(val("Speed"), 0, 170)                 # m/s
        f.speed_kmh = None if sp is None else sp * 3.6
        f.rpm = num(val("RPM"), 0, 25000)
        f.throttle, f.brake = pedal(val("Throttle")), pedal(val("Brake"))
        g = val("Gear")
        f.gear = g if isinstance(g, int) and -1 <= g <= 12 else None
        ab = val("BrakeABSactive")
        f.abs_active = None if ab is None else (1.0 if ab else 0.0)
        # TC aktivitesi iRacing'de YOK -> None (tahmin edilmez)
        f.abs_level = num(val("dcABS"), 0, 30)
        f.tc_level = num(val("dcTractionControl"), 0, 30)
        f.fuel_l = num(val("FuelLevel"), 0, 500)
        f.water_c = num_nz(val("WaterTemp"), 1, 200)
        f.oil_c = num_nz(val("OilTemp"), 1, 250)

        pit = val("OnPitRoad")
        f.in_pit = None if pit is None else bool(pit)
        if pit:        # lastik sicaklik/basinci yalnizca pit yolunda guvenilir kabul edilir
            temps = []
            for c in ("LF", "RF", "LR", "RR"):
                parts = [num_nz(val("%stemp%s" % (c, s)), -50, 400) for s in "LMR"]
                temps.append(sum(parts) / 3 if all(p is not None for p in parts) else None)
            f.tyre_temp_c = temps if any(t is not None for t in temps) else None
            f.tyre_press_kpa = four([val("%spressure" % c) for c in ("LF", "RF", "LR", "RR")], 30, 700)

        lc = val("LapCompleted")
        if isinstance(lc, int) and 0 <= lc <= 9999:
            f.lap_count = lc
            cur = val("LapCurrentLapTime")
            f.lap_current_ms = ms_or_none(round(cur * 1000), 0) if cur is not None and cur >= 0 else None
            last = val("LapLastLapTime")
            f.lap_last_ms = ms_or_none(round(last * 1000)) if last is not None and last > 0 else None
            best = val("LapBestLapTime")
            f.lap_best_ms = ms_or_none(round(best * 1000)) if best is not None and best > 0 else None
            f.clock_s = num(val("SessionTime"), 0, 1e7)
        derive_engine_running(f)
        return f
