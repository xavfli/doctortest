"""Generate the app icons (favicon, apple-touch, PWA) from a single vector source.

Run after changing the brand colours or the mark:

    python tools/build_icons.py

Writes into web/assets/icons/. Keeping real files in the project means the
browser never falls back to another page's cached icon for /favicon.ico.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "assets" / "icons"

BRAND = (47, 124, 246)  # --brand
ACCENT = (107, 75, 240)  # gradient end used by .logo
BG_DARK = (11, 18, 32)  # --bg


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Prefer a bold UI font; fall back to the bundled Pillow font."""
    candidates = [
        "C:/Windows/Fonts/segoeuibl.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit_font(text: str, max_width: int, start: int) -> ImageFont.ImageFont:
    """Shrink the font until the text fits inside max_width."""
    size = start
    while size > 6:
        font = _font(size)
        left, _, right, _ = font.getbbox(text)
        if right - left <= max_width:
            return font
        size -= 1
    return _font(6)


def render_icon(size: int, *, rounded: bool, bleed: bool) -> Image.Image:
    """Draw the OSH mark: rounded brand gradient with a medical cross."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Diagonal gradient background, matching .logo in the CSS.
    radius = size * 0.22 if rounded else 0
    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for y in range(size):
        frac = y / max(size - 1, 1)
        colour = tuple(
            round(BRAND[i] + (ACCENT[i] - BRAND[i]) * frac) for i in range(3)
        )
        gdraw.line([(0, y), (size, y)], fill=colour + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    img.paste(gradient, (0, 0), mask)

    # Medical cross, centred.
    cx, cy = size / 2, size / 2
    arm = size * (0.30 if not bleed else 0.32)
    thick = size * (0.105 if not bleed else 0.115)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [cx - arm / 2, cy - thick / 2, cx + arm / 2, cy + thick / 2],
        radius=thick / 2,
        fill=(255, 255, 255, 255),
    )
    draw.rounded_rectangle(
        [cx - thick / 2, cy - arm / 2, cx + thick / 2, cy + arm / 2],
        radius=thick / 2,
        fill=(255, 255, 255, 255),
    )

    # Wordmark only when there is room for it (192px and larger).
    if size >= 192:
        text = "OSH"
        max_w = size * 0.62
        font = _fit_font(text, max_w, int(size * 0.19))
        left, top, right, bottom = font.getbbox(text)
        draw.text(
            ((size - (right - left)) / 2 - left, size * 0.80 - (bottom + top) / 2),
            text,
            font=font,
            fill=(255, 255, 255, 235),
        )
    return img


def render_maskable(size: int) -> Image.Image:
    """PWA maskable icon: mark inside the 80% safe zone, background bled out."""
    img = Image.new("RGBA", (size, size), BG_DARK + (255,))
    mark = render_icon(size, rounded=False, bleed=True)
    inner = int(size * 0.62)
    mark = mark.resize((inner, inner), Image.LANCZOS)
    offset = (size - inner) // 2
    img.alpha_composite(mark, (offset, offset))
    return img


def write_svg() -> None:
    """Vector favicon: crisp on any size, used by modern browsers first."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="OSH">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2f7cf6"/>
      <stop offset="1" stop-color="#6b4bf0"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#g)"/>
  <rect x="19" y="28.5" width="26" height="7" rx="3.5" fill="#fff"/>
  <rect x="28.5" y="19" width="7" height="26" rx="3.5" fill="#fff"/>
</svg>
"""
    (OUT_DIR / "favicon.svg").write_text(svg, encoding="utf-8")


MANIFEST = """{
  "name": "Oilaviy shifokorlik testi",
  "short_name": "OSH test",
  "description": "Oilaviy shifokorlik mutaxassisligi testi platformasi",
  "lang": "uz",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#0b1220",
  "theme_color": "#2f7cf6",
  "icons": [
    {
      "src": "icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "icon-maskable-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}
"""


def write_manifest() -> None:
    """Write the PWA manifest next to the icons.

    The file is written into the icons folder only: /manifest.webmanifest is
    served from there, and the HTML links to assets/icons/manifest.webmanifest
    so both paths resolve to the same bytes instead of drifting apart.
    """
    (OUT_DIR / "manifest.webmanifest").write_text(MANIFEST, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # favicon.ico: multi-resolution so Windows and old browsers look sharp.
    # Pillow derives the smaller entries from the image it is given, so the
    # largest frame is saved and the rest are produced by resampling.
    ico_sizes = [16, 24, 32, 48, 64]
    render_icon(64, rounded=False, bleed=False).save(
        OUT_DIR / "favicon.ico",
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
    )

    # Tab icon: rounded like the header logo.
    render_icon(64, rounded=True, bleed=False).save(OUT_DIR / "favicon-64.png")
    render_icon(32, rounded=True, bleed=False).save(OUT_DIR / "favicon-32.png")
    # Apple home-screen icon must be square-cornered.
    render_icon(180, rounded=False, bleed=False).save(OUT_DIR / "apple-touch-icon.png")
    # PWA icons.
    render_icon(192, rounded=True, bleed=False).save(OUT_DIR / "icon-192.png")
    render_icon(512, rounded=True, bleed=False).save(OUT_DIR / "icon-512.png")
    render_maskable(512).save(OUT_DIR / "icon-maskable-512.png")

    write_svg()
    write_manifest()

    print("Icons written to", OUT_DIR.relative_to(ROOT))
    for path in sorted(OUT_DIR.iterdir()):
        print(f"  {path.name:26} {path.stat().st_size:>7,} bytes")


if __name__ == "__main__":
    main()