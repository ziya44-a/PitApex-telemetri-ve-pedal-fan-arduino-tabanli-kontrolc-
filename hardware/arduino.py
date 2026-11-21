"""Arduino seri baglantisi. Pedal motoru ve fan AYNI portu paylasir; bu yuzden tek bir
baglanti nesnesi ve tek bir yazma kilidi vardir.

Eski kod (PedalHaptic.py) bu islerin hepsini Engine icinde yapiyordu; mantik ayni, sadece
fan da kullanabilsin diye ayrildi."""
import threading
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # pyserial kurulu degilse arayuz yine acilir, baglanti kurulamaz
    serial = None

PEDAL_FW_OK = (2, 3, 4)   # pedal komutlari V2, V3 ve V4 kodlarinda calisir
FAN_FW_MIN = 3            # fan komutu (F) V3 ile geldi (V3: tek fan, cikis kodda sabit)
MULTI_FW_MIN = 4          # M3/M4 titresim motoru ve secilebilir/iki fan cikisi V4 ile geldi


def list_ports():
    if serial is None:
        return []
    try:
        return [p.device for p in serial.tools.list_ports.comports()]
    except Exception:
        return []


class ArduinoLink:
    FAREWELL = b"M1,0,0\nM2,0,0\nM3,0,0\nM4,0,0\nF,0\nF1,0\nF2,0\nF3,0\nF4,0\n"   # baglanti kesilirken: her sey dursun

    def __init__(self):
        self.led_version = None    # LED kartinin kodu "LED<n>" diye cevap verirse (pedal/fan kodu cevap vermez)
        self.ser = None
        self.lock = threading.Lock()
        self.ready_at = 0.0
        self.fw_version = None     # None = henuz cevap yok
        self.fw_asked = 0.0
        self.latency = None
        self.lat_max = 0.0
        self.ping_t = 0.0
        self.ping_sent = 0.0
        self.error = ""
        self.alive = True

    # --- durum ---
    @property
    def connected(self):
        return self.ser is not None

    @property
    def ready(self):
        return self.ser is not None and time.time() >= self.ready_at

    @property
    def fw_ok(self):
        """Pedal kodu uyumlu mu? None=bilinmiyor, True/False."""
        if self.fw_version is None:
            return None
        return self.fw_version in PEDAL_FW_OK

    @property
    def fan_supported(self):
        return self.fw_version is not None and self.fw_version >= FAN_FW_MIN

    @property
    def multi_output(self):
        """V4+: 4 cikis (M1-M4), her biri pedal motoru ya da fan olabilir."""
        return self.fw_version is not None and self.fw_version >= MULTI_FW_MIN

    # --- baglanti ---
    def connect(self, port):
        if serial is None:
            raise RuntimeError("pyserial kurulu degil (1_kurulum.bat calistirin)")
        self.disconnect()
        ser = serial.Serial(port, 115200, timeout=0.05, write_timeout=0.1)
        self.ser = ser
        self.ready_at = time.time() + 2.0   # Arduino baglaninca yeniden baslar
        self.latency = None
        self.lat_max = 0.0
        self.fw_version = None
        self.led_version = None
        self.fw_asked = 0.0
        self.error = ""
        threading.Thread(target=self._reader, args=(ser,), daemon=True).start()

    def disconnect(self):
        ser, self.ser = self.ser, None
        if ser:
            try:
                ser.write(self.FAREWELL)
                ser.close()
            except Exception:
                pass

    def fail(self, exc):
        self.error = "Seri port hatasi: %s" % exc
        self.ser = None

    def _reader(self, ser):
        while self.alive and ser is self.ser:
            try:
                line = ser.readline()
            except Exception:
                break
            ln = line.strip()
            if ln.startswith(b"LED"):
                try:
                    self.led_version = int(ln[3:])
                except ValueError:
                    self.led_version = 0
            elif ln.startswith(b"V"):
                try:
                    self.fw_version = int(ln[1:])
                except ValueError:
                    self.fw_version = 0     # taninmayan surum: uyumsuz say
            if ln == b"P" and self.ping_t:
                ms = (time.perf_counter() - self.ping_t) * 1000.0 / 2.0
                self.latency = ms if self.latency is None else 0.8 * self.latency + 0.2 * ms
                self.lat_max = max(self.lat_max, ms)

    # --- yazma ---
    def write_line(self, text):
        """Tek komut yazar (kendi kilidiyle). Basariliysa True."""
        ser = self.ser
        if not ser or time.time() < self.ready_at:
            return False
        try:
            with self.lock:
                ser.write((text + "\n").encode())
            return True
        except Exception as e:
            self.fail(e)
            return False

    def service_locked(self, ser, now):
        """Kilit alinmisken surum sorgusu ve gecikme olcumu (Engine.send'den cagrilir)."""
        if self.fw_version is None and now - self.fw_asked > 1.0:
            ser.write(b"V\n")
            self.fw_asked = now
        if now - self.ping_sent > 1.0:
            self.ping_t = time.perf_counter()
            ser.write(b"P\n")
            self.ping_sent = now


class LedLink(ArduinoLink):
    """LED kartinin AYRI Arduino'su icin ikinci baglanti (pedal/fan baglantisindan tamamen bagimsiz)."""
    FAREWELL = b"C\n"

    @property
    def led_ok(self):
        return self.led_version is not None and self.led_version >= 1


def list_port_names():
    """['COM3 - Arduino Uno (COM3)', ...] (cihaz adi ilk kelimedir)."""
    if serial is None:
        return []
    try:
        return ["%s - %s" % (p.device, p.description) for p in serial.tools.list_ports.comports()]
    except Exception:
        return []
