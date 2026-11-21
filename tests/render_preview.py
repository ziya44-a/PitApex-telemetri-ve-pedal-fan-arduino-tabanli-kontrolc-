"""Gelistirici araci: _draw_vehicle'in kaydettigi tuval ogelerini PIL ile cizip PNG onizleme uretir.
Gercek Tk goruntusu DEGILDIR (yazi tipi/yumusatma farkli); ayni cizim kodunun yerlesimini dogrulamak icindir.
Kullanim:  python3 tests/render_preview.py cikti.png"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
try:
    import tkinter  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.join(HERE, "fake_tk"))

from unittest import mock  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from core.models import TelemetryFrame  # noqa: E402
from tests import rich_fake_tk as rtk  # noqa: E402
from tests.test_overlay import FakeApp  # noqa: E402
from ui import overlays_page as op  # noqa: E402

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
FONTS_B = [f.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") for f in FONTS]


def font(pt, bold):
    for p in (FONTS_B if bold else FONTS):
        if os.path.exists(p):
            return ImageFont.truetype(p, max(6, int(round(pt * 96 / 72))))
    return ImageFont.load_default()


def hexrgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def raster(canvas, key_hex):
    """Tuval ogelerini seffaf RGBA'ya cizer (tuval zemini = anahtar renk -> seffaf)."""
    img = Image.new("RGBA", (canvas.w, canvas.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if canvas.cfg.get("bg") != key_hex:
        d.rectangle([0, 0, canvas.w, canvas.h], fill=hexrgb(canvas.cfg["bg"]) + (255,))
    for kind, a, k in canvas.items:
        if kind == "rect":
            fill, out = k.get("fill"), k.get("outline")
            d.rectangle(a, fill=hexrgb(fill) + (255,) if fill else None,
                        outline=hexrgb(out) + (255,) if out else None, width=int(k.get("width", 1)))
        elif kind == "line":
            d.line(a, fill=hexrgb(k.get("fill", "#ffffff")) + (255,), width=int(k.get("width", 1)))
        elif kind == "poly":
            d.polygon(a, fill=hexrgb(k["fill"]) + (255,) if k.get("fill") else None,
                      outline=hexrgb(k["outline"]) + (255,) if k.get("outline") else None)
        elif kind == "text":
            fam, pt, *rest = k["font"]
            f = font(pt, "bold" in rest)
            anchor = {"w": "lm", "e": "rm", "center": "mm"}.get(k.get("anchor", "w"), "lm")
            d.text((a[0], a[1]), k["text"], fill=hexrgb(k["fill"]) + (255,), font=f, anchor=anchor)
        elif kind == "image":
            ph = Image.open(k["image"].file).convert("RGBA")
            img.alpha_composite(ph, (int(a[0]), int(a[1])))
    return img


def scene(w, h):
    """Oyun gorunumunu taklit eden degisken arka plan (seffaflik etkisi gorulsun diye)."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            band = 90 + int(70 * ((x // 40 + y // 40) % 2))
            px[x, y] = (60 + band // 3, 110 + band // 4, 70 + band // 5) if y > h * 0.45 else (90 + band // 3, 120 + band // 3, 170)
    return img


def render(key, frame, transparency, size=None):
    with mock.patch.object(op, "tk", rtk), mock.patch.object(op.sys, "platform", "win32"):
        app = FakeApp()
        mgr = op.OverlayManager(app)
        mgr.set_transparency(key, transparency)
        mgr.open(key)
        w = mgr.windows[key]
        if size:
            w.canvas.w, w.canvas.h = size
        w.update(frame, True)
        fg = raster(w.canvas, op.TRANSPARENT_KEY)
        alpha = w.background.attrs["-alpha"] if w.background is not None else 1.0
    bgimg = scene(*fg.size).convert("RGBA")
    back = Image.new("RGBA", fg.size, hexrgb(op.BACKDROP_COLOR) + (int(255 * alpha),))
    bgimg.alpha_composite(back)
    bgimg.alpha_composite(fg)
    return bgimg.convert("RGB")


def main(out):
    base = dict(game="ACC", live=True, tyre_temp_c=[82.0, 84.0, 79.0, 80.0], tyre_press_kpa=[190.0, 191.0, 185.0, 186.0],
                fuel_l=41.5)
    f_unknown = TelemetryFrame(**base)
    f_damage = TelemetryFrame(**base, body_damage={"front": 3.2, "rear": 0.0, "left": 0.0, "right": 1.4, "center": 0.0},
                              wheel_damage=[0.0, 2.0, 0.0, 0.0])
    f_clean = TelemetryFrame(**base, body_damage=dict.fromkeys(("front", "rear", "left", "right", "center"), 0.0),
                             wheel_damage=[0.0] * 4)
    shots = [render("tyres", f_damage, 0), render("tyres", f_damage, 60), render("tyres", f_unknown, 60),
             render("tyres", f_clean, 85)]
    W, H = shots[0].size
    sheet = Image.new("RGB", (W * 2 + 10, H * 2 + 10), (255, 255, 255))
    for i, s in enumerate(shots):
        sheet.paste(s, ((i % 2) * (W + 10), (i // 2) * (H + 10)))
    sheet.save(out)
    print("yazildi:", out, sheet.size)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "overlay_preview.png")
