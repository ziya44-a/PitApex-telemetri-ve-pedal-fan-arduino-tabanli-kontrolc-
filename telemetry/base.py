"""Oyun Bilgileri okuyucularinin ortak tabani."""
import time

from core.models import TelemetryFrame


class GameAdapter:
    ID = "?"
    NAME = "?"

    def read(self):
        """TelemetryFrame doner; oyunun paylasimli bellegi yoksa/okunamiyorsa None."""
        raise NotImplementedError

    def close(self):
        pass

    @staticmethod
    def new_frame(game):
        return TelemetryFrame(game=game, t=time.monotonic())


def pad(raw, size):
    """Haritadan beklenenden kisa veri gelirse sifirla tamamla (eksik alanlar 'veri yok' olur)."""
    if raw is None:
        return None
    if len(raw) >= size:
        return raw[:size]
    return raw + b"\0" * (size - len(raw))


def derive_engine_running(f, rpm_min=100):
    """Oyun motor durumu bayragi vermiyorsa: devir > esik ise 'calisiyor' (gercek devirden turetilir)."""
    if f.engine_running is None and f.rpm is not None:
        f.engine_running = f.rpm > rpm_min
