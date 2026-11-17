#!/usr/bin/env python3
"""비밀상회 브랜드 이미지 생성 (brand/logo.svg 와 같은 모양을 Pillow 로 그린다).

만드는 것
  brand/app-icon-1024.png                       원본 앱 아이콘
  public/apple-touch-icon.png, icon-192/512.png 웹 아이콘
  public/og-image.png                           Open Graph 공유 이미지(1200x630)
  ios/.../AppIcon-512@2x.png, Splash 3종         iOS 아이콘·스플래시
  android/.../mipmap-*/ic_launcher*.png, splash  Android 아이콘·스플래시(기존 크기 유지)

실행: secret-store-vue 에서  python3 brand/make_assets.py
색은 회의록 2장 dark-teal 기준 고정(아이콘·스플래시는 런타임 테마를 따라가지 않는다).
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG = (14, 15, 18)          # --sc-bg (dark-teal)
BG_2 = (22, 24, 29)        # --sc-surface
SILVER = (154, 160, 171)   # 로고 실버 #9AA0AB
TEXT = (231, 233, 238)     # --sc-text
TEXT_SUB = (139, 145, 156) # --sc-text-sub
POINT = (45, 212, 191)     # --sc-point
SS = 4                     # 슈퍼샘플링 배율

HEX = [(32, 3.5), (56.7, 17.75), (56.7, 46.25), (32, 60.5), (7.3, 46.25), (7.3, 17.75)]
LINE = ((19, 38), (45, 38))
HEX_W, LINE_W = 3.4, 3.6


def draw_logo(img, cx, cy, size, color=SILVER):
    """img 위 (cx, cy) 중심에 한 변 size px 의 64 단위 로고를 그린다."""
    big = Image.new('RGBA', (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    k = size * SS / 64
    pts = [(x * k, y * k) for x, y in HEX]
    w = max(1, round(HEX_W * k))
    d.line(pts + [pts[0], pts[1]], fill=color + (255,), width=w, joint='curve')
    lw = max(1, round(LINE_W * k))
    (x1, y1), (x2, y2) = LINE
    d.line([(x1 * k, y1 * k), (x2 * k, y2 * k)], fill=color + (255,), width=lw)
    r = lw / 2
    for x in (x1, x2):
        d.ellipse([x * k - r, y1 * k - r, x * k + r, y1 * k + r], fill=color + (255,))
    small = big.resize((size, size), Image.LANCZOS)
    img.alpha_composite(small, (round(cx - size / 2), round(cy - size / 2))) if img.mode == 'RGBA' else img.paste(small, (round(cx - size / 2), round(cy - size / 2)), small)


def vertical_bg(w, h, top=BG_2, bottom=BG):
    img = Image.new('RGB', (w, h), bottom)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=c)
    return img


def app_icon(n):
    img = vertical_bg(n, n)
    draw_logo(img, n / 2, n / 2, round(n * 0.62))
    return img


def splash(w, h):
    img = Image.new('RGB', (w, h), BG)
    draw_logo(img, w / 2, h / 2, round(min(w, h) * 0.28))
    return img


def round_mask(img):
    n = img.size[0]
    m = Image.new('L', (n * SS, n * SS), 0)
    ImageDraw.Draw(m).ellipse([0, 0, n * SS - 1, n * SS - 1], fill=255)
    m = m.resize((n, n), Image.LANCZOS)
    out = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    out.paste(img.convert('RGBA'), (0, 0), m)
    return out


def font(size, bold=True):
    path = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
    # ttc index: 0 Regular … 6 Bold (macOS 기본 배치)
    return ImageFont.truetype(path, size, index=6 if bold else 0)


def og_image():
    w, h = 1200, 630
    img = vertical_bg(w, h)
    d = ImageDraw.Draw(img)
    draw_logo(img, 250, h / 2, 300)
    d.text((470, 205), '비밀상회', font=font(112), fill=TEXT)
    d.rectangle([474, 360, 474 + 64, 366], fill=POINT)
    d.text((472, 392), '자동매매 현황을 한눈에', font=font(40, bold=False), fill=TEXT_SUB)
    return img


def save(img, rel):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.convert('RGB').save(p, optimize=True) if img.mode != 'RGBA' else img.save(p, optimize=True)
    print('  ', rel, img.size)


def main():
    save(app_icon(1024), 'brand/app-icon-1024.png')
    save(app_icon(180), 'public/apple-touch-icon.png')
    save(app_icon(192), 'public/icon-192.png')
    save(app_icon(512), 'public/icon-512.png')
    save(og_image(), 'public/og-image.png')

    ios = 'ios/App/App/Assets.xcassets'
    if os.path.isdir(os.path.join(ROOT, ios)):
        save(app_icon(1024), f'{ios}/AppIcon.appiconset/AppIcon-512@2x.png')
        for name in ('splash-2732x2732.png', 'splash-2732x2732-1.png', 'splash-2732x2732-2.png'):
            save(splash(2732, 2732), f'{ios}/Splash.imageset/{name}')

    res = os.path.join(ROOT, 'android/app/src/main/res')
    if os.path.isdir(res):
        for dp, _, files in os.walk(res):
            for f in files:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, ROOT)
                if f == 'splash.png':
                    w, h = Image.open(p).size
                    save(splash(w, h), rel)
                elif f in ('ic_launcher.png', 'ic_launcher_round.png', 'ic_launcher_foreground.png'):
                    n = Image.open(p).size[0]
                    if f == 'ic_launcher_foreground.png':
                        # 적응형 아이콘 전경: 투명 바탕, 안전 영역(가운데 66%) 안에 로고
                        fg = Image.new('RGBA', (n, n), (0, 0, 0, 0))
                        draw_logo(fg, n / 2, n / 2, round(n * 0.42))
                        save(fg, rel)
                    elif f == 'ic_launcher_round.png':
                        save(round_mask(app_icon(n)), rel)
                    else:
                        save(app_icon(n), rel)


if __name__ == '__main__':
    main()
