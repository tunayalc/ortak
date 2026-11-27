"""Compose titled store images from raw simulator screenshots.

Usage: python3 scripts/make_store_images.py <raw_dir> <out_dir>
Raw screenshots are named like the slide keys below (e.g. iphone/01.png, ipad/01.png).
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SF = '/System/Library/Fonts/SFNS.ttf'
RED, INK, PINK = 'red', 'ink', 'pink'
THEMES = {
    RED: dict(top=(226, 24, 36), bottom=(176, 10, 22), kicker=(255, 255, 255, 200), title=(255, 255, 255), body=(255, 255, 255, 215)),
    INK: dict(top=(38, 38, 42), bottom=(16, 16, 18), kicker=(255, 110, 115), title=(255, 255, 255), body=(255, 255, 255, 200)),
    PINK: dict(top=(255, 244, 244), bottom=(253, 228, 229), kicker=(200, 16, 30), title=(26, 26, 26), body=(70, 70, 74)),
}
SLIDES = [
    ('01', RED, 'MEKÂN BUL', 'Herkese uyan\nbuluşma yeri', 'Nerede ve ne yapacağınızı seçin, ORTAK\nherkese yakın mekânları bulsun.'),
    ('02', INK, 'ODALAR', 'Herkes yerini\nkendisi ekler', 'Oda bağlantısını paylaşın; herkes adını ve\nyerini girer, siz ağırlıkları seçersiniz.'),
    ('03', PINK, 'TERCİHLER', 'Neye önem\nverdiğinizi seçin', 'Yakınlık, puan veya bütçe; tek dokunuşla\nya da kendi cümlenizle.'),
    ('04', RED, 'SONUÇLAR', 'Kim ne kadar\nyol gider, görün', 'Her mekân için kişi kişi yol süresi,\npuan ve fiyat düzeyi.'),
    ('05', INK, 'AÇIKLAMA', 'Neden bu mekân,\nsize açıkça söyler', 'Puanın nereden geldiğini adım adım\ngörün, kararı birlikte verin.'),
    ('06', PINK, 'BULUŞMA PLANI', 'Ne yapacağınıza\nbirlikte karar verin', 'Şehri, süreyi ve ilgi alanlarını seçin;\nORTAK size bir plan önersin.'),
]
DEVICES = {
    # canvas, phone screen width, phone top, bezel, screen corner radius (in screen px before scaling), island
    'iphone': dict(size=(1320, 2868), screen_w=1010, top=880, bezel=26, radius=190, island=True, pad=110, scale=1.0),
    'ipad': dict(size=(2064, 2752), screen_w=1560, top=850, bezel=34, radius=60, island=False, pad=170, scale=1.35),
    'play': dict(size=(1080, 1920), screen_w=700, top=640, bezel=18, radius=190, island=True, pad=80, scale=0.74),
}


def font(size, weight):
    f = ImageFont.truetype(SF, size)
    f.set_variation_by_name(weight)
    return f


def gradient(size, top, bottom):
    w, h = size
    col = Image.new('RGB', (1, h))
    for y in range(h):
        t = y / (h - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    img = col.resize(size)
    # soft light in the upper right corner, like a studio backdrop
    glow = Image.new('L', size, 0)
    ImageDraw.Draw(glow).ellipse((w * 0.35, -h * 0.25, w * 1.45, h * 0.45), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.18))
    light = Image.new('RGB', size, (255, 255, 255))
    return Image.composite(light, img, glow.point(lambda v: v * 0.35))


def rounded_mask(size, radius):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return m


def draw_text(img, d, slide, theme):
    _, _, kicker, title, body = slide
    s, pad = d['scale'], d['pad']
    draw = ImageDraw.Draw(img, 'RGBA')
    y = round(250 * s)
    kf = font(round(40 * s), 'Semibold')
    draw.line((pad, y + round(22 * s), pad + round(44 * s), y + round(22 * s)), fill=theme['kicker'], width=max(3, round(4 * s)))
    x = pad + round(62 * s)
    for ch in kicker:  # letter-spaced caps
        draw.text((x, y), ch, font=kf, fill=theme['kicker'])
        x += draw.textlength(ch, font=kf) + round(5 * s)
    y += round(84 * s)
    size = round(116 * s)
    while max(draw.textlength(l, font=font(size, 'Bold')) for l in title.split('\n')) > img.width - 2 * pad:
        size -= 2
    tf = font(size, 'Bold')
    for line in title.split('\n'):
        draw.text((pad, y), line, font=tf, fill=theme['title'])
        y += round(128 * s)
    y += round(40 * s)
    bf = font(round(44 * s), 'Regular')
    for line in body.split('\n'):
        draw.text((pad, y), line, font=bf, fill=theme['body'])
        y += round(60 * s)
    return y


def place_phone(img, shot, d, dark_bg):
    W, H = img.size
    sw = d['screen_w']
    shot = shot.convert('RGB')
    sh = round(shot.height * sw / shot.width)
    shot = shot.resize((sw, sh), Image.LANCZOS)
    r = round(d['radius'] * sw / shot.width) if False else round(d['radius'] * sw / 1320)
    b = d['bezel']
    fw, fh = sw + 2 * b, sh + 2 * b
    fx, fy = (W - fw) // 2, d['top']
    # shadow
    shadow = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((fx, fy + 30, fx + fw, fy + fh + 30), r + b, fill=(0, 0, 0, 120 if dark_bg else 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(45))
    img.paste(shadow, (0, 0), shadow)
    # frame: dark titanium body with a thin lighter rim
    frame = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle((0, 0, fw - 1, fh - 1), r + b, fill=(58, 58, 62))
    fd.rounded_rectangle((3, 3, fw - 4, fh - 4), r + b - 3, fill=(20, 20, 22))
    img.paste(frame, (fx, fy), frame)
    img.paste(shot, (fx + b, fy + b), rounded_mask((sw, sh), r))
    if d['island']:
        iw, ih = round(sw * 0.285), round(sw * 0.083)
        ix, iy = fx + b + (sw - iw) // 2, fy + b + round(sw * 0.026)
        ImageDraw.Draw(img).rounded_rectangle((ix, iy, ix + iw, iy + ih), ih // 2, fill=(0, 0, 0))


def compose(raw_dir, out_dir):
    for kind, d in DEVICES.items():
        src = raw_dir / ('ipad' if kind == 'ipad' else 'iphone')
        if not src.exists():
            continue
        (out_dir / kind).mkdir(parents=True, exist_ok=True)
        for slide in SLIDES:
            path = src / f'{slide[0]}.png'
            if not path.exists():
                continue
            theme = THEMES[slide[1]]
            img = gradient(d['size'], theme['top'], theme['bottom'])
            draw_text(img, d, slide, theme)
            place_phone(img, Image.open(path), d, slide[1] != PINK)
            img.convert('RGB').save(out_dir / kind / f'{slide[0]}.png', optimize=True)
            print(out_dir / kind / f'{slide[0]}.png', img.size)


if __name__ == '__main__':
    compose(Path(sys.argv[1]), Path(sys.argv[2]))
