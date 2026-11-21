"""Le Mans Ultimate Oyun Bilgileri okuyucusu (rFactor 2 paylasimli bellek eklentisi yapisi).

DENEYSEL: Yapilar bu ortamda oyunla test edilemedi. Guvenlik icin:
 * Yapi boyutlari bilinen degerlerle (telemetri 1888, tekerlek 260, skor 548, arac skoru 584 bayt)
   birebir tutmuyorsa adaptor hic veri vermez.
 * Tur suresi iki BAGIMSIZ kaynaktan (skor tablosu ve telemetrideki tur baslangic zamani) dogrulanir;
   uyusmazsa tur/sektor verilmez.
 * ABS/TC bu yapida yok -> None (kayma oranindan tahmin EDILMEZ).
LMU'da eklenti (rFactor2SharedMemoryMapPlugin) etkin degilse veri yoktur."""
import ctypes

from core.models import compound_is_wet, four, num, num_nz, pedal
from core.winmem import SharedMap
from telemetry.base import GameAdapter, derive_engine_running
from telemetry.legacy_sources import RF2Vehicle, RF2Wheel
from telemetry.naming import clean_text

D = ctypes.c_double
I = ctypes.c_int
U8 = ctypes.c_ubyte
VEC3 = D * 3


class RF2ScoringInfo(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("mTrackName", ctypes.c_char * 64), ("mSession", I), ("mCurrentET", D), ("mEndET", D),
        ("mMaxLaps", I), ("mLapDist", D), ("pointer1", U8 * 8), ("mNumVehicles", I),
        ("mGamePhase", U8), ("mYellowFlagState", ctypes.c_byte), ("mSectorFlag", ctypes.c_byte * 3),
        ("mStartLight", U8), ("mNumRedLights", U8), ("mInRealtime", ctypes.c_bool),
        ("mPlayerName", ctypes.c_char * 32), ("mPlrFileName", ctypes.c_char * 64),
        ("mDarkCloud", D), ("mRaining", D), ("mAmbientTemp", D), ("mTrackTemp", D), ("mWind", VEC3),
        ("mMinPathWetness", D), ("mMaxPathWetness", D), ("mGameMode", U8),
        ("mIsPasswordProtected", ctypes.c_bool), ("mServerPort", ctypes.c_uint16),
        ("mServerPublicIP", ctypes.c_uint32), ("mMaxPlayers", I), ("mServerName", ctypes.c_char * 32),
        ("mStartET", ctypes.c_float), ("mAvgPathWetness", D), ("mExpansion", U8 * 200),
        ("pointer2", U8 * 8),
    ]


class RF2VehicleScoring(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("mID", I), ("mDriverName", ctypes.c_char * 32), ("mVehicleName", ctypes.c_char * 64),
        ("mTotalLaps", ctypes.c_int16), ("mSector", ctypes.c_byte), ("mFinishStatus", ctypes.c_byte),
        ("mLapDist", D), ("mPathLateral", D), ("mTrackEdge", D),
        ("mBestSector1", D), ("mBestSector2", D), ("mBestLapTime", D),
        ("mLastSector1", D), ("mLastSector2", D), ("mLastLapTime", D),
        ("mCurSector1", D), ("mCurSector2", D),
        ("mNumPitstops", ctypes.c_int16), ("mNumPenalties", ctypes.c_int16),
        ("mIsPlayer", ctypes.c_bool), ("mControl", ctypes.c_byte), ("mInPits", ctypes.c_bool),
        ("mPlace", U8), ("mVehicleClass", ctypes.c_char * 32),
        ("mTimeBehindNext", D), ("mLapsBehindNext", I), ("mTimeBehindLeader", D),
        ("mLapsBehindLeader", I), ("mLapStartET", D),
        ("mPos", VEC3), ("mLocalVel", VEC3), ("mLocalAccel", VEC3), ("mOri", VEC3 * 3),
        ("mLocalRot", VEC3), ("mLocalRotAccel", VEC3),
        ("mHeadlights", U8), ("mPitState", U8), ("mServerScored", U8), ("mIndividualPhase", U8),
        ("mQualification", I), ("mTimeIntoLap", D), ("mEstimatedLapTime", D),
        ("mPitGroup", ctypes.c_char * 24), ("mFlag", U8), ("mUnderYellow", ctypes.c_bool),
        ("mCountLapFlag", U8), ("mInGarageStall", ctypes.c_bool), ("mUpgradePack", U8 * 16),
        ("mPitLapDist", ctypes.c_float), ("mBestLapSector1", ctypes.c_float),
        ("mBestLapSector2", ctypes.c_float), ("mExpansion", U8 * 48),
    ]


SCORING_HDR = 12          # surum sayaclari (2x uint32) + mBytesUpdatedHint
TELEM_HDR = 16
STRUCTS_OK = (ctypes.sizeof(RF2Vehicle) == 1888 and ctypes.sizeof(RF2Wheel) == 260
              and ctypes.sizeof(RF2ScoringInfo) == 548 and ctypes.sizeof(RF2VehicleScoring) == 584)

LAP_TOLERANCE_S = 0.06


def _txt(b):
    try:
        return b.split(b"\0", 1)[0].decode("utf-8", "replace")
    except Exception:
        return ""


def _normalize_car(name):
    """Yaris numarasini/sinif ekini atar ('Team #12:HY' -> 'Team'). Sadece bicimlendirme."""
    import re
    n = name.split(":", 1)[0]
    n = re.sub(r"#\s*\d+", "", n)
    return re.sub(r"\s+", " ", n).strip()


class LMUAdapter(GameAdapter):
    ID = "LMU"
    NAME = "Le Mans Ultimate"

    def __init__(self, tel_mem=None, sco_mem=None):
        self.m_tel = tel_mem or SharedMap("$rFactor2SMMP_Telemetry$", 0)
        self.m_sco = sco_mem or SharedMap("$rFactor2SMMP_Scoring$", 0)
        self.starts = []         # oyuncunun mLapStartET degerleri (ayri olanlar)
        self.last_id = None

    def close(self):
        self.m_tel.close()
        self.m_sco.close()

    # --- bellek ---
    def _read_buffer(self, mem, hdr_size, item_size, max_items, count_getter, tries=4):
        """Surum sayaci ile tutarli okuma. (baslik_bytes, item_bytes, count) veya None."""
        for _ in range(tries):
            h = mem.read_at(0, hdr_size + 8)
            if h is None or len(h) < hdr_size:
                return None
            b0 = int.from_bytes(h[0:4], "little")
            e0 = int.from_bytes(h[4:8], "little")
            if b0 != e0:
                continue
            cnt = count_getter(mem)
            if cnt is None:
                return None
            cnt = max(0, min(cnt, max_items))
            body = mem.read_at(hdr_size, cnt * item_size) if cnt else b""
            h2 = mem.read_at(0, 8)
            if body is None or h2 is None:
                return None
            if int.from_bytes(h2[0:4], "little") == b0 and int.from_bytes(h2[4:8], "little") == e0:
                return h, body, cnt
        return None

    def read(self):
        if not STRUCTS_OK:
            f = self.new_frame(self.ID)
            f.state = "Veri yapısı doğrulanamadı: LMU okuması kapalı"
            return f
        tel = self._read_buffer(self.m_tel, TELEM_HDR, ctypes.sizeof(RF2Vehicle), 128,
                                lambda m: int.from_bytes(m.read_at(12, 4) or b"\0\0\0\0", "little", signed=True))
        if tel is None:
            return None
        sco = self._read_scoring()
        return self.parse(tel, sco)

    def _read_scoring(self):
        try:
            h = self.m_sco.read_at(0, SCORING_HDR + ctypes.sizeof(RF2ScoringInfo))
            if h is None or len(h) < SCORING_HDR + ctypes.sizeof(RF2ScoringInfo):
                return None
            info = RF2ScoringInfo.from_buffer_copy(h, SCORING_HDR)
            n = info.mNumVehicles
            if not 1 <= n <= 128:
                return None
            body = self.m_sco.read_at(SCORING_HDR + ctypes.sizeof(RF2ScoringInfo),
                                      n * ctypes.sizeof(RF2VehicleScoring))
            h2 = self.m_sco.read_at(0, 8)
            if body is None or h2 is None or h2[0:4] != h2[4:8] or h[0:4] != h2[0:4]:
                return None
            return info, body, n
        except Exception:
            return None

    # --- cozumleme ---
    def parse(self, tel, sco):
        _hdr, body, cnt = tel
        f = self.new_frame(self.ID)
        vehs = [RF2Vehicle.from_buffer_copy(body, i * ctypes.sizeof(RF2Vehicle)) for i in range(cnt)]
        if not vehs:
            f.state = "Oyuncu aracı yok (garaj/menü)"
            return f

        player_v = player_s = None
        info = None
        if sco is not None:
            info, sbody, n = sco
            for i in range(n):
                s = RF2VehicleScoring.from_buffer_copy(sbody, i * ctypes.sizeof(RF2VehicleScoring))
                if s.mIsPlayer:
                    player_s = s
                    break
            if player_s is not None:
                for v in vehs:
                    if v.mID == player_s.mID:
                        player_v = v
                        break
        if player_v is None:
            if sco is None and len(vehs) == 1:
                player_v = vehs[0]       # tek arac: oyuncu o
                f.notes.append("Skor tablosu okunamadı: tur bilgisi yok")
            else:
                f.state = "Oyuncu aracı doğrulanamadı"
                return f
        v = player_v
        f.tick = v.mElapsedTime
        f.clock_s = num(v.mElapsedTime, 0, 1e7)
        scoring_ok = player_s is not None and info is not None
        f.live = bool(info.mInRealtime) if scoring_ok else True
        f.state = "Canlı" if f.live else "Garajda / pistte değil"

        trk = clean_text(_txt(v.mTrackName), 64)
        car = clean_text(_normalize_car(_txt(v.mVehicleName)), 64)
        if trk and car:
            f.track_id, f.track_name, f.car_id, f.car_name = trk, trk, car, car
        if not f.live:
            return f

        ms = (v.mLocalVel[0] ** 2 + v.mLocalVel[1] ** 2 + v.mLocalVel[2] ** 2) ** 0.5
        sp = num(ms, 0, 170)
        f.speed_kmh = None if sp is None else sp * 3.6
        f.rpm = num(v.mEngineRPM, 0, 25000)
        f.throttle, f.brake = pedal(v.mUnfilteredThrottle), pedal(v.mUnfilteredBrake)
        f.gear = v.mGear if -1 <= v.mGear <= 12 else None
        f.fuel_l = num(v.mFuel, 0, 500)
        f.water_c = num_nz(v.mEngineWaterTemp, 1, 200)
        f.oil_c = num_nz(v.mEngineOilTemp, 1, 250)
        # ABS/TC: bu yapida YOK -> None (kayma oranindan tahmin edilmez)
        temps, press = [], []
        for w in v.mWheels:
            ks = [num_nz(x, 250, 450) for x in w.mTemperature]            # Kelvin
            temps.append(sum(ks) / 3 - 273.15 if all(k is not None for k in ks) else None)
            press.append(w.mPressure)
        f.tyre_temp_c = temps if any(t is not None for t in temps) else None
        f.tyre_press_kpa = four(press, 30, 700)
        f.tyre_wet = compound_is_wet(_txt(bytes(v.mFrontTireCompoundName)))   # oyunun on lastik bilesigi adi

        if scoring_ok:
            self._laps(f, v, player_s)
        derive_engine_running(f)
        return f

    def _laps(self, f, v, s):
        # oyuncunun tur baslangic zamanlarini izle (bagimsiz dogrulama icin)
        if v.mID != self.last_id:
            self.starts, self.last_id = [], v.mID
        st = v.mLapStartET
        if self.starts and 0 <= st < self.starts[-1]:
            self.starts = []                    # oyun saati geri gitti (yeni oturum): eski tur baslangiclari tasinmasin
        if st >= 0 and (not self.starts or self.starts[-1] != st):
            self.starts = (self.starts + [st])[-3:]
        if 0 <= s.mTotalLaps <= 9999:
            f.lap_count = int(s.mTotalLaps)
        else:
            return
        cur = v.mElapsedTime - v.mLapStartET
        if 0 <= cur < 3600:
            f.lap_current_ms = int(round(cur * 1000))
        f.in_pit = bool(s.mInPits)
        f.lap_best_ms = int(round(s.mBestLapTime * 1000)) if 5 < s.mBestLapTime < 3600 else None

        last = s.mLastLapTime
        if len(self.starts) >= 2 and 5 < last < 3600:
            derived = self.starts[-1] - self.starts[-2]
            if abs(derived - last) <= LAP_TOLERANCE_S:          # iki kaynak uyusuyor
                f.lap_last_ms = int(round(last * 1000))
                s1, c2 = s.mLastSector1, s.mLastSector2            # c2 = S1+S2 (kumulatif)
                if 3 < s1 < last and s1 < c2 < last:
                    a, b, c = int(round(s1 * 1000)), int(round((c2 - s1) * 1000)), int(round((last - c2) * 1000))
                    if min(a, b, c) > 0:
                        f.last_lap_sectors = (a, b, c)
