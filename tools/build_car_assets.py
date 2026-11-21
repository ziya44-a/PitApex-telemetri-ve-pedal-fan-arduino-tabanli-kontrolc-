"""Araç Durumu overlay'i için görselleri hazırlar (SADECE geliştirici aracı; çalışma anında Pillow gerekmez).

Kaynak: tools/car_source/pitapex_gt_top_source.png (üstten görünüm, ön YUKARIDA, arka kanat AŞAĞIDA, siyah zemin)
Çıktı : assets/car/car_<yükseklik>_base.png               siyah zemin şeffaflaştırılmış araç
        assets/car/car_<yükseklik>_<bölge>_s<0..8>.png      bölge boyaması (yarı saydam); s0 = yeşil (sağlam), s8 = kırmızı (tam hasar)
        assets/car/car_meta.json                           boyutlar, bölgeler, tekerlek konumları

Çalıştırma:  py tools/build_car_assets.py        (Pillow + numpy + scipy gerekir)
Bölge sınırlarını değiştirmek için aşağıdaki sabitleri düzenleyip yeniden çalıştır."""
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets", "car")
SOURCE = os.path.join(HERE, "car_source", "pitapex_gt_top_source.png")   # EXE'ye girmez

SIZES = (280, 380, 500, 640, 800)          # üretilecek araç yükseklikleri (piksel)
OVERLAY_ALPHA = 0.88                        # bölge katmanı opaklığı: araç bölge içinde yeniden boyanır (detay korunur)
KEY_RGB = (21, 21, 21)                      # overlay'in saydam anahtar rengi (#151515): görselde birebir bu renk OLMAMALI (delinir)
STEPS = 9                                   # yeşilden kırmızıya kademe sayısı (s0 = yeşil ... s8 = kırmızı)
HUE_GREEN, HUE_RED, SAT, VAL = 140.0, 0.0, 0.86, 1.0


def step_color(i, steps=STEPS):
    """Canlı yeşil -> limon -> sarı -> turuncu -> kırmızı: sabit doygunluk/parlaklıkta ton (hue) kaydırma (çamur/kahve yok).
    (ui/car_view.py içindeki gradient_rgb ile AYNI formül olmalı.)"""
    t = max(0.0, min(1.0, i / float(steps - 1)))
    h = (HUE_GREEN + (HUE_RED - HUE_GREEN) * t) / 360.0
    r, g, b = colorsys.hsv_to_rgb(h, SAT, VAL)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


RED, GREEN = step_color(STEPS - 1), step_color(0)


def recolor(rgb, tint):
    """Aracın kendi gölge/parlama detayını koruyarak 'tint' renginde yeniden boyar (düz saydam renk katmanı çamur gibi duruyordu)."""
    f = rgb.astype(float) / 255.0
    luma = 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]
    shade = 0.40 + 0.85 * np.clip(luma, 0, 1) ** 0.7
    out = np.array(tint, float)[None, None, :] * shade[..., None]
    spec = (np.clip((luma - 0.65) / 0.35, 0, 1) * 0.55)[..., None]      # parlak yansımalar beyaza kayar
    out = out * (1 - spec) + 255.0 * spec
    return np.clip(out, 0, 255).astype("uint8")


def sanitize_key(rgb):
    """Anahtar renge (±2) çok yakın pikselleri 3 birim açar: aksi halde tekerlek/gövde karası şeffaf delik olarak görünür."""
    near = np.all(np.abs(rgb.astype(int) - np.array(KEY_RGB)[None, None, :]) <= 2, axis=2)
    out = rgb.copy()
    out[near] = (KEY_RGB[0] + 4,) * 3
    return out


# --- kaynak görsel koordinatları (1024x1536) ---
BG_THRESHOLD = 3                            # siyah zemin 0-1; araç detayları bunun üstünde
Y_FRONT = 475                               # bunun üstü: ön bölge (kaput, burun, ön çamurluklar)
Y_REAR = 905                                # bunun altı: arka bölge (motor kapağı, arka çamurluklar, kanat)
CENTER_POLY = [(318, 475), (706, 475), (726, 610), (662, Y_REAR), (362, Y_REAR), (298, 610)]   # kabin/tavan
WHEELS = {                                  # tekerlek kutuları (x0, y0, x1, y1), sırayla: SolÖn, SağÖn, SolArka, SağArka
    "fl": (216, 328, 286, 540), "fr": (736, 328, 804, 540),
    "rl": (216, 980, 290, 1200), "rr": (732, 980, 804, 1200),
}
ZONES = ("front", "rear", "left", "right", "center")
GAP = 3                                     # bölgeler arası görünür ince ayrım (px)


def silhouette(rgb):
    mx = rgb.max(axis=2)
    m = mx > BG_THRESHOLD
    m = ndi.binary_closing(m, structure=np.ones((3, 3)), iterations=4)
    m = ndi.binary_fill_holes(m)
    m = ndi.binary_opening(m, structure=np.ones((3, 3)), iterations=1)
    lab, n = ndi.label(m)
    if n > 1:                                # en büyük parça = araç
        sizes = ndi.sum(m, lab, range(1, n + 1))
        m = lab == (1 + int(np.argmax(sizes)))
    return m


def zone_masks(sil, h, w):
    yy, xx = np.mgrid[0:h, 0:w]
    poly = Image.new("L", (w, h), 0)
    ImageDraw.Draw(poly).polygon(CENTER_POLY, fill=255)
    in_center = np.array(poly) > 0
    wheel = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in WHEELS.values():
        wheel[y0:y1, x0:x1] = True
    body = sil & ~wheel
    mid = (yy >= Y_FRONT) & (yy < Y_REAR)
    masks = {
        "front": body & (yy < Y_FRONT),
        "rear": body & (yy >= Y_REAR),
        "center": body & mid & in_center,
        "left": body & mid & ~in_center & (xx < w // 2),
        "right": body & mid & ~in_center & (xx >= w // 2),
    }
    out = {}
    for k, m in masks.items():              # bölgeleri hafif küçült: aralarında ince çizgi kalsın
        out[k] = ndi.binary_erosion(m, structure=np.ones((3, 3)), iterations=GAP) if GAP else m
    return out


def feather(mask, radius=1.2):
    img = Image.fromarray((mask * 255).astype("uint8"))
    return np.array(img.filter(ImageFilter.GaussianBlur(radius))).astype(float) / 255.0


def main():
    src = Image.open(SOURCE).convert("RGB")
    rgb = np.array(src)
    h, w, _ = rgb.shape
    sil = silhouette(rgb)
    ys, xs = np.where(sil)
    pad = 4
    x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + 1 + pad)
    print("araç sınırı:", (x0, y0, x1, y1), "silüet alanı %.1f%%" % (100 * sil.mean()))

    alpha = feather(ndi.binary_erosion(sil, structure=np.ones((3, 3)), iterations=1), 1.0)
    rgb = sanitize_key(rgb)
    base = np.dstack([rgb, (alpha * 255).astype("uint8")])
    zones = zone_masks(sil, h, w)

    os.makedirs(ASSETS, exist_ok=True)
    for f in os.listdir(ASSETS):
        if f.startswith("car_") and f.endswith(".png"):
            os.remove(os.path.join(ASSETS, f))
    cw, ch = x1 - x0, y1 - y0
    meta = {"source_crop": [int(x0), int(y0), int(x1), int(y1)], "aspect": cw / ch, "sizes": [], "zones": list(ZONES),
            "wheels": {k: [(a - x0) / cw, (b - y0) / ch, (c - x0) / cw, (d - y0) / ch] for k, (a, b, c, d) in WHEELS.items()},
            "damage_eps": 0.1, "steps": STEPS}
    for H in SIZES:
        W = int(round(H * cw / ch))
        meta["sizes"].append([H, W])
        bimg = Image.fromarray(base[y0:y1, x0:x1], "RGBA").convert("RGBa").resize((W, H), Image.LANCZOS).convert("RGBA")
        barr = np.array(bimg)
        barr[..., :3] = sanitize_key(barr[..., :3])
        Image.fromarray(barr).save(os.path.join(ASSETS, "car_%d_base.png" % H), optimize=True)
        crop_rgb = rgb[y0:y1, x0:x1]
        for i in range(STEPS):
            colored = recolor(crop_rgb, step_color(i))
            for z in ZONES:
                fm = feather(zones[z])[y0:y1, x0:x1] * alpha[y0:y1, x0:x1].clip(0, 1)
                a = (fm * 255 * OVERLAY_ALPHA).astype("uint8")
                img = Image.fromarray(np.dstack([colored, a]), "RGBA").convert("RGBa")      # premultiplied: kenarda koyu halka olmasın
                img = img.resize((W, H), Image.LANCZOS).convert("RGBA")
                arr = np.array(img)
                arr[..., :3] = sanitize_key(arr[..., :3])
                Image.fromarray(arr).save(os.path.join(ASSETS, "car_%d_%s_s%d.png" % (H, z, i)), optimize=True)
    with open(os.path.join(ASSETS, "car_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    total = sum(os.path.getsize(os.path.join(ASSETS, f)) for f in os.listdir(ASSETS) if f.startswith("car_"))
    print("üretilen dosya: %d, toplam %.0f KB" % (len([f for f in os.listdir(ASSETS) if f.startswith("car_")]), total / 1024))

    # --- kontrol görseli: her bölge farklı renkte + tekerlek kutuları ---
    prev = Image.open(os.path.join(ASSETS, "car_640_base.png")).convert("RGBA")
    bg = Image.new("RGBA", prev.size, (21, 21, 21, 255))
    bg.alpha_composite(prev)
    for z, c in zip(ZONES, ("s8", "s0", "s6", "s2", "s4")):
        bg.alpha_composite(Image.open(os.path.join(ASSETS, "car_640_%s_%s.png" % (z, c))).convert("RGBA"))
    d = ImageDraw.Draw(bg)
    for k, (a, b, c2, dd) in meta["wheels"].items():
        d.rectangle([a * bg.width, b * bg.height, c2 * bg.width, dd * bg.height], outline=(255, 255, 0), width=2)
    bg.convert("RGB").save(os.path.join("/tmp", "car_debug.png"))


if __name__ == "__main__":
    sys.exit(main())
