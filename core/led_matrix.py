"""MAX7219 8x8 LED matris icin Tk'dan bagimsiz mantik: font, yon donusumu, ayar dogrulama.

Goruntu = 8 satir, her satir bir bayt (satir 0 = ust, bit7 = en sol sutun). PC tarafi goruntuyu cizer, Arduino sadece
16 hex karakterlik "D" komutuyla gelen 8 baytı modüle yazar; bu yuzden her MAX7219 matrisi (modul kablolamasi farkli
olsa da) donme/ayna ayariyla dogru yone getirilebilir.
"""
from core.engine import norm_gear

ROTATIONS = (0, 90, 180, 270)
BRIGHTNESS_MAX = 15
BLANK = (0,) * 8

# 7 satirlik govdeler (satir 0 = ust, bit7 = sol). glyph() bunlari dikeyde ortalar.
_FONT = {
    "0": (0x3C, 0x66, 0x6E, 0x76, 0x66, 0x66, 0x3C),
    "1": (0x18, 0x38, 0x18, 0x18, 0x18, 0x18, 0x7E),
    "2": (0x3C, 0x66, 0x06, 0x0C, 0x18, 0x30, 0x7E),
    "3": (0x3C, 0x66, 0x06, 0x1C, 0x06, 0x66, 0x3C),
    "4": (0x0C, 0x1C, 0x2C, 0x4C, 0x7E, 0x0C, 0x0C),
    "5": (0x7E, 0x60, 0x7C, 0x06, 0x06, 0x66, 0x3C),
    "6": (0x1C, 0x30, 0x60, 0x7C, 0x66, 0x66, 0x3C),
    "7": (0x7E, 0x66, 0x0C, 0x18, 0x18, 0x18, 0x18),
    "8": (0x3C, 0x66, 0x66, 0x3C, 0x66, 0x66, 0x3C),
    "9": (0x3C, 0x66, 0x66, 0x3E, 0x06, 0x0C, 0x38),
    "N": (0x66, 0x76, 0x7E, 0x7E, 0x6E, 0x66, 0x66),
    "R": (0x7C, 0x66, 0x66, 0x7C, 0x78, 0x6C, 0x66),
    "-": (0x00, 0x00, 0x00, 0x7E, 0x00, 0x00, 0x00),
    "+": (0x00, 0x18, 0x18, 0x7E, 0x18, 0x18, 0x00),
    " ": (0, 0, 0, 0, 0, 0, 0),
}


def glyph(ch):
    """Karakterin 8 satirlik goruntusu (yoksa bos). 7 satirlik govde dikeyde ortalanir (ust satir bos)."""
    body = _FONT.get(ch)
    return BLANK if body is None else (0,) + tuple(body)


def all_on():
    return (0xFF,) * 8


def _bits(rows):
    return [[(rows[r] >> (7 - c)) & 1 for c in range(8)] for r in range(8)]


def _bytes(bits):
    return tuple(sum(bits[r][c] << (7 - c) for c in range(8)) for r in range(8))


def transform(rows, rotation=0, flip_h=False, flip_v=False):
    """Once ayna (yatay/dikey), sonra saat yonunde 0/90/180/270 derece doner. Dort donme = ayni goruntu."""
    b = _bits(rows)
    if flip_h:
        b = [row[::-1] for row in b]
    if flip_v:
        b = b[::-1]
    for _ in range((int(rotation) // 90) % 4):
        b = [[b[7 - c][r] for c in range(8)] for r in range(8)]          # saat yonunde 90 derece
    return _bytes(b)


def to_hex(rows):
    return "".join("%02X" % (v & 0xFF) for v in rows)


def parse_hex(text):
    """16 hex karakter -> 8 bayt ya da None (gecersiz)."""
    if not isinstance(text, str) or len(text) != 16:
        return None
    try:
        return tuple(int(text[i:i + 2], 16) for i in range(0, 16, 2))
    except ValueError:
        return None


# ---------------------------------------------------------------- ayarlar
FEATURES = (("gear", "Vites göstergesi"),)            # ileride yeni LED ozellikleri buraya eklenir
NEUTRAL_CHOICES = ("N", "0")
NO_DATA_CHOICES = ("blank", "dash")
DEFAULT_LED = {
    "enabled": False,
    "port": "",
    "auto_connect": False,
    "brightness": 4,                  # 0-15 (MAX7219 parlaklik)
    "rotation": 0,
    "flip_h": False,
    "flip_v": False,
    "feature": "gear",
    "gear": {"neutral": "N", "no_data": "blank"},
    "show_gear": True, "show_flags": False, "show_proximity": False,
    "show_adjustments": True, "adjustment_seconds": 2.5,
    "adjustment_enabled": {k: True for k in ("tc", "abs", "map", "tc2")},
    "blink_flags": False, "blink_proximity": True, "blink_flag_speed": 3, "blink_proximity_speed": 3,
    "flag_enabled": {k: True for k in ("blue","green","yellow","double_yellow","white","warning","mechanical","black","pit","final","red","checkered")},
    "colors": {k: v for k,v in {"gear":"#ff3b30","blue":"#30398f","green":"#00dd55","yellow":"#ffcc00","double_yellow":"#ffcc00","white":"#ffffff","warning":"#ffffff","mechanical":"#ff8b18","black":"#777777","pit":"#00aaff","final":"#ffe500","red":"#ff2222","checkered":"#ffffff","left":"#ff0000","right":"#ff0000","both":"#ff0000","rear":"#ff0000"}.items()},
}


def _int(v, lo, hi, default):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:
        return default
    return int(min(hi, max(lo, round(f))))


CUSTOM_KEYS = tuple(["gear_"+str(n) for n in range(1,10)] + ["gear_N","gear_R","gear_+","gear_-","left","right","both","rear"] + list(("blue","green","yellow","double_yellow","white","warning","mechanical","black","pit","final","red","checkered")) + ["adjust_%s_%d" % (k,n) for k in ("tc","abs","map","tc2") for n in range(100)])
def custom_image(cfg, key, fallback):
    return tuple(cfg.get("custom_patterns", {}).get(key, fallback))

def normalized(cfg):
    """Ayarlari guvenli degerlere getirir (bozuk/eksik alan varsayilana doner)."""
    cfg = cfg if isinstance(cfg, dict) else {}
    gear = cfg.get("gear") if isinstance(cfg.get("gear"), dict) else {}
    rot = _int(cfg.get("rotation", 0), 0, 270, 0)
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "port": cfg.get("port") if isinstance(cfg.get("port"), str) else "",
        "auto_connect": bool(cfg.get("auto_connect", False)),
        "brightness": _int(cfg.get("brightness", 4), 0, BRIGHTNESS_MAX, 4),
        "rotation": rot if rot in ROTATIONS else 0,
        "flip_h": bool(cfg.get("flip_h", False)),
        "flip_v": bool(cfg.get("flip_v", False)),
        "feature": cfg.get("feature") if cfg.get("feature") in dict(FEATURES) else "gear",
        "show_gear": bool(cfg.get("show_gear", True)),
        "show_adjustments": bool(cfg.get("show_adjustments", True)),
        "adjustment_seconds": max(0.5, min(8.0, float(cfg.get("adjustment_seconds", 2.5)))) if str(cfg.get("adjustment_seconds",2.5)).replace(".","",1).isdigit() else 2.5,
        "adjustment_enabled": {k: bool((cfg.get("adjustment_enabled") or {}).get(k, True)) for k in ("tc","abs","map","tc2")},
        "show_flags": bool(cfg.get("show_flags", False)),
        "show_proximity": bool(cfg.get("show_proximity", False)),
        "blink_flags": bool(cfg.get("blink_flags", False)),
        "blink_proximity": bool(cfg.get("blink_proximity", True)),
        "blink_flag_speed": _int(cfg.get("blink_flag_speed", 3), 1, 10, 3),
        "blink_proximity_speed": _int(cfg.get("blink_proximity_speed", 3), 1, 10, 3),
        "flag_enabled": {k: bool((cfg.get("flag_enabled") or {}).get(k, True)) for k in DEFAULT_LED["flag_enabled"]},
        "colors": {k: (cfg.get("colors") or {}).get(k, v) if isinstance((cfg.get("colors") or {}).get(k, v), str) and __import__("re").fullmatch(r"#[0-9a-fA-F]{6}", (cfg.get("colors") or {}).get(k, v)) else v for k,v in DEFAULT_LED["colors"].items()},
        "custom_patterns": {k:list(v) for k,v in (cfg.get("custom_patterns") if isinstance(cfg.get("custom_patterns"),dict) else {}).items() if k in CUSTOM_KEYS and isinstance(v,(list,tuple)) and len(v)==8 and all(type(n)==int and 0<=n<=255 for n in v)},
        "gear": {"neutral": gear.get("neutral") if gear.get("neutral") in NEUTRAL_CHOICES else "N",
                 "no_data": gear.get("no_data") if gear.get("no_data") in NO_DATA_CHOICES else "blank"},
    }


# ---------------------------------------------------------------- vites
def gear_char(gear, neutral="N"):
    """Normalize vites (-1=R, 0=N, 1..=ileri) -> gosterilecek karakter. 10 ve ustu '+' (tek hane sigmaz)."""
    if gear is None:
        return None
    if gear < 0:
        return "R"
    if gear == 0:
        return neutral if neutral in NEUTRAL_CHOICES else "N"
    return str(gear) if gear <= 9 else "+"


def live_gear(snap, source_name):
    """Pedal motorunun okumasindan (SALT-OKUNUR) normalize vites. Canli veri yoksa None: vites uydurulmaz."""
    try:
        if not snap or not snap.get("live") or not snap.get("valid", True):
            return None
        t = snap.get("t")
        if not t or "gear" not in t:
            return None
        return norm_gear(source_name, t["gear"])
    except Exception:
        return None


def feature_image(cfg, gear):
    """Secili ozelligin goruntusu ve aciklamasi: (satirlar, metin). Yon donusumu BURADA uygulanmaz."""
    g = cfg["gear"]
    ch = gear_char(gear, g["neutral"])
    if ch is None:
        if g["no_data"] == "dash":
            return glyph("-"), "Veri yok (çizgi)"
        return BLANK, "Veri yok (boş)"
    return custom_image(cfg, "gear_"+ch, glyph(ch)), "Vites: %s" % ch


FLAG_NAMES = {
    "blue":"Mavi", "green":"Yeşil", "yellow":"Sarı", "double_yellow":"Çift sarı",
    "white":"Beyaz", "warning":"Siyah-beyaz uyarı", "mechanical":"Mekanik arıza",
    "black":"Siyah", "pit":"Pit", "final":"Son tur", "red":"Kırmızı", "checkered":"Damalı"
}
# Tek renkli MAX7219 icin desenler. Renkli bayraklar sadece yazilim onizlemesinde tam renklidir.
FLAG_PATTERNS = {
    "blue": (0xFF,)*8,
    "green": (0xFF,)*8,
    "yellow": (0xFF,)*8,
    "double_yellow": (0xFF,0xFF,0xFF,0xFF,0x00,0x00,0xFF,0xFF),
    "white": (0xFF,)*8,
    "warning": (0xF0,0xF0,0xCC,0xCC,0x33,0x33,0x0F,0x0F),
    "mechanical": (0x00,0x18,0x3C,0x7E,0x7E,0x3C,0x18,0x00),
    "black": (0xFF,)*8,
    "pit": (0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00),
    "final": (0x81,0x42,0x24,0x18,0x18,0x24,0x42,0x81),
    "red": (0xFF,)*8,
    "checkered": (0xAA,0x55,0xAA,0x55,0xAA,0x55,0xAA,0x55),
}

def flag_preview_color(flag, row, col, colors):
    """8x8 RGB onizleme renkleri (tek renkli fiziksel MAX7219'a uygulanmaz)."""
    black, white = "#171717", "#ffffff"
    if flag == "checkered":
        return black if (row+col)%2 == 0 else white
    if flag == "double_yellow":
        return colors.get("double_yellow", "#ffcc00") if row < 2 or row >= 6 else (white if row < 4 else black)
    if flag == "mechanical":
        return colors.get("mechanical", "#ff8b18") if FLAG_PATTERNS[flag][row] & (1 << (7-col)) else black
    if flag == "final":
        return black if FLAG_PATTERNS[flag][row] & (1 << (7-col)) else colors.get("final", "#ffe500")
    if flag == "warning":
        return black if FLAG_PATTERNS[flag][row] & (1 << (7-col)) else white
    return colors.get(flag, "#ffffff")

def proximity_pattern(side):
    """Köşeli parantez: dış sütunda 8, üst/alt çıkıntılarda 1'er LED."""
    if side == "left":
        return (0xC0,) + (0x80,) * 6 + (0xC0,)
    if side == "right":
        return (0x03,) + (0x01,) * 6 + (0x03,)
    if side == "rear":
        return (0, 0, 0, 0, 0, 0, 0, 0xFF)
    if side == "both":
        return tuple(a | b for a, b in zip(proximity_pattern("left"), proximity_pattern("right")))
    return BLANK

def live_alerts(snap):
    """Yalnizca gercekten iletilen, acik olay alanlarini okur; veri yoksa uyari uydurmaz."""
    if not isinstance(snap,dict) or not snap.get("live") or not snap.get("valid", True):
        return None, None
    t = snap.get("t") or {}
    flag = t.get("led_flag", t.get("flag_name"))
    if isinstance(flag,str):
        flag = flag.lower().strip().replace(" ","_")
    if flag not in FLAG_PATTERNS: flag = None
    side = t.get("led_proximity", t.get("proximity"))
    if side not in ("left","right","both","rear"): side = None
    return flag,side

# Ayrı sürüş ayarı olayları. Yalnızca oyun tarafından bildirilen seviyeler kullanılır.
ADJUSTMENTS = {"tc":"TC", "abs":"ABS", "map":"MAP", "tc2":"TC2"}
ADJUSTMENT_FIELDS = {"tc":("tc_level","dcTractionControl"), "abs":("abs_level","dcABS"),
                     "map":("ecu_map","engine_map","dcEngineMap"),
                     "tc2":("tc2_level","tc2","dcTractionControl2")}

def adjustment_values(snap):
    if not isinstance(snap,dict) or not snap.get("live") or not snap.get("valid",True):
        return {}
    t = snap.get("t") or {}
    result = {}
    for key, names in ADJUSTMENT_FIELDS.items():
        for name in names:
            value = t.get(name)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and __import__('math').isfinite(value) and 0 <= value <= 100:
                result[key] = round(float(value),2)
                break
    return result

def adjustment_image(key, value):
    """8x8 matris: etiket olmadan yalnızca yeni tam sayı (BB desteklenmez)."""
    if key not in ADJUSTMENTS:
        raise ValueError("Desteklenmeyen LED araç ayarı: " + str(key))
    number = int(round(value))
    if number < 0 or number > 99:
        raise ValueError("LED ayar değeri 0-99 arasında olmalı")
    if number < 10:
        return glyph(str(number))
    # İki basamak, 3x5 piksel font; 1 sütun boşluk ve kenarlarda pay.
    digits = {
        "0": (7,5,5,5,7), "1": (2,6,2,2,7), "2": (7,1,7,4,7),
        "3": (7,1,7,1,7), "4": (5,5,7,1,1), "5": (7,4,7,1,7),
        "6": (7,4,7,5,7), "7": (7,1,2,2,2), "8": (7,5,7,5,7),
        "9": (7,5,7,1,7),
    }
    result = [0] * 8
    for i, digit in enumerate(str(number)):
        for r, bits in enumerate(digits[digit], start=2):
            result[r] |= bits << (4 if i == 0 else 0)
    return tuple(result)
