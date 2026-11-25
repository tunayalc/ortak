"""Draws the ORTAK "Kesişim" mark (two overlapping circles, the shared part highlighted)
and writes every app icon. Run from the repository root: python3 scripts/make_icons.py
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

TEAL, YELLOW, WHITE = (18, 165, 148), (255, 200, 87), (255, 255, 255)
SOFT = (148, 214, 207)  # white at 55% over teal, as a solid colour (iOS icons have no alpha)
ROOT = Path(__file__).resolve().parent.parent
SS = 4  # supersampling for smooth edges


def circle(size, cx, cy, r):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    return mask


def mark(size, width_ratio, background, left, right, middle, right_alpha=255):
    """Two circles of radius r, centres r apart, centred; total width = 3r."""
    big = size * SS
    r = big * width_ratio / 3
    cx, cy = big / 2, big / 2
    a, b = circle(big, cx - r / 2, cy, r), circle(big, cx + r / 2, cy, r)
    image = Image.new("RGBA", (big, big), background)
    image.paste(Image.new("RGBA", (big, big), right + (right_alpha,)), (0, 0), b)
    image.paste(Image.new("RGBA", (big, big), left + (255,)), (0, 0), a)
    image.paste(Image.new("RGBA", (big, big), middle + (255,)), (0, 0), ImageChops.multiply(a, b))
    return image.resize((size, size), Image.LANCZOS)


def save(image, path, opaque=False):
    path = ROOT / path
    (image.convert("RGB") if opaque else image).save(path, optimize=True)
    print("wrote", path.relative_to(ROOT), image.size)


# iOS/App Store icon: full-bleed square, no transparency; the system rounds the corners.
save(mark(1024, 0.70, TEAL + (255,), WHITE, SOFT, YELLOW), "mobile/assets/icon.png", opaque=True)
# Android adaptive foreground: transparent, inside the 66% safe zone; background colour is in app.config.js.
save(mark(1024, 0.56, (0, 0, 0, 0), WHITE, WHITE, YELLOW, right_alpha=140), "mobile/assets/adaptive-icon.png")
# Android themed (monochrome) icon: only alpha is used.
save(mark(1024, 0.56, (0, 0, 0, 0), WHITE, WHITE, WHITE, right_alpha=120), "mobile/assets/monochrome-icon.png")
# Splash and in-app header mark: coloured, on transparent so light and dark splash backgrounds both work.
save(mark(1024, 0.96, (0, 0, 0, 0), TEAL, TEAL, YELLOW, right_alpha=140), "mobile/assets/splash-icon.png")

(ROOT / "frontend/public/favicon.svg").write_text("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#12A594"/>
  <circle cx="25" cy="32" r="14" fill="#fff"/>
  <circle cx="39" cy="32" r="14" fill="#fff" fill-opacity="0.55"/>
  <path d="M32 19.88A14 14 0 0 1 32 44.12A14 14 0 0 1 32 19.88Z" fill="#FFC857"/>
</svg>
""")
print("wrote frontend/public/favicon.svg")
