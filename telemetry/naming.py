"""Pist/arac dahili adlarini okunur hale getirir. Sadece bicimlendirme yapar, bilgi eklemez."""
import re

ACC_TRACKS = {
    "spa": "Spa-Francorchamps", "monza": "Monza", "misano": "Misano", "paul_ricard": "Circuit Paul Ricard",
    "brands_hatch": "Brands Hatch", "zandvoort": "Zandvoort", "zolder": "Zolder",
    "hungaroring": "Hungaroring", "barcelona": "Barcelona-Catalunya", "nurburgring": "Nürburgring GP",
    "silverstone": "Silverstone", "kyalami": "Kyalami", "mount_panorama": "Mount Panorama",
    "suzuka": "Suzuka", "laguna_seca": "Laguna Seca", "imola": "Imola", "oulton_park": "Oulton Park",
    "donington": "Donington Park", "snetterton": "Snetterton", "cota": "Circuit of the Americas",
    "indianapolis": "Indianapolis", "watkins_glen": "Watkins Glen", "valencia": "Valencia",
    "red_bull_ring": "Red Bull Ring", "nurburgring_24h": "Nürburgring 24h",
}

_UPPER = {"gt3", "gt4", "gt2", "gte", "gtd", "gtp", "lmp1", "lmp2", "lmp3", "lmh", "lmdh", "bmw", "amg",
          "drs", "ks", "cup", "evo", "rs", "wrc", "f1", "f3", "tcr", "ai", "usa", "uk", "gp"}
_BRAND = {"amr": "Aston Martin", "mclaren": "McLaren", "mercedes": "Mercedes", "porsche": "Porsche",
          "ferrari": "Ferrari", "lamborghini": "Lamborghini", "audi": "Audi"}


def pretty_id(raw, drop_ks=True):
    """'ferrari_296_gt3' -> 'Ferrari 296 GT3'"""
    if not raw:
        return None
    s = raw.strip()
    if drop_ks and s.lower().startswith("ks_"):
        s = s[3:]
    toks = [t for t in re.split(r"[_\s\-]+", s) if t]
    out = []
    for t in toks:
        low = t.lower()
        if low in _UPPER and low != "ks":
            out.append(low.upper())
        elif low in _BRAND:
            out.append(_BRAND[low])
        elif re.fullmatch(r"\d+[a-z]*", low):
            out.append(t.upper() if len(t) <= 4 and not t.isdigit() else t)
        else:
            out.append(t[:1].upper() + t[1:])
    return " ".join(out)


def clean_text(s, maxlen=64):
    """Oyundan gelen ad gecerli/yazdirilabilir degilse None."""
    if s is None:
        return None
    s = s.strip().strip("\x00")
    if not s or len(s) > maxlen:
        return None
    if any((ord(c) < 32 or ord(c) == 0xFFFD) for c in s):
        return None
    return s
