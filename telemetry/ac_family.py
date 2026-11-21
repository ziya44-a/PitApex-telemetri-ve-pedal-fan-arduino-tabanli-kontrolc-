"""Assetto Corsa Competizione ve Assetto Corsa icin Oyun Bilgileri okuyuculari.

Her iki oyun da Local\\acpmf_physics / _graphics / _static bellek sayfalarini kullanir. Hangisinin
acik oldugu BELLEKTEN anlasilamaz; program adindan (acs.exe / ac2-win64-shipping.exe) anlasilir.
Bu nedenle iki ayri sinif vardir ve hangisinin calisacagina GameDetector karar verir.

Sayfa yapilari resmi paylasimli bellek belgelerine gore yazildi, ANCAK bu ortamda oyunla test
edilemedi. Bu yuzden her alan mantik araligiyla dogrulanir; uyusmayan alan None (Veri alinamiyor) olur."""
import ctypes
import time

from core.models import (compound_is_wet, four, ms_or_none, num, num_nz, pedal)
from core.winmem import SharedMap
from telemetry.base import GameAdapter, derive_engine_running, pad
from telemetry.legacy_sources import Physics
from telemetry.naming import ACC_TRACKS, clean_text, pretty_id

F = ctypes.c_float
I = ctypes.c_int
W = ctypes.c_uint16        # wchar_t (Windows'ta 2 bayt) - platformdan bagimsiz test icin
PSI_TO_KPA = 6.894757


def wstr(arr):
    out = []
    for c in arr:
        if c == 0:
            break
        out.append(chr(c))
    return "".join(out)


class PhysicsACC(Physics):
    """Physics + ACC'nin devami (su sicakligi, motor durumu)."""
    _pack_ = 4
    _fields_ = [
        ("tcinAction", F), ("absInAction", F), ("suspensionDamage", F * 4), ("tyreTemp", F * 4),
        ("waterTemp", F), ("brakePressure", F * 4), ("frontBrakeCompound", I), ("rearBrakeCompound", I),
        ("padLife", F * 4), ("discLife", F * 4), ("ignitionOn", I), ("starterEngineOn", I),
        ("isEngineRunning", I),
    ]


class GraphicsAC(ctypes.Structure):
    """AC graphics sayfasi (ortak on kisim; normalizedCarPosition'a kadar)."""
    _pack_ = 4
    _fields_ = [
        ("packetId", I), ("status", I), ("session", I),
        ("currentTime", W * 15), ("lastTime", W * 15), ("bestTime", W * 15), ("split", W * 15),
        ("completedLaps", I), ("position", I), ("iCurrentTime", I), ("iLastTime", I), ("iBestTime", I),
        ("sessionTimeLeft", F), ("distanceTraveled", F), ("isInPit", I), ("currentSectorIndex", I),
        ("lastSectorTime", I), ("numberOfLaps", I), ("tyreCompound", W * 33),
        ("replayTimeMultiplier", F), ("normalizedCarPosition", F),
    ]


class GraphicsACC(ctypes.Structure):
    """ACC graphics sayfasi, isValidLap'e kadar."""
    _pack_ = 4
    _fields_ = [
        ("packetId", I), ("status", I), ("session", I),
        ("currentTime", W * 15), ("lastTime", W * 15), ("bestTime", W * 15), ("split", W * 15),
        ("completedLaps", I), ("position", I), ("iCurrentTime", I), ("iLastTime", I), ("iBestTime", I),
        ("sessionTimeLeft", F), ("distanceTraveled", F), ("isInPit", I), ("currentSectorIndex", I),
        ("lastSectorTime", I), ("numberOfLaps", I), ("tyreCompound", W * 33),
        ("replayTimeMultiplier", F), ("normalizedCarPosition", F), ("activeCars", I),
        ("carCoordinates", F * 180), ("carID", I * 60), ("playerCarID", I), ("penaltyTime", F),
        ("flag", I), ("penalty", I), ("idealLineOn", I), ("isInPitLane", I), ("surfaceGrip", F),
        ("mandatoryPitDone", I), ("windSpeed", F), ("windDirection", F), ("isSetupMenuVisible", I),
        ("mainDisplayIndex", I), ("secondaryDisplayIndex", I), ("TC", I), ("TCCut", I),
        ("EngineMap", I), ("ABS", I), ("fuelXLap", I), ("rainLights", I), ("flashingLights", I),
        ("lightsStage", I), ("exhaustTemperature", F), ("wiperLV", I), ("driverStintTotalTimeLeft", I),
        ("driverStintTimeLeft", I), ("rainTyres", I), ("sessionIndex", I), ("usedFuel", F),
        ("deltaLapTime", W * 15), ("iDeltaLapTime", I), ("estimatedLapTime", W * 15),
        ("iEstimatedLapTime", I), ("isDeltaPositive", I), ("iSplit", I), ("isValidLap", I),
    ]


class StaticAC(ctypes.Structure):
    """AC/ACC static sayfasi, trackConfiguration'a kadar."""
    _pack_ = 4
    _fields_ = [
        ("smVersion", W * 15), ("acVersion", W * 15), ("numberOfSessions", I), ("numCars", I),
        ("carModel", W * 33), ("track", W * 33), ("playerName", W * 33), ("playerSurname", W * 33),
        ("playerNick", W * 33), ("sectorCount", I), ("maxTorque", F), ("maxPower", F), ("maxRpm", I),
        ("maxFuel", F), ("suspensionMaxTravel", F * 4), ("tyreRadius", F * 4), ("maxTurboBoost", F),
        ("deprecated_1", F), ("deprecated_2", F), ("penaltiesEnabled", I), ("aidFuelRate", F),
        ("aidTireRate", F), ("aidMechanicalDamage", F), ("aidAllowTyreBlankets", I), ("aidStability", F),
        ("aidAutoClutch", I), ("aidAutoBlip", I), ("hasDRS", I), ("hasERS", I), ("hasKERS", I),
        ("kersMaxJ", F), ("engineBrakeSettingsCount", I), ("ersPowerControllerCount", I),
        ("trackSPlineLength", F), ("trackConfiguration", W * 33),
    ]


STATE_TEXT = {0: "Oyun menüde / pist yüklü değil", 1: "Tekrar (replay) izleniyor", 2: "Canlı", 3: "Oyun duraklatıldı"}


def _gear(g):
    """AC/ACC: 0=R, 1=N, 2=1. vites -> -1/0/1.."""
    return (int(g) - 1) if 0 <= int(g) <= 10 else None


BODY_ZONES = ("front", "rear", "left", "right", "center")   # AC/ACC carDamage[5] sirasi (Kunos belgesi)


def _body_damage(values):
    """carDamage[5] -> {bolge: ham_deger}. Herhangi biri gecersiz/aralik disiysa None (yarisi gosterilmez)."""
    try:
        vals = [num(v, 0, 10000) for v in list(values)[:5]]
    except TypeError:
        return None
    if len(vals) != 5 or any(v is None for v in vals):
        return None
    return dict(zip(BODY_ZONES, vals))


def _pressures_kpa(psi4):
    v = four(psi4, 5, 90)                   # psi
    return None if v is None else [None if x is None else x * PSI_TO_KPA for x in v]


class _ACBase(GameAdapter):
    GRAPHICS = GraphicsAC
    ID = ""

    def __init__(self):
        self.m_phys = SharedMap("Local\\acpmf_physics", self.PHYS_SIZE)
        self.m_gfx = SharedMap("Local\\acpmf_graphics", ctypes.sizeof(self.GRAPHICS))
        self.m_sta = SharedMap("Local\\acpmf_static", ctypes.sizeof(StaticAC))
        self._sta_raw = None
        self._sta = None

    def close(self):
        for m in (self.m_phys, self.m_gfx, self.m_sta):
            m.close()

    def read(self):
        rp = self.m_phys.read()
        rg = self.m_gfx.read()
        if rp is None or rg is None:
            return None
        rs = self.m_sta.read()
        return self.parse(rp, rg, rs)

    def _static(self, rs):
        if rs is None or len(rs) < ctypes.sizeof(StaticAC):
            return None             # kisa/eksik okuma: pist-arac bilgisi guvenilmez
        rs = rs[:ctypes.sizeof(StaticAC)]
        if rs != self._sta_raw:
            self._sta_raw = rs
            self._sta = StaticAC.from_buffer_copy(rs)
        return self._sta


class ACCAdapter(_ACBase):
    ID = "ACC"
    NAME = "Assetto Corsa Competizione"
    GRAPHICS = GraphicsACC
    PHYS_SIZE = ctypes.sizeof(PhysicsACC)

    def parse(self, rp, rg, rs):
        f = self.new_frame(self.ID)
        if len(rp) < ctypes.sizeof(Physics) or len(rg) < ctypes.sizeof(GraphicsAC):
            f.state = "Veri yapısı uyuşmuyor (bellek beklenenden kısa)"
            return f
        phys_ext_ok = len(rp) >= ctypes.sizeof(PhysicsACC)
        gfx_full = len(rg) >= ctypes.sizeof(GraphicsACC)
        p = PhysicsACC.from_buffer_copy(pad(rp, ctypes.sizeof(PhysicsACC)))
        g = GraphicsACC.from_buffer_copy(pad(rg, ctypes.sizeof(GraphicsACC)))
        f.tick = p.packetId
        if g.status not in STATE_TEXT:
            f.state = "Veri yapısı uyuşmuyor (okunan değerler güvenilmez)"
            return f
        f.state = STATE_TEXT[g.status]
        f.live = g.status == 2
        sta = self._static(rs)
        if g.status in (2, 3) and sta is not None:
            car, trk = clean_text(wstr(sta.carModel), 32), clean_text(wstr(sta.track), 32)
            if car and trk:
                f.car_id, f.car_name = car, pretty_id(car)
                f.track_id, f.track_name = trk, ACC_TRACKS.get(trk.lower(), pretty_id(trk))
        if not f.live:
            return f

        f.speed_kmh = num(p.speedKmh, 0, 600)
        f.rpm = num(p.rpms, 0, 25000)
        f.throttle, f.brake = pedal(p.gas), pedal(p.brake)
        f.gear = _gear(p.gear)
        f.fuel_l = num(p.fuel, 0, 500)
        a, t = num(p.abs, 0, 5), num(p.tc, 0, 5)
        f.abs_active = None if a is None else min(1.0, a)
        f.tc_active = None if t is None else min(1.0, t)
        if 0 <= g.ABS <= 30:
            f.abs_level = float(g.ABS)
        if 0 <= g.TC <= 30:
            f.tc_level = float(g.TC)
        f.tyre_temp_c = four(p.tyreCoreTemperature, -50, 400)
        f.tyre_press_kpa = _pressures_kpa(p.wheelsPressure)
        f.tyre_wet = compound_is_wet(wstr(g.tyreCompound))             # "wet_compound" / "dry_compound"
        if f.tyre_wet is None and gfx_full and g.rainTyres in (0, 1):  # bilesik adi okunamadiysa oyunun yagmur lastigi bayragi
            f.tyre_wet = bool(g.rainTyres)
        f.body_damage = _body_damage(p.carDamage)

        # fiziksel sayfanin ACC'ye ozel devami: yapi dogrulanirsa kullanilir
        if phys_ext_ok and p.ignitionOn in (0, 1) and p.starterEngineOn in (0, 1) and p.isEngineRunning in (0, 1):
            f.engine_running = bool(p.isEngineRunning)
            f.water_c = num_nz(p.waterTemp, 1, 200)
            wd = [num(v, 0, 10000) for v in p.suspensionDamage]
            f.wheel_damage = wd if all(v is not None for v in wd) else None
        # (ACC'de yag sicakligi paylasimli bellekte yok -> oil_c None kalir)

        # tur bilgisi: gecerlilik bayragi okunabiliyorsa guvenilir; okunamiyorsa tur takibi KAPALI
        late_ok = gfx_full and g.isValidLap in (0, 1) and g.isInPitLane in (0, 1) and g.isInPit in (0, 1) \
            and -1 <= g.session <= 6
        if late_ok and 0 <= g.completedLaps <= 9999:
            f.lap_count = g.completedLaps
            f.lap_current_ms = ms_or_none(g.iCurrentTime, 0)
            f.lap_last_ms = ms_or_none(g.iLastTime)
            f.lap_best_ms = ms_or_none(g.iBestTime)
            f.sector_index = g.currentSectorIndex if 0 <= g.currentSectorIndex <= 2 else None
            f.last_sector_ms = ms_or_none(g.lastSectorTime)
            f.lap_valid = bool(g.isValidLap)
            f.in_pit = bool(g.isInPit or g.isInPitLane)
        else:
            f.notes.append("ACC graphics yapısı doğrulanamadı: tur takibi kapalı")
        derive_engine_running(f)
        return f


class ACAdapter(_ACBase):
    ID = "AC"
    NAME = "Assetto Corsa"
    GRAPHICS = GraphicsAC
    PHYS_SIZE = Physics.localVelocity.offset + 12

    def parse(self, rp, rg, rs):
        f = self.new_frame(self.ID)
        if len(rp) < self.PHYS_SIZE or len(rg) < ctypes.sizeof(GraphicsAC):
            f.state = "Veri yapısı uyuşmuyor (bellek beklenenden kısa)"
            return f
        p = Physics.from_buffer_copy(pad(rp, ctypes.sizeof(Physics)))
        g = GraphicsAC.from_buffer_copy(pad(rg, ctypes.sizeof(GraphicsAC)))
        f.tick = p.packetId
        if g.status not in STATE_TEXT:
            f.state = "Veri yapısı uyuşmuyor (okunan değerler güvenilmez)"
            return f
        f.state = STATE_TEXT[g.status]
        f.live = g.status == 2
        sta = self._static(rs)
        sectors3 = False
        if g.status in (2, 3) and sta is not None:
            car, trk = clean_text(wstr(sta.carModel), 32), clean_text(wstr(sta.track), 32)
            cfg = clean_text(wstr(sta.trackConfiguration), 32) or ""
            if car and trk:
                f.car_id, f.car_name = car, pretty_id(car)
                f.track_id = trk + ("|" + cfg if cfg else "")
                f.track_name = pretty_id(trk) + (" (%s)" % pretty_id(cfg) if cfg else "")
            sectors3 = sta.sectorCount == 3
        if not f.live:
            return f

        f.speed_kmh = num(p.speedKmh, 0, 600)
        f.rpm = num(p.rpms, 0, 25000)
        f.throttle, f.brake = pedal(p.gas), pedal(p.brake)
        f.gear = _gear(p.gear)
        f.fuel_l = num(p.fuel, 0, 500)
        a, t = num(p.abs, 0, 5), num(p.tc, 0, 5)
        f.abs_active = None if a is None else min(1.0, a)
        f.tc_active = None if t is None else min(1.0, t)
        f.tyre_temp_c = four(p.tyreCoreTemperature, -50, 400)
        f.tyre_press_kpa = _pressures_kpa(p.wheelsPressure)
        f.tyre_wet = compound_is_wet(wstr(g.tyreCompound))             # AC bilesik adi; "wet/rain" iceriyorsa islak
        f.body_damage = _body_damage(p.carDamage)
        # AC'de su/yag sicakligi ve ABS/TC ayar seviyesi paylasimli bellekte yok -> None

        if 0 <= g.completedLaps <= 9999 and g.isInPit in (0, 1):
            f.lap_count = g.completedLaps
            f.lap_current_ms = ms_or_none(g.iCurrentTime, 0)
            f.lap_last_ms = ms_or_none(g.iLastTime)
            f.lap_best_ms = ms_or_none(g.iBestTime)
            if sectors3 and 0 <= g.currentSectorIndex <= 2:
                f.sector_index = g.currentSectorIndex
                f.last_sector_ms = ms_or_none(g.lastSectorTime)
            f.in_pit = bool(g.isInPit)
            # AC gecerlilik bilgisi vermez. Sadece 3+ tekerlek pist disindaysa tur SUPHELI sayilir
            # (supheli tur rekora yazilmaz); bu bir tahmindir, "dogrulanmis" gibi sunulmaz.
            if 0 <= p.numberOfTyresOut <= 4:
                f.lap_suspect = p.numberOfTyresOut >= 3
        else:
            f.notes.append("AC graphics yapısı doğrulanamadı: tur takibi kapalı")
        derive_engine_running(f)
        return f
