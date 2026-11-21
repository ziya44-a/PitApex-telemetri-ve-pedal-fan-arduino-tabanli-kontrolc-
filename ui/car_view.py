"""Araç Durumu overlay'i için araç görseli ve hasar renklendirmesi (çizimden bağımsız, test edilebilir mantık).

Kurallar:
 * Renk hasarla kademeli değişir: yeşil (hasarsız) -> sarı -> turuncu -> kırmızı (tamamen kırık).
   Kademe = ham değer / *_DAMAGE_FULL (0..1 arası kırpılır), 9 hazır kademeye (s0..s8) yuvarlanır.
 * Oyun hasar verisi vermiyorsa bölge BOYANMAZ (nötr kalır): bilinmeyen bölge asla "sağlam" gösterilmez.
 * Görseller assets/car altında önceden ölçeklenmiş PNG'lerdir (tools/build_car_assets.py üretir);
   çalışma anında Pillow gerekmez, yalnızca tk.PhotoImage kullanılır."""
import colorsys
import json
import os

from storage.paths import resource_path

ZONES = ("front", "rear", "left", "right", "center")
ZONE_LABELS = {"front": "Ön", "rear": "Arka", "left": "Sol", "right": "Sağ", "center": "Orta"}
WHEEL_KEYS = ("fl", "fr", "rl", "rr")                # telemetri sırası: SolÖn, SağÖn, SolArka, SağArka
DAMAGE_EPS = 0.1                                      # bu değerin altı/eşiti "hasarsız" (ham oyun biriminde)
# "Tamamen kırık" sayılan ham değer: bu değer ve üstü tam kırmızı. DOĞRULANMADI - oyunun gerçek tavan değerine göre
# ayarla (alt şeritteki ham değerlere bak). Daha küçük yaparsan renk daha çabuk kırmızıya döner.
BODY_DAMAGE_FULL = 100.0
SUSP_DAMAGE_FULL = 100.0
PULL_WARN_LEVEL = 4                                   # bu kademe ve üstü: tekerlek/aks ciddi hasarlı -> "çekiş" uyarısı (DOĞRULANMADI)
KPA_TO_PSI = 1 / 6.894757
STEPS = 9                                             # build_car_assets.STEPS ile aynı olmalı (s0..s8)
_HUE_GREEN, _HUE_RED, _SAT, _VAL = 140.0, 0.0, 0.86, 1.0     # build_car_assets ile aynı olmalı
NEUTRAL = "#8e9aaa"


def gradient_rgb(t):
    """t: 0 (yeşil) .. 1 (kırmızı). Sabit canlı doygunluk/parlaklıkta ton kaydırma (limon/sarı/turuncu üzerinden, çamur yok);
    tools/build_car_assets.step_color ile AYNI formül."""
    t = max(0.0, min(1.0, float(t)))
    h = (_HUE_GREEN + (_HUE_RED - _HUE_GREEN) * t) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, _SAT, _VAL)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


RED = "#%02x%02x%02x" % gradient_rgb(1.0)
GREEN = "#%02x%02x%02x" % gradient_rgb(0.0)


def level_color(level):
    """Kademe (0..STEPS-1) -> '#rrggbb'; None (veri yok) -> nötr gri."""
    if level is None:
        return NEUTRAL
    return "#%02x%02x%02x" % gradient_rgb(level / float(STEPS - 1))


def damage_level(value, full=BODY_DAMAGE_FULL, eps=DAMAGE_EPS):
    """None (veri yok) | 0 (hasarsız, yeşil) .. STEPS-1 (tamamen kırık, kırmızı).
    Eşiğin üstündeki herhangi bir hasar en az 1. kademe olur (ilk hasar gözle görülsün)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    if v <= eps:
        return 0
    t = min(1.0, v / float(full))
    return max(1, int(round(t * (STEPS - 1))))


def zone_levels(body_damage):
    if not isinstance(body_damage, dict):
        return {z: None for z in ZONES}
    return {z: damage_level(body_damage.get(z), BODY_DAMAGE_FULL) for z in ZONES}


def wheel_levels(wheel_damage):
    try:
        vals = list(wheel_damage)
    except TypeError:
        return [None] * 4
    if len(vals) != 4:
        return [None] * 4
    return [damage_level(v, SUSP_DAMAGE_FULL) for v in vals]


def color_of(level):
    return level_color(level)


WHEEL_NAMES = {"fl": "SOL ÖN", "fr": "SAĞ ÖN", "rl": "SOL ARKA", "rr": "SAĞ ARKA"}


def kpa_to_psi(kpa):
    try:
        v = float(kpa)
    except (TypeError, ValueError):
        return None
    return None if v != v else v * KPA_TO_PSI


def wheel_warning(key, level):
    """Tek tekerlek için kart uyarısı (None = uyarı yok). Ön tekerlek bozuksa araç o tarafa çeker (hasarlı tarafa; tahmin),
    arka tekerlekte yön değil kararsızlık bildirilir. Telemetride gerçek 'çekiş' sinyali yok: hasar seviyesinden türetilir."""
    if level is None or level < PULL_WARN_LEVEL:
        return None
    front = key in ("fl", "fr")
    side = "SOLA" if key in ("fl", "rl") else "SAĞA"
    if front:
        return ("KIRIK: " if level >= STEPS - 1 else "") + side + " ÇEKER"
    return "ARKA KARARSIZ" if level < STEPS - 1 else "KIRIK: ARKA KARARSIZ"


def pull_banner(levels):
    """Üst şerit uyarısı: None | 'SAĞ ÖN KIRIK · SAĞA ÇEKER' | 'SOL ÖN HASARLI · SOLA ÇEKER' | '2 TEKERLEK HASARLI'."""
    bad = [(k, lv) for k, lv in zip(WHEEL_KEYS, levels) if lv is not None and lv >= PULL_WARN_LEVEL]
    if not bad:
        return None
    if len(bad) > 1:
        return "%d TEKERLEK HASARLI" % len(bad)
    k, lv = bad[0]
    state = "KIRIK" if lv >= STEPS - 1 else "HASARLI"
    w = wheel_warning(k, lv)
    return "%s %s · %s" % (WHEEL_NAMES[k], state, w.replace("KIRIK: ", ""))


def summary_text(body_damage):
    """Alt şerit için ham değerler: 'Ön 0.0 · Arka 3.2 ...' (yüzde uydurulmaz)."""
    if not isinstance(body_damage, dict):
        return None
    parts = []
    for z in ZONES:
        v = body_damage.get(z)
        parts.append("%s %s" % (ZONE_LABELS[z], "—" if v is None else "%.1f" % v))
    return " · ".join(parts)


class CarAssets:
    """Önceden ölçeklenmiş araç PNG'lerini yükler/önbelleğe alır. Dosya yoksa ya da Tk açamazsa
    available=False olur ve çağıran taraf poligon çizime döner."""

    def __init__(self, photo_factory, base_dir=None):
        self.photo_factory = photo_factory
        self.dir = base_dir or resource_path("assets", "car")
        self.cache = {}
        self.broken = set()
        self.meta = None
        try:
            with open(os.path.join(self.dir, "car_meta.json"), "r", encoding="utf-8") as f:
                meta = json.load(f)
            sizes = sorted((int(h), int(w)) for h, w in meta["sizes"])
            wheels = {k: [float(x) for x in meta["wheels"][k]] for k in WHEEL_KEYS}
            self.meta = {"sizes": sizes, "wheels": wheels, "aspect": float(meta["aspect"])}
        except (OSError, ValueError, KeyError, TypeError):
            self.meta = None

    @property
    def available(self):
        return self.meta is not None

    @property
    def aspect(self):
        return self.meta["aspect"] if self.meta else None

    def pick_height(self, max_h):
        """max_h sığan en büyük hazır yükseklik; hiçbiri sığmıyorsa en küçüğü."""
        if not self.meta:
            return None
        fit = [h for h, _w in self.meta["sizes"] if h <= max_h]
        return max(fit) if fit else self.meta["sizes"][0][0]

    def width_for(self, h):
        for hh, ww in self.meta["sizes"]:
            if hh == h:
                return ww
        return None

    def photo(self, h, name):
        key = (h, name)
        if key in self.cache:
            return self.cache[key]
        if key in self.broken:
            return None
        path = os.path.join(self.dir, "car_%d_%s.png" % (h, name))
        try:
            ph = self.photo_factory(path)
        except Exception:                      # dosya yok / Tk PNG açamadı
            self.broken.add(key)
            return None
        self.cache[key] = ph
        return ph


def draw_car(canvas, assets, cx, top, max_h, body_damage=None, wheel_damage=None):
    """Aracı canvas'a çizer. cx: yatay orta, top: üst kenar, max_h: sığabileceği yükseklik (piksel).
    Başarılıysa {'rect': (x0,y0,x1,y1), 'wheels': {anahtar: (x0,y0,x1,y1)}}, değilse None."""
    if assets is None or not assets.available:
        return None
    h = assets.pick_height(max_h)
    base = assets.photo(h, "base") if h else None
    if base is None:
        return None
    w = assets.width_for(h)
    x0, y0 = cx - w / 2.0, top
    canvas.create_image(x0, y0, image=base, anchor="nw")
    for zone, level in zone_levels(body_damage).items():
        if level is not None:
            ph = assets.photo(h, "%s_s%d" % (zone, level))
            if ph is not None:
                canvas.create_image(x0, y0, image=ph, anchor="nw")
    wheels = {}
    for key, st in zip(WHEEL_KEYS, wheel_levels(wheel_damage)):
        a, b, c, d = assets.meta["wheels"][key]
        box = (x0 + a * w, y0 + b * h, x0 + c * w, y0 + d * h)
        wheels[key] = box
        if st is not None:                     # tekerlek: renkli çerçeve (veri yoksa çizilmez)
            canvas.create_rectangle(*box, outline=color_of(st), width=3)
    return {"rect": (x0, y0, x0 + w, y0 + h), "wheels": wheels}
