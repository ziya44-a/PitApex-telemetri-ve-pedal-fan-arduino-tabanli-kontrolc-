"""Lastik sıcaklığı renklendirmesi: kuru ve ıslak için AYRI aralıklar, hangisinin uygulanacağı otomatik seçilir.

Her profil 4 sayıdır (°C):  cold < opt_min < opt_max < hot
  * cold ve altı  -> mavi (çok soğuk)
  * opt_min..opt_max -> yeşil (ideal pencere)
  * hot ve üstü   -> kırmızı (aşırı sıcak)
  * aradaki değerler renkler arasında yumuşak geçiş yapar (mavi→yeşil, yeşil→kırmızı).

Hangi profil: mod "auto" ise oyunun GERÇEK lastik tipi bilgisi (frame.tyre_wet) kullanılır; oyun bilgi vermiyorsa
(None) tahmin edilmez, kullanıcının seçtiği yedek profil (varsayılan: kuru) uygulanır ve bu etikette açıkça yazılır.

Varsayılan değerler yalnızca başlangıç içindir, DOĞRULANMIŞ ideal değerler değildir: araç/lastik/oyuna göre ayarla."""
import colorsys

MODES = ("auto", "dry", "wet")
MODE_LABELS = {"auto": "Otomatik", "dry": "Hep kuru", "wet": "Hep ıslak"}
FALLBACKS = ("dry", "wet")                 # oyun lastik tipini vermezse kullanılacak profil
KEYS = ("cold", "opt_min", "opt_max", "hot")
KEY_LABELS = {"cold": "Soğuk altı (mavi)", "opt_min": "İdeal en düşük", "opt_max": "İdeal en yüksek",
              "hot": "Sıcak üstü (kırmızı)"}
LIMITS = (-20.0, 300.0)

DEFAULT_RANGES = {
    "dry": {"cold": 60.0, "opt_min": 80.0, "opt_max": 95.0, "hot": 110.0},
    "wet": {"cold": 40.0, "opt_min": 55.0, "opt_max": 75.0, "hot": 90.0},
}
COLD_RGB, OPT_RGB, HOT_RGB = (46, 170, 255), (36, 255, 109), (255, 36, 36)      # canlı mavi / yeşil / kırmızı (hasar renkleriyle uyumlu)
NEUTRAL = "#8e9aaa"


def validate(profile):
    """profile -> temiz {'cold','opt_min','opt_max','hot'} sözlüğü ya da ValueError (Türkçe mesajla)."""
    try:
        vals = {k: float(profile[k]) for k in KEYS}
    except (KeyError, TypeError, ValueError):
        raise ValueError("Dört değerin de sayı olması gerekir")
    for k, v in vals.items():
        if v != v or not (LIMITS[0] <= v <= LIMITS[1]):
            raise ValueError("%s: %d–%d °C arasında olmalı" % (KEY_LABELS[k], LIMITS[0], LIMITS[1]))
    if not (vals["cold"] < vals["opt_min"] < vals["opt_max"] < vals["hot"]):
        raise ValueError("Sıra şöyle olmalı: soğuk < ideal en düşük < ideal en yüksek < sıcak")
    return vals


def normalize_config(raw):
    """Kayıtlı ayarı güvenli hale getirir; bozuk/eksik parça varsayılana döner. -> {'mode','fallback','ranges'}"""
    raw = raw if isinstance(raw, dict) else {}
    mode = raw.get("mode") if raw.get("mode") in MODES else "auto"
    fallback = raw.get("fallback") if raw.get("fallback") in FALLBACKS else "dry"
    ranges = {}
    saved = raw.get("ranges") if isinstance(raw.get("ranges"), dict) else {}
    for name in ("dry", "wet"):
        try:
            ranges[name] = validate(saved.get(name))
        except ValueError:
            ranges[name] = dict(DEFAULT_RANGES[name])
    return {"mode": mode, "fallback": fallback, "ranges": ranges}


def resolve_profile(config, wet):
    """-> (profil_adı 'dry'|'wet', otomatik_mi, oyun_bilgisi_var_mı). wet: True/False (oyundan) ya da None (bilinmiyor)."""
    mode = config.get("mode", "auto")
    if mode in ("dry", "wet"):
        return mode, False, wet is not None
    if wet is None:
        return config.get("fallback", "dry"), True, False
    return ("wet" if wet else "dry"), True, True


def profile_label(config, wet):
    """Üst şerit etiketi: 'LASTİK: KURU (oto) · ideal 80–95 °C' ya da '... (oyun tipi vermiyor, varsayılan)'."""
    name, auto, known = resolve_profile(config, wet)
    r = config["ranges"][name]
    tag = ("(oto)" if known else "(oyun tipi vermiyor)") if auto else "(elle)"
    return "LASTİK: %s %s · ideal %d–%d °C" % ("ISLAK" if name == "wet" else "KURU", tag, round(r["opt_min"]), round(r["opt_max"]))


def _mix(a, b, t):
    # HSV'de ton interpolasyonu: mavi→yeşil→kırmızı geçişleri çamurlaşmaz
    ha, sa, va = colorsys.rgb_to_hsv(*[c / 255.0 for c in a])
    hb, sb, vb = colorsys.rgb_to_hsv(*[c / 255.0 for c in b])
    h = ha + (hb - ha) * t
    r, g, bl = colorsys.hsv_to_rgb(h, sa + (sb - sa) * t, va + (vb - va) * t)
    return int(round(r * 255)), int(round(g * 255)), int(round(bl * 255))


def temp_rgb(temp, r):
    t = float(temp)
    if t <= r["cold"]:
        return COLD_RGB
    if t < r["opt_min"]:
        return _mix(COLD_RGB, OPT_RGB, (t - r["cold"]) / (r["opt_min"] - r["cold"]))
    if t <= r["opt_max"]:
        return OPT_RGB
    if t < r["hot"]:
        return _mix(OPT_RGB, HOT_RGB, (t - r["opt_max"]) / (r["hot"] - r["opt_max"]))
    return HOT_RGB


def temp_color(temp, r):
    """°C -> '#rrggbb'; veri yok/geçersiz -> nötr gri."""
    try:
        t = float(temp)
    except (TypeError, ValueError):
        return NEUTRAL
    if t != t or t in (float("inf"), float("-inf")):
        return NEUTRAL
    return "#%02x%02x%02x" % temp_rgb(t, r)


def temp_status(temp, r):
    """'SOĞUK' | 'İDEAL' | 'SICAK' | None (veri yok). Sadece ham eşiklere göre; ara geçiş bölgeleri en yakın uca yazılır."""
    try:
        t = float(temp)
    except (TypeError, ValueError):
        return None
    if t != t:
        return None
    if t < r["opt_min"]:
        return "SOĞUK"
    if t > r["opt_max"]:
        return "SICAK"
    return "İDEAL"
