"""Ortak telemetri veri modeli + dogrulama yardimcilari.

KURAL: Bir alan oyundan GERCEKTEN ve MANTIKLI olarak okunamadiysa None'dir. Arayuz None'i
'Veri alinamiyor' diye gosterir. Hicbir yerde tahmin/uydurma deger uretilmez."""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class TelemetryFrame:
    game: str = ""
    t: float = 0.0                       # okuma zamani (time.monotonic)
    live: bool = False                   # oyun canli suruste ve veri akiyor
    state: str = ""                      # kullaniciya gosterilecek durum ("canli", "pause", ...)
    tick: Optional[float] = None         # veri tazeligi sayaci (degisiyorsa veri akiyor)
    clock_s: Optional[float] = None      # oyunun kendi saati (saniye), tur dogrulamasi icin

    track_id: Optional[str] = None
    track_name: Optional[str] = None
    car_id: Optional[str] = None
    car_name: Optional[str] = None

    speed_kmh: Optional[float] = None
    rpm: Optional[float] = None
    throttle: Optional[float] = None     # 0..1
    brake: Optional[float] = None        # 0..1
    gear: Optional[int] = None           # -1=R, 0=N, 1..=vites
    abs_active: Optional[float] = None   # 0..1 oyunun GERCEK ABS aktivitesi
    tc_active: Optional[float] = None    # 0..1 oyunun GERCEK TC aktivitesi
    abs_level: Optional[float] = None    # surucunun sectigi ABS ayari
    tc_level: Optional[float] = None
    fuel_l: Optional[float] = None
    water_c: Optional[float] = None
    oil_c: Optional[float] = None
    tyre_temp_c: Optional[List[Optional[float]]] = None      # SolOn, SagOn, SolArka, SagArka
    tyre_press_kpa: Optional[List[Optional[float]]] = None
    tyre_wet: Optional[bool] = None      # True = islak/yagmur lastigi takili, False = kuru; oyun bilgi vermiyorsa None
    engine_running: Optional[bool] = None
    # Bolgesel hasar: yalnizca oyunun GERCEK hasar alani okunabildiyse dolar, aksi halde None.
    # body_damage: {"front","rear","left","right","center"} -> ham deger (0 = hasarsiz); oyunun birimi korunur.
    body_damage: Optional[dict] = None
    wheel_damage: Optional[List[float]] = None   # SolOn, SagOn, SolArka, SagArka suspansiyon hasari (ham)
    weather_current: Optional[str] = None  # Only game-provided observations
    weather_forecast: Optional[list] = None  # Only game-provided forecasts

    lap_count: Optional[int] = None      # tamamlanan tur sayisi (oyunun sayaci)
    lap_current_ms: Optional[int] = None
    lap_last_ms: Optional[int] = None
    lap_best_ms: Optional[int] = None
    sector_index: Optional[int] = None   # 0,1,2
    last_sector_ms: Optional[int] = None
    last_lap_sectors: Optional[Tuple[int, int, int]] = None  # oyunun verdigi son tur sektorleri
    lap_valid: Optional[bool] = None     # oyun gecerlilik bilgisi veriyorsa
    lap_suspect: Optional[bool] = None   # oyun bilgi vermiyor ama tur supheli (ornegin 3+ tekerlek pist disinda)
    in_pit: Optional[bool] = None
    notes: List[str] = field(default_factory=list)


# ---- dogrulama yardimcilari ----
def compound_is_wet(name):
    """Oyunun verdigi lastik bilesigi adindan: islak mi? Bos/okunamayan ad -> None (tahmin yok)."""
    try:
        n = str(name).strip().lower()
    except Exception:
        return None
    n = "".join(ch for ch in n if ch.isprintable())
    if not n:
        return None
    return any(w in n for w in ("wet", "rain", "inter", "islak"))


def num(v, lo, hi):
    """Sayi mantikli aralikta ve sonlu ise float, degilse None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f) or f < lo or f > hi:
        return None
    return f


def num_nz(v, lo, hi):
    """num() + tam 0 'veri yok' sayilir (oyunlar saglamadiklari alani 0 doldurur)."""
    f = num(v, lo, hi)
    return None if f is None or f == 0.0 else f


def pedal(v):
    f = num(v, -0.02, 1.02)
    return None if f is None else min(1.0, max(0.0, f))


def ms_or_none(v, lo=1, hi=3_600_000):
    """Milisaniye tamsayi, aralik disi (ornegin INT_MAX 'yok' isareti) None."""
    try:
        i = int(v)
    except (TypeError, ValueError):
        return None
    return i if lo <= i <= hi else None


def four(values, lo, hi, nonzero=True):
    """4 tekerlek degeri: hepsi mantikliysa liste, degilse None. Hepsi 0 ise None (veri yok)."""
    try:
        vals = list(values)[:4]
    except TypeError:
        return None
    if len(vals) != 4:
        return None
    out = [(num_nz if nonzero else num)(v, lo, hi) for v in vals]
    if all(o is None for o in out):
        return None
    return out


def fmt_ms(ms):
    """2:21.222 biciminde sure."""
    if ms is None:
        return None
    ms = int(round(ms))
    m, rest = divmod(ms, 60000)
    return "%d:%06.3f" % (m, rest / 1000.0)


def fmt_hms(seconds):
    s = int(max(0, seconds))
    return "%02d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def gear_text(g):
    if g is None:
        return None
    return "R" if g < 0 else ("N" if g == 0 else str(g))
