"""Oyun Bilgileri icin telemetri iscisi. Pedal motorundan TAMAMEN bagimsiz bir iplikte calisir;
burada olusan hata pedal/fan sistemini etkilemez."""
import threading
import time

from core.game_detector import GameDetector
from telemetry.ac_family import ACAdapter, ACCAdapter
from telemetry.iracing import IRacingAdapter
from telemetry.lmu import LMUAdapter

GAME_NAMES = {"ACC": "Assetto Corsa Competizione", "AC": "Assetto Corsa",
              "LMU": "Le Mans Ultimate", "iRacing": "iRacing"}
ADAPTERS = {"ACC": ACCAdapter, "AC": ACAdapter, "LMU": LMUAdapter, "iRacing": IRacingAdapter}
STALE_S = 0.7           # tick bu sureden uzun degismezse veri akmiyor sayilir
MISS_TO_CLOSE = 3       # oyun surecini kac ardisik taramada goremeyince kapandi say


class TelemetryManager(threading.Thread):
    def __init__(self, tracker):
        super().__init__(daemon=True)
        self.tracker = tracker
        self.detector = GameDetector()
        self.running = True
        self.lock = threading.Lock()
        self._state = {"game_id": None, "game_name": None, "running": False, "status": "Oyun algılanmadı",
                       "frame": None, "elapsed_s": None, "clock_running": False}
        self.game = None
        self.adapter = None
        self.start_epoch = None
        self.final_elapsed = None
        self.misses = 0
        self.last_detect = 0.0
        self.last_tick = None
        self.last_tick_change = 0.0
        self.errors = 0
        self.last_error = ""

    def state(self):
        with self.lock:
            return dict(self._state)

    def _switch(self, gid):
        if self.adapter:
            try:
                self.adapter.close()
            except Exception:
                pass
        self.tracker.end()
        self.adapter = ADAPTERS[gid]() if gid else None
        self.game = gid
        self.last_tick = None
        self.errors = 0
        self.last_error = ""

    def _detect(self, now):
        if now - self.last_detect < 1.0:
            return
        self.last_detect = now
        try:
            det = self.detector.detect(self.game)
        except Exception:
            det = None
        if det is None:
            if self.game:
                self.misses += 1
                if self.misses >= MISS_TO_CLOSE:     # oyun kapandi: sayac durur, oturum kaydedilir
                    self.final_elapsed = self._elapsed()
                    self.tracker.end()
                    self._switch(None)
                    self.start_epoch = None
            return
        self.misses = 0
        gid, _pid, start = det
        if gid != self.game:
            self._switch(gid)
            self.final_elapsed = None
            self.start_epoch = start or time.time()
        elif start and self.start_epoch is None:
            self.start_epoch = start

    def _elapsed(self):
        if self.game and self.start_epoch:
            return max(0.0, time.time() - self.start_epoch)
        return self.final_elapsed

    def run(self):
        while self.running:
            now = time.monotonic()
            frame, status = None, ""
            try:
                self._detect(now)
                if self.game and self.adapter:
                    try:
                        frame = self.adapter.read()
                        self.errors = 0
                    except Exception as e:           # adaptor hatasi digerlerini etkilemez
                        self.errors += 1
                        self.last_error = "%s: %s" % (type(e).__name__, e)
                        frame = None
                    if frame is not None:
                        if frame.tick != self.last_tick:
                            self.last_tick = frame.tick
                            self.last_tick_change = now
                        elif frame.live and now - self.last_tick_change > STALE_S:
                            frame.live = False
                            frame.state = "Veri akmıyor"
                    if self.errors >= 5:
                        status = "Okuma hatası: " + self.last_error
                    elif frame is None:
                        status = "%s açık, telemetri verisi bulunamadı (oyun menüde veya paylaşımlı bellek kapalı)" \
                                 % GAME_NAMES[self.game]
                    else:
                        status = frame.state
                    self.tracker.update(frame, now)
                else:
                    self.tracker.update(None, now)
                    status = "Desteklenen bir oyun algılanmadı"
            except Exception as e:                   # beklenmeyen: dongu asla olmesin
                status = "Beklenmeyen hata: %s" % e
            el = self._elapsed()
            with self.lock:
                self._state = {"game_id": self.game, "game_name": GAME_NAMES.get(self.game),
                               "running": self.game is not None, "status": status, "frame": frame,
                               "elapsed_s": el, "clock_running": self.game is not None}
            time.sleep(0.03 if self.game else 0.25)

    def stop(self):
        self.running = False
        try:
            self.tracker.end()
            if self.adapter:
                self.adapter.close()
        except Exception:
            pass
