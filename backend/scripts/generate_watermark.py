#!/usr/bin/env python3
"""Render Nagrik watermark PNG (used as FFmpeg overlay) from bundled fonts.

    python3 scripts/generate_watermark.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "app" / "assets"
FONTS = ASSETS / "fonts"
OUT = ASSETS / "watermark"
GOLD = (216, 168, 66, 255)          # #D8A842
CREAM = (245, 235, 216, 235)        # #F5EBD8
SCALE = 4                            # render large, downscale for crispness


def font(path: str, size: int):
    return ImageFont.truetype(str(FONTS / path), size)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    W, H = 1240 * SCALE // 2, 340 * SCALE // 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── circular mark ──────────────────────────────────────
    cx, cy, r = 160 * SCALE // 2, H // 2 + 6 * SCALE // 2, 138 * SCALE // 2
    ring_w = 11 * SCALE // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GOLD, width=ring_w)
    d.text((cx, cy - 6 * SCALE // 2), "ना", font=font("NotoSansDevanagari-Bold.ttf", 118 * SCALE // 2),
           fill=GOLD, anchor="mm")

    # ── wordmark ───────────────────────────────────────────
    tx = 330 * SCALE // 2
    d.text((tx, cy - 34 * SCALE // 2), "नागरिक",
           font=font("NotoSansDevanagari-Bold.ttf", 128 * SCALE // 2), fill=GOLD, anchor="lm")
    d.text((tx + 4 * SCALE // 2, cy + 62 * SCALE // 2), "C I V I C   S E N S E   I N D I A",
           font=font("Inter.ttf", 40 * SCALE // 2), fill=CREAM, anchor="lm")

    out_path = OUT / "watermark.png"
    final = img.resize((img.width // SCALE * 2, img.height // SCALE * 2), Image.LANCZOS)
    final.save(out_path)
    print(f"✓ {out_path} ({final.width}x{final.height})")


if __name__ == "__main__":
    main()
