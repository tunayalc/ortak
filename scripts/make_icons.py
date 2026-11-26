"""Draws the ORTAK "Kesişim" mark (two overlapping circles, the shared part highlighted)
and writes every app icon. Run from the repository root: python3 scripts/make_icons.py
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

RED, WHITE = (217, 15, 28), (255, 255, 255)
ROOT = Path(__file__).resolve().parent.parent
SS = 4  # supersampling for smooth edges


def circle(size, cx, cy, r):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    return mask


def mark(size, width_ratio, background, ring, middle, ring_alpha=255):
    """Two rings of radius r, centres r apart, centred (total width 3r); the shared lens is filled."""
    big = size * SS
    r = big * width_ratio / 3
    w = r * 0.24
    cx, cy = big / 2, big / 2
    a, b = circle(big, cx - r / 2, cy, r), circle(big, cx + r / 2, cy, r)
    rings = ImageChops.lighter(
        ImageChops.subtract(a, circle(big, cx - r / 2, cy, r - w)),
        ImageChops.subtract(b, circle(big, cx + r / 2, cy, r - w)),
    )
    image = Image.new("RGBA", (big, big), background)
    image.paste(Image.new("RGBA", (big, big), ring + (ring_alpha,)), (0, 0), rings)
    image.paste(Image.new("RGBA", (big, big), middle + (255,)), (0, 0), ImageChops.multiply(a, b))
    return image.resize((size, size), Image.LANCZOS)


def save(image, path, opaque=False):
    path = ROOT / path
    (image.convert("RGB") if opaque else image).save(path, optimize=True)
    print("wrote", path.relative_to(ROOT), image.size)


# iOS/App Store icon: full-bleed square, no transparency; the system rounds the corners.
save(mark(1024, 0.70, RED + (255,), WHITE, WHITE), "mobile/assets/icon.png", opaque=True)
# Android adaptive foreground: transparent, inside the 66% safe zone; background colour is in app.config.js.
save(mark(1024, 0.56, (0, 0, 0, 0), WHITE, WHITE), "mobile/assets/adaptive-icon.png")
# Android themed (monochrome) icon: only alpha is used.
save(mark(1024, 0.56, (0, 0, 0, 0), WHITE, WHITE), "mobile/assets/monochrome-icon.png")
# Splash and in-app header mark: coloured, on transparent so light and dark splash backgrounds both work.
save(mark(1024, 0.96, (0, 0, 0, 0), RED, RED), "mobile/assets/splash-icon.png")

(ROOT / "frontend/public/favicon.svg").write_text("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#D90F1C"/>
  <g fill="none" stroke="#fff" stroke-width="3.4">
    <circle cx="25" cy="32" r="12.3"/>
    <circle cx="39" cy="32" r="12.3"/>
  </g>
  <path d="M32 19.88A14 14 0 0 1 32 44.12A14 14 0 0 1 32 19.88Z" fill="#fff"/>
</svg>
""")
print("wrote frontend/public/favicon.svg")
