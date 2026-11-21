"""PEDAL MOTORU icin orijinal telemetri kaynaklari (PedalHaptic.py'den AYNEN tasindi).
Bu dosyadaki mantik degistirilmedi. Oyun Bilgileri icin kullanilmaz; onun okuyuculari
telemetry/ klasorundeki ayri adaptorlerdir."""
import ctypes
import http.client
import json
import os
import socket
import struct
import time

from core.winmem import k32, running_processes

F = ctypes.c_float
I = ctypes.c_int


class Physics(ctypes.Structure):
    """ACC physics sayfasi (Local\\acpmf_physics) - sadece ihtiyacimiz olan kisma kadar."""
    _pack_ = 4
    _fields_ = [
        ("packetId", I), ("gas", F), ("brake", F), ("fuel", F), ("gear", I), ("rpms", I),
        ("steerAngle", F), ("speedKmh", F), ("velocity", F * 3), ("accG", F * 3),
        ("wheelSlip", F * 4), ("wheelLoad", F * 4), ("wheelsPressure", F * 4),
        ("wheelAngularSpeed", F * 4), ("tyreWear", F * 4), ("tyreDirtyLevel", F * 4),
        ("tyreCoreTemperature", F * 4), ("camberRAD", F * 4), ("suspensionTravel", F * 4),
        ("drs", F), ("tc", F), ("heading", F), ("pitch", F), ("roll", F), ("cgHeight", F),
        ("carDamage", F * 5), ("numberOfTyresOut", I), ("pitLimiterOn", I),
        ("abs", F), ("kersCharge", F), ("kersInput", F), ("autoShifterOn", I),
        ("rideHeight", F * 2), ("turboBoost", F), ("ballast", F), ("airDensity", F),
        ("airTemp", F), ("roadTemp", F), ("localAngularVel", F * 3), ("finalFF", F),
        ("performanceMeter", F), ("engineBrake", I), ("ersRecoveryLevel", I),
        ("ersPowerLevel", I), ("ersHeatCharging", I), ("ersIsCharging", I),
        ("kersCurrentKJ", F), ("drsAvailable", I), ("drsEnabled", I),
        ("brakeTemp", F * 4), ("clutch", F), ("tyreTempI", F * 4), ("tyreTempM", F * 4),
        ("tyreTempO", F * 4), ("isAIControlled", I), ("tyreContactPoint", F * 12),
        ("tyreContactNormal", F * 12), ("tyreContactHeading", F * 12), ("brakeBias", F),
        ("localVelocity", F * 3), ("P2PActivations", I), ("P2PStatus", I),
        ("currentMaxRpm", I), ("mz", F * 4), ("fx", F * 4), ("fy", F * 4),
        ("slipRatio", F * 4), ("slipAngle", F * 4),
    ]


PHYS_SIZE = ctypes.sizeof(Physics)


class MapSource:
    """Windows paylasimli bellegini (sadece MEVCUTSA) acan taban sinif. Oyun yokken hicbir sey olusturmaz."""
    NAME = "?"
    MAP = ""
    SIZE = 0

    def __init__(self):
        self.handle = None
        self.ptr = None
        self.last_try = 0.0

    def close(self):
        if os.name != "nt":
            return
        if self.ptr:
            k32.UnmapViewOfFile(self.ptr)
        if self.handle:
            k32.CloseHandle(self.handle)
        self.ptr = None
        self.handle = None

    def _ensure(self):
        if os.name != "nt":
            return None
        if not self.ptr:
            if time.time() - self.last_try < 0.5:
                return None
            self.last_try = time.time()
            h = k32.OpenFileMappingW(0x4, False, self.MAP)
            if not h:
                return None
            p = k32.MapViewOfFile(h, 0x4, 0, 0, self.SIZE)  # SIZE=0 -> tamamini esle
            if not p:
                k32.CloseHandle(h)
                return None
            self.handle, self.ptr = h, p
        return self.ptr

    def raw(self):
        p = self._ensure()
        if p is None:
            return None
        return ctypes.string_at(p, self.SIZE)


class ACCSource(MapSource):
    NAME = "ACC"
    MAP = "Local\\acpmf_physics"
    SIZE = PHYS_SIZE

    def read(self):
        raw = self.raw()
        if raw is None:
            return None
        d = Physics.from_buffer_copy(raw)
        valid = (-0.01 <= d.gas <= 1.01) and (-0.01 <= d.brake <= 1.01) and (0 <= d.speedKmh < 600)
        return {
            "packetId": d.packetId, "gas": d.gas, "brake": d.brake, "speed": d.speedKmh,
            "abs": d.abs, "tc": d.tc, "slipRatio": list(d.slipRatio), "valid": valid,
            "gear": d.gear,
            "rpm_ratio": (d.rpms / d.currentMaxRpm) if d.currentMaxRpm > 0 else 0.0,
        }


# --- LMU (rFactor 2 paylasimli bellek eklentisi yapisi, DENEYSEL) ---
D = ctypes.c_double
U8 = ctypes.c_ubyte


class RF2Wheel(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("mSuspensionDeflection", D), ("mRideHeight", D), ("mSuspForce", D), ("mBrakeTemp", D),
        ("mBrakePressure", D), ("mRotation", D), ("mLateralPatchVel", D),
        ("mLongitudinalPatchVel", D), ("mLateralGroundVel", D), ("mLongitudinalGroundVel", D),
        ("mCamber", D), ("mLateralForce", D), ("mLongitudinalForce", D), ("mTireLoad", D),
        ("mGripFract", D), ("mPressure", D), ("mTemperature", D * 3), ("mWear", D),
        ("mTerrainName", ctypes.c_char * 16), ("mSurfaceType", U8), ("mFlat", U8),
        ("mDetached", U8), ("mStaticUndeflectedRadius", U8), ("mVerticalTireDeflection", D),
        ("mWheelYLocation", D), ("mToe", D), ("mTireCarcassTemperature", D),
        ("mTireInnerLayerTemperature", D * 3), ("mExpansion", U8 * 24),
    ]


class RF2Vehicle(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("mID", I), ("mDeltaTime", D), ("mElapsedTime", D), ("mLapNumber", I), ("mLapStartET", D),
        ("mVehicleName", ctypes.c_char * 64), ("mTrackName", ctypes.c_char * 64),
        ("mPos", D * 3), ("mLocalVel", D * 3), ("mLocalAccel", D * 3), ("mOri", D * 9),
        ("mLocalRot", D * 3), ("mLocalRotAccel", D * 3), ("mGear", I), ("mEngineRPM", D),
        ("mEngineWaterTemp", D), ("mEngineOilTemp", D), ("mClutchRPM", D),
        ("mUnfilteredThrottle", D), ("mUnfilteredBrake", D), ("mUnfilteredSteering", D),
        ("mUnfilteredClutch", D), ("mFilteredThrottle", D), ("mFilteredBrake", D),
        ("mFilteredSteering", D), ("mFilteredClutch", D), ("mSteeringShaftTorque", D),
        ("mFront3rdDeflection", D), ("mRear3rdDeflection", D), ("mFrontWingHeight", D),
        ("mFrontRideHeight", D), ("mRearRideHeight", D), ("mDrag", D), ("mFrontDownforce", D),
        ("mRearDownforce", D), ("mFuel", D), ("mEngineMaxRPM", D),
        ("mScheduledStops", U8), ("mOverheating", U8), ("mDetached", U8), ("mHeadlights", U8),
        ("mDentSeverity", U8 * 8), ("mLastImpactET", D), ("mLastImpactMagnitude", D),
        ("mLastImpactPos", D * 3), ("mEngineTorque", D), ("mCurrentSector", I),
        ("mSpeedLimiter", U8), ("mMaxGears", U8), ("mFrontTireCompoundIndex", U8),
        ("mRearTireCompoundIndex", U8), ("mFuelCapacity", D),
        ("mFrontFlapActivated", U8), ("mRearFlapActivated", U8), ("mRearFlapLegalStatus", U8),
        ("mIgnitionStarter", U8), ("mFrontTireCompoundName", ctypes.c_char * 18),
        ("mRearTireCompoundName", ctypes.c_char * 18), ("mSpeedLimiterAvailable", U8),
        ("mAntiStallActivated", U8), ("mUnused", U8 * 2), ("mVisualSteeringWheelRange", F),
        ("mRearBrakeBias", D), ("mTurboBoostPressure", D), ("mPhysicsToGraphicsOffset", F * 3),
        ("mPhysicalSteeringWheelRange", F), ("mExpansion", U8 * 152), ("mWheels", RF2Wheel * 4),
    ]


class RF2Telemetry1(ctypes.Structure):
    """Baslik + ilk arac."""
    _pack_ = 4
    _fields_ = [("begin", ctypes.c_uint32), ("end", ctypes.c_uint32), ("hint", I),
                ("num", I), ("veh", RF2Vehicle)]


class LMUSource(MapSource):
    NAME = "LMU"
    MAP = "$rFactor2SMMP_Telemetry$"
    SIZE = ctypes.sizeof(RF2Telemetry1)

    def __init__(self):
        super().__init__()
        self.last = None

    def read(self):
        d = None
        for _ in range(4):  # surum sayaci ile tutarli okuma
            raw = self.raw()
            if raw is None:
                return None
            d = RF2Telemetry1.from_buffer_copy(raw)
            if d.begin == d.end:
                break
        else:
            return self.last
        empty = {"packetId": 0, "gas": 0.0, "brake": 0.0, "speed": 0.0, "abs": 0.0, "tc": 0.0,
                 "slipRatio": [0.0] * 4, "valid": True, "gear": 0, "rpm_ratio": 0.0}
        if d.num <= 0:
            return empty
        v = d.veh
        v_ms = sum(x * x for x in v.mLocalVel) ** 0.5
        sr = []
        for w in v.mWheels:  # sira: SOL-ON, SAG-ON, SOL-ARKA, SAG-ARKA
            r = w.mStaticUndeflectedRadius / 100.0
            if v_ms > 3.0 and r > 0.1:
                sr.append(max(-1.5, min(1.5, (abs(w.mRotation) * r - v_ms) / v_ms)))
            else:
                sr.append(0.0)
        gas, brake = v.mUnfilteredThrottle, v.mUnfilteredBrake
        # LMU'da ABS/TC bayragi bu yapida yok: hafif kaymayi ABS/TC gibi sayiyoruz
        abs_v = max(0.0, -min(sr[0], sr[1]) - 0.10) if brake > 0.2 else 0.0
        tc_v = max(0.0, max(sr[2], sr[3]) - 0.10) if gas > 0.2 else 0.0
        valid = (-0.01 <= gas <= 1.01) and (-0.01 <= brake <= 1.01) and v_ms < 250
        self.last = {"packetId": int(v.mElapsedTime * 1000), "gas": gas, "brake": brake,
                     "speed": v_ms * 3.6, "abs": abs_v, "tc": tc_v, "slipRatio": sr,
                     "valid": valid, "gear": v.mGear,
                     "rpm_ratio": (v.mEngineRPM / v.mEngineMaxRPM) if v.mEngineMaxRPM > 0 else 0.0}
        return self.last


# --- iRacing (resmi irsdk paylasimli bellegi) ---
class IRacingSource(MapSource):
    NAME = "iRacing"
    MAP = "Local\\IRSDKMemMapFileName"
    SIZE = 0
    NEEDED = ("Throttle", "Brake", "Speed", "BrakeABSactive", "LFspeed", "RFspeed", "LRspeed", "RRspeed", "Gear")

    def __init__(self):
        super().__init__()
        self.vars = None
        self.vars_key = None
        self.last = None

    def close(self):
        super().close()
        self.vars = None

    def _parse_vars(self, p, num, off):
        raw = ctypes.string_at(p + off, num * 144)
        out = {}
        for i in range(num):
            vtype, voff, _cnt = struct.unpack_from("<3i", raw, i * 144)
            name = raw[i * 144 + 16:i * 144 + 48].split(b"\0", 1)[0].decode("ascii", "ignore")
            if name in self.NEEDED:
                out[name] = (vtype, voff)
        return out

    def read(self):
        p = self._ensure()
        if p is None:
            return None
        empty = {"packetId": 0, "gas": 0.0, "brake": 0.0, "speed": 0.0, "abs": 0.0, "tc": 0.0,
                 "slipRatio": [0.0] * 4, "valid": True, "gear": 0, "rpm_ratio": 0.0}
        for _ in range(4):
            h = ctypes.string_at(p, 112)
            (_ver, status, _tr, _siu, _sil, _sio, num, voff, nbuf, blen) = struct.unpack_from("<10i", h, 0)
            if not (status & 1) or nbuf < 1 or nbuf > 4 or num <= 0 or blen <= 0:
                return empty
            bufs = [struct.unpack_from("<4i", h, 48 + 16 * i) for i in range(nbuf)]
            tick, boff = max((b[0], b[1]) for b in bufs)
            key = (num, voff)
            if self.vars is None or self.vars_key != key:
                self.vars = self._parse_vars(p, num, voff)
                self.vars_key = key
            data = ctypes.string_at(p + boff, blen)
            h2 = ctypes.string_at(p, 112)
            if max((struct.unpack_from("<4i", h2, 48 + 16 * i)[0]) for i in range(nbuf)) == tick:
                break
        else:
            return self.last

        def val(name, fmt, default=0.0):
            v = self.vars.get(name)
            if not v:
                return default
            return struct.unpack_from(fmt, data, v[1])[0]

        speed = val("Speed", "<f")
        gas = val("Throttle", "<f")
        brake = val("Brake", "<f")
        absa = 1.0 if val("BrakeABSactive", "<?", False) else 0.0
        ws = [val("LFspeed", "<f"), val("RFspeed", "<f"), val("LRspeed", "<f"), val("RRspeed", "<f")]
        have_ws = all(n in self.vars for n in ("LFspeed", "RFspeed", "LRspeed", "RRspeed"))
        if have_ws and speed > 3.0:
            sr = [max(-1.5, min(1.5, (abs(w) - speed) / speed)) for w in ws]
        else:
            sr = [0.0] * 4
        tc_v = max(0.0, max(sr[2], sr[3]) - 0.10) if gas > 0.2 else 0.0  # iRacing'de TC bayragi yok
        valid = ("Throttle" in self.vars and "Brake" in self.vars and "Speed" in self.vars
                 and -0.01 <= gas <= 1.01 and -0.01 <= brake <= 1.01 and speed < 250)
        self.last = {"packetId": tick, "gas": gas, "brake": brake, "speed": speed * 3.6,
                     "abs": absa, "tc": tc_v, "slipRatio": sr, "valid": valid,
                     "gear": int(val("Gear", "<i", 0)), "rpm_ratio": 0.0}
        return self.last


# --- Assetto Corsa (ilk oyun): ACC ile ayni bellek adi, daha kisa yapi ---
class ACSource(MapSource):
    NAME = "AC"
    MAP = "Local\\acpmf_physics"
    SIZE = Physics.localVelocity.offset + 12

    def __init__(self):
        super().__init__()
        self.R = 0.33  # tekerlek yaricapi tahmini (surus sirasinda kendini ayarlar)

    def read(self):
        raw = self.raw()
        if raw is None:
            return None
        d = Physics.from_buffer_copy(raw + b"\0" * (PHYS_SIZE - len(raw)))
        v = d.speedKmh / 3.6
        w = [abs(x) for x in d.wheelAngularSpeed]
        if d.gas < 0.05 and d.brake < 0.02 and v > 8.0 and sum(w) > 4.0:
            rn = v / (sum(w) / 4.0)  # gaz-fren yokken tekerlekler serbest doner: yaricapi ogren
            if 0.2 < rn < 0.5:
                self.R += 0.02 * (rn - self.R)
        if v > 3.0:
            sr = [max(-1.5, min(1.5, (x * self.R - v) / v)) for x in w]
        else:
            sr = [0.0] * 4
        valid = (-0.01 <= d.gas <= 1.01) and (-0.01 <= d.brake <= 1.01) and (0 <= d.speedKmh < 600)
        return {"packetId": d.packetId, "gas": d.gas, "brake": d.brake, "speed": d.speedKmh,
                "abs": d.abs, "tc": d.tc, "slipRatio": sr, "valid": valid,
                "gear": d.gear, "rpm_ratio": 0.0}


# --- BeamNG.drive: OutGauge UDP (oyunda acilmasi gerekir: 127.0.0.1, port 4444) ---
OG_FMT = "<I4sHBBfffffffIIfff"


class BeamNGSource:
    NAME = "BeamNG"
    PORT = 4444

    def __init__(self):
        self.sock = None
        self.thread = None
        self.last = None
        self.count = 0
        self.gen = 0

    def _loop(self, gen):
        try:
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sk.bind(("0.0.0.0", self.PORT))
            sk.settimeout(0.2)
        except Exception:
            return
        self.sock = sk
        while gen == self.gen:
            try:
                data = sk.recv(256)
            except socket.timeout:
                continue
            except Exception:
                break
            self.parse(data)
        try:
            sk.close()
        except Exception:
            pass

    def parse(self, data):
        if len(data) < 92:
            return
        (_t, _car, _fl, gear, _plid, speed, _rpm, _turbo, _et, _fuel, _op, _ot, _dash, show,
         thr, brk, _clu) = struct.unpack_from(OG_FMT, data, 0)
        self.count += 1
        self.last = {"packetId": self.count, "gas": thr, "brake": brk, "speed": speed * 3.6,
                     "abs": 1.0 if show & (1 << 10) else 0.0,
                     "tc": 1.0 if show & (1 << 4) else 0.0,
                     "slipRatio": [0.0] * 4,
                     "valid": (-0.01 <= thr <= 1.01) and (-0.01 <= brk <= 1.01) and speed < 250,
                     "gear": gear,
                     "rpm_ratio": 0.98 if show & 1 else 0.0}  # vites isigi yanarken "devir siniri"

    def read(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, args=(self.gen,), daemon=True)
            self.thread.start()
            return None
        return self.last

    def close(self):
        self.gen += 1  # eski is parcacigi kendiliginden biter (yuvayi kendisi kapatir)
        self.thread = None
        self.last = None


# --- Euro Truck Simulator 2: "ETS2 Telemetry Server" (Funbit) HTTP API ---
class ETS2Source:
    NAME = "ETS2"
    HOST, PORT, PATH = "127.0.0.1", 25555, "/api/ets2/telemetry"

    def __init__(self):
        self.thread = None
        self.last = None
        self.count = 0
        self.gen = 0

    def _loop(self, gen):
        conn = None
        while gen == self.gen:
            try:
                if conn is None:
                    conn = http.client.HTTPConnection(self.HOST, self.PORT, timeout=0.5)
                conn.request("GET", self.PATH)
                resp = conn.getresponse()
                j = json.loads(resp.read())
                self.parse(j)
                time.sleep(0.015)
            except Exception:
                conn = None
                time.sleep(0.5)

    def parse(self, j):
        if not j.get("game", {}).get("connected", False):
            return
        t = j.get("truck", {})
        mx = t.get("engineRpmMax", 0) or 0
        gas = float(t.get("userThrottle", 0.0))
        brk = float(t.get("userBrake", 0.0))
        speed = abs(float(t.get("speed", 0.0)))
        self.count += 1
        self.last = {"packetId": self.count, "gas": gas, "brake": brk, "speed": speed,
                     "abs": 0.0, "tc": 0.0, "slipRatio": [0.0] * 4,
                     "valid": (-0.01 <= gas <= 1.01) and (-0.01 <= brk <= 1.01) and speed < 300,
                     "gear": int(t.get("gear", 0)),
                     "rpm_ratio": (float(t.get("engineRpm", 0.0)) / mx) if mx > 0 else 0.0}

    def read(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, args=(self.gen,), daemon=True)
            self.thread.start()
            return None
        return self.last

    def close(self):
        self.gen += 1
        self.thread = None
        self.last = None


SOURCES = {"ACC": ACCSource, "AC": ACSource, "LMU": LMUSource, "iRacing": IRacingSource,
           "BeamNG": BeamNGSource, "ETS2": ETS2Source}
HINTS = {"ACC": " (oyunu baslat)", "AC": " (oyunu baslat, pistte ol)",
         "LMU": " (oyunu baslat, rF2 eklentisi acik mi?)", "iRacing": " (oyunu baslat, pistte ol)",
         "BeamNG": " (BeamNG'de OutGauge acik mi? 127.0.0.1, port 4444)",
         "ETS2": " (ETS2 Telemetry Server calisiyor mu?)"}
PROC_GAMES = [("acs.exe", "AC"), ("acs_x86.exe", "AC"), ("ac2-win64-shipping.exe", "ACC"),
              ("le mans ultimate.exe", "LMU"), ("beamng.drive.x64.exe", "BeamNG"),
              ("beamng.drive.exe", "BeamNG"), ("eurotrucks2.exe", "ETS2")]



def probe_games():
    """Hangi oyun acik? Once program adina bakar, sonra paylasimli bellege (sadece var mi diye)."""
    if os.name != "nt":
        return None
    procs = running_processes()
    for exe, name in PROC_GAMES:
        if exe in procs:
            return name
    for p in procs:
        if p.startswith("iracingsim"):
            return "iRacing"
    for name in ("ACC", "iRacing", "LMU"):
        h = k32.OpenFileMappingW(0x4, False, SOURCES[name].MAP)
        if h:
            k32.CloseHandle(h)
            return name
    return None

