#!/usr/bin/env python3
"""Render Nagrik branded frame overlay (1080x1920) — burgundy/gold, editorial, minimal.

The frame is a PNG with transparency in the center; FFmpeg overlays it as the
final video filter. Re-run after changing brand colours:

    python3 scripts/generate_frame.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
ASSETS = Path(__file__).resolve().parent.parent / "app" / "assets"
FONTS = ASSETS / "fonts"
OUT_DIR = ASSETS / "frame"
OUT = OUT_DIR / "frame.png"

# Brand palette
BURGUNDY = (58, 10, 22, 255)       # #3A0A16
BURGUNDY_LIGHT = (74, 14, 31, 255) # #4A0E1F
GOLD = (212, 165, 55, 255)         # #D4A537
GOLD_SOFT = (233, 200, 120, 255)   # #E9C878
CREAM = (245, 235, 216, 255)       # #F5EBD8


def font(path: str, size: int):
    return ImageFont.truetype(str(FONTS / path), size)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── Top header bar (burgundy, full width) ─────────────────
    HEADER_H = 74
    d.rectangle([0, 0, W, HEADER_H], fill=BURGUNDY)

    # thin gold rule under header
    d.rectangle([0, HEADER_H, W, HEADER_H + 2], fill=GOLD)

    # Gold ring + ना mark (left side, centered in header)
    ring_cx, ring_cy, ring_r = 52, HEADER_H // 2, 24
    d.ellipse(
        [ring_cx - ring_r, ring_cy - ring_r, ring_cx + ring_r, ring_cy + ring_r],
        outline=GOLD, width=2,
    )
    # na glyph (smaller so it sits well at header scale)
    try:
        na_font = font("NotoSansDevanagari-Bold.ttf", 20)
        d.text((ring_cx, ring_cy + 1), "ना", font=na_font, fill=GOLD_SOFT, anchor="mm")
    except Exception:
        pass

    # Brand wordmark (Devanagari)
    try:
        dev_font = font("NotoSansDevanagari-Bold.ttf", 28)
        d.text((88, HEADER_H // 2 - 1), "नागरिक", font=dev_font, fill=GOLD_SOFT, anchor="lm")
    except Exception:
        d.text((88, HEADER_H // 2 - 1), "NAGRIK", font=font("Anton-Regular.ttf", 22), fill=GOLD_SOFT, anchor="lm")

    # "CIVIC SENSE INDIA" (right side)
    try:
        latin_font = font("Inter.ttf", 13)
        try:
            latin_font.set_variation_by_name("Bold")
        except Exception:
            pass
    except Exception:
        latin_font = ImageFont.load_default()
    tag = "CIVIC  SENSE  INDIA"
    # measure and right-align with padding
    tw = d.textlength(tag, font=latin_font)
    d.text((W - 18 - tw, HEADER_H // 2 - 1), tag, font=latin_font, fill=(*CREAM[:3], 210), anchor="lm")

    # ── Border frame (subtle, editorial) ──────────────────────
    # Outer burgundy stroke (8px) + inner gold hairline (1.5px) — only on sides+bottom,
    # top is already covered by header bar.
    BORDER_OUT = 8
    GOLD_LINE = 2
    # sides + bottom outer burgundy
    d.rectangle([0, HEADER_H, BORDER_OUT, H], fill=BURGUNDY)                 # left
    d.rectangle([W - BORDER_OUT, HEADER_H, W, H], fill=BURGUNDY)             # right
    d.rectangle([0, H - BORDER_OUT, W, H], fill=BURGUNDY)                    # bottom
    # inner gold hairline inset from outer border
    inset = BORDER_OUT
    d.rectangle([inset, HEADER_H + 6, inset + GOLD_LINE, H - BORDER_OUT], fill=(*GOLD[:3], 180))           # left gold
    d.rectangle([W - inset - GOLD_LINE, HEADER_H + 6, W - inset, H - BORDER_OUT], fill=(*GOLD[:3], 180))   # right gold
    d.rectangle([inset, H - BORDER_OUT, W - inset, H - BORDER_OUT + GOLD_LINE], fill=(*GOLD[:3], 160))     # bottom gold (subtle)

    img.save(OUT, "PNG")
    print(f"✓ {OUT} ({W}x{H}, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
