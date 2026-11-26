"""Generates the ECM Launcher logos (no external artwork, pure Pillow).

Output
  assets/logo/applogo/app_icon.png          launcher / exe icon (isometric voxel cube)
  assets/logo/applogo/app_icon.ico          multi-size Windows icon used by builder.bat
  assets/logo/clientlogo/client_logo.png    ECM Client mark (slanted "E" in a shield)
  assets/logo/clientlogo/client_banner.png  mark + wordmark

Run:  python tools/make_logos.py
Edit the colours below to re-skin the launcher's identity.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "assets" / "logo" / "applogo"
CLIENT_DIR = ROOT / "assets" / "logo" / "clientlogo"

GLACIER = (92, 230, 240)
AMETHYST = (139, 108, 246)
INDIGO = (58, 42, 160)
INK = (11, 14, 23)
INK2 = (20, 26, 46)


def gradient(size, c1, c2, vertical=False):
    """Diagonal (or vertical) two-colour gradient as an RGB image."""
    w, h = size
    small = Image.new("L", (64, 64))
    px = small.load()
    for y in range(64):
        for x in range(64):
            t = y / 63 if vertical else (x + y) / 126
            px[x, y] = int(t * 255)
    mask = small.resize((w, h), Image.BILINEAR)
    return Image.composite(Image.new("RGB", size, c2), Image.new("RGB", size, c1), mask)


def paste_poly(canvas, points, fill_img):
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    canvas.paste(fill_img, (0, 0), mask)


def star(draw, cx, cy, r, fill):
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rad = r if i % 2 == 0 else r * 0.22
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    draw.polygon(pts, fill=fill)


# --------------------------------------------------------------------------- app icon
def make_app_icon(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = int(size * 0.22)

    tile = gradient((size, size), INK2, INK, vertical=True).convert("RGBA")
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    img.paste(tile, (0, 0), m)

    # gradient rim light
    rim = gradient((size, size), GLACIER, AMETHYST).convert("RGBA")
    ring = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(ring)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    d.rounded_rectangle((size * 0.012, size * 0.012, size * 0.988, size * 0.988),
                        radius=int(size * 0.21), fill=0)
    img.paste(rim, (0, 0), ring)

    cx, cy, R = size * 0.5, size * 0.53, size * 0.31
    k = math.cos(math.radians(30))
    top = (cx, cy - R)
    ur = (cx + R * k, cy - R / 2)
    lr = (cx + R * k, cy + R / 2)
    bot = (cx, cy + R)
    ll = (cx - R * k, cy + R / 2)
    ul = (cx - R * k, cy - R / 2)
    ctr = (cx, cy)

    # glow behind the cube
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - R * 1.1, cy - R * 1.1, cx + R * 1.1, cy + R * 1.1),
                                 fill=GLACIER + (110,))
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.07))
    img = Image.alpha_composite(img, glow)

    cube = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    faces = [
        ([top, ur, ctr, ul], gradient((size, size), (170, 250, 255), GLACIER, vertical=True)),
        ([ul, ctr, bot, ll], gradient((size, size), AMETHYST, (96, 66, 214), vertical=True)),
        ([ctr, ur, lr, bot], gradient((size, size), (74, 52, 190), INDIGO, vertical=True)),
    ]
    for pts, fill in faces:
        paste_poly(cube, pts, fill)

    # voxel seams: midlines on every face
    seam = ImageDraw.Draw(cube)
    w = max(3, int(size * 0.008))

    def mid(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    for a, b, c, dd in [(top, ur, ctr, ul), (ul, ctr, bot, ll), (ctr, ur, lr, bot)]:
        seam.line([mid(a, b), mid(dd, c)], fill=INK + (200,), width=w)
        seam.line([mid(b, c), mid(a, dd)], fill=INK + (200,), width=w)

    # bitten corner: a small cube removed from the upper-right edge
    bite = R * 0.34
    bx, by = ur[0] - bite * 0.15, ur[1] + bite * 0.15
    bpts = [(bx, by - bite * 0.6), (bx + bite * k * 0.9, by - bite * 0.15),
            (bx, by + bite * 0.3), (bx - bite * k * 0.9, by - bite * 0.15)]
    ImageDraw.Draw(cube).polygon(bpts, fill=(0, 0, 0, 0))
    img = Image.alpha_composite(img, cube)

    d = ImageDraw.Draw(img)
    d.line([top, ur, lr, bot, ll, ul, top], fill=(255, 255, 255, 60),
           width=max(2, int(size * 0.006)), joint="curve")
    star(d, size * 0.79, size * 0.2, size * 0.075, (255, 255, 255, 255))
    return img


# --------------------------------------------------------------------------- client mark
def make_client_mark(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx, cy = size / 2, size / 2
    R = size * 0.46

    def hexagon(radius):
        return [(cx + radius * math.cos(math.radians(60 * i - 90)),
                 cy + radius * math.sin(math.radians(60 * i - 90))) for i in range(6)]

    body = gradient((size, size), (18, 24, 46), (10, 13, 24), vertical=True).convert("RGBA")
    bm = Image.new("L", (size, size), 0)
    ImageDraw.Draw(bm).polygon(hexagon(R), fill=255)
    img.paste(body, (0, 0), bm)

    rim = gradient((size, size), GLACIER, AMETHYST).convert("RGBA")
    ring = Image.new("L", (size, size), 0)
    ImageDraw.Draw(ring).polygon(hexagon(R), fill=255)
    ImageDraw.Draw(ring).polygon(hexagon(R * 0.93), fill=0)
    img.paste(rim, (0, 0), ring)

    # slanted "E": three bars + spine, sheared for a feeling of speed
    def sheared(x, y):
        return (x + (cy - y) * 0.2, y)

    u = size * 0.036
    left, right = cx - 4.6 * u, cx + 4.6 * u
    bars = [
        (cy - 7.5 * u, cy - 4.5 * u, left, right),               # top
        (cy - 1.5 * u, cy + 1.5 * u, left, right - 1.8 * u),     # middle (shorter)
        (cy + 4.5 * u, cy + 7.5 * u, left, right),               # bottom
        (cy - 7.5 * u, cy + 7.5 * u, left, left + 3 * u),        # spine
    ]
    letter = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fill = gradient((size, size), GLACIER, AMETHYST)
    for y0, y1, x0, x1 in bars:
        paste_poly(letter, [sheared(x0, y0), sheared(x1, y0), sheared(x1, y1), sheared(x0, y1)], fill)

    # soft glow (built from the alpha channel so it never turns muddy)
    halo = letter.split()[3].filter(ImageFilter.GaussianBlur(size * 0.03)).point(lambda v: int(v * 0.55))
    glow = Image.new("RGBA", (size, size), GLACIER + (0,))
    glow.putalpha(halo)
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, letter)
    star(ImageDraw.Draw(img), cx + 3.6 * u, cy - 2.8 * u, size * 0.05, (255, 255, 255, 255))
    return img


def _font(px):
    for n in ("DejaVuSans-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def make_client_banner(mark, w=1600, h=512):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.alpha_composite(mark.resize((h, h), Image.LANCZOS), (0, 0))
    d = ImageDraw.Draw(img)
    tx = h + 30
    grad = gradient((w, h), GLACIER, AMETHYST)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((tx, 90), "ECM", font=_font(230), fill=255)
    img.paste(grad, (0, 0), mask)
    d.text((tx + 8, 340), "  ".join("CLIENT"), font=_font(64), fill=(232, 236, 255, 255))
    return img


def main():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CLIENT_DIR.mkdir(parents=True, exist_ok=True)

    app = make_app_icon(1024)
    app.resize((512, 512), Image.LANCZOS).save(APP_DIR / "app_icon.png")
    app.resize((256, 256), Image.LANCZOS).save(
        APP_DIR / "app_icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    mark = make_client_mark(1024)
    mark.resize((512, 512), Image.LANCZOS).save(CLIENT_DIR / "client_logo.png")
    make_client_banner(mark).save(CLIENT_DIR / "client_banner.png")
    print("Logos written to", ROOT / "assets" / "logo")


if __name__ == "__main__":
    main()
