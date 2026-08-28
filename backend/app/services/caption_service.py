"""Caption generation: turns script lines into large, mobile-first caption units.

Rules (editorial short-form style):
  * 2–7 words per visual unit
  * uppercase for the bold styles
  * emphasis words highlighted by the renderer / preview
  * units are distributed across the clip duration proportional to word count
"""
import re
from typing import List

from ..schemas.models import CaptionUnit

MAX_WORDS = 7
MIN_WORDS = 2

UPPERCASE_STYLES = {"bold_editorial", "highlight", "nagrik"}


def _split_phrases(text: str) -> List[str]:
    """Split into clause-level phrases first."""
    parts = re.split(r"[.!?…:;—–]+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, max_words: int = MAX_WORDS) -> List[str]:
    """Break text into <=max-word chunks at natural points."""
    chunks: List[str] = []
    for phrase in _split_phrases(text):
        words = phrase.split()
        if not words:
            continue
        if len(words) <= max_words:
            chunks.append(phrase)
            continue
        # try to split on conjunctions/punct for natural rhythm
        pieces = re.split(r"(\s+(?:but|and|so|while|however|because|that|which)\s+)", " " + phrase + " ")
        buffer: List[str] = []
        count = 0
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            pw = piece.split()
            if count + len(pw) > max_words and buffer:
                chunks.append(" ".join(buffer))
                buffer, count = [], 0
            buffer.extend(pw)
            count += len(pw)
            while len(buffer) > max_words:
                chunks.append(" ".join(buffer[:max_words]))
                buffer = buffer[max_words:]
                count = len(buffer)
        if buffer:
            chunks.append(" ".join(buffer))
    return [c.strip() for c in chunks if c.strip()]


def normalize_emphasis(words: List[str], unit_text: str) -> List[str]:
    """Keep only emphasis words that actually occur in this caption unit."""
    unit_words = {w.lower().strip(".,!?\"'():;") for w in unit_text.split()}
    out: List[str] = []
    for w in words or []:
        wl = w.lower().strip(".,!?\"'():;")
        if wl and wl in unit_words and wl not in out:
            out.append(wl)
    return out


def build_captions(
    voiceover: str,
    fallback_caption: str,
    duration: float,
    style: str,
    emphasis_words: List[str],
) -> List[CaptionUnit]:
    text_source = (voiceover or "").strip() or (fallback_caption or "").strip()
    if not text_source:
        return []
    raw_chunks = chunk_text(text_source)

    # For very short clips prefer a single punchy caption.
    if duration <= 3.2 and fallback_caption:
        raw_chunks = [fallback_caption] + [c for c in raw_chunks if c != fallback_caption]

    upper = style in UPPERCASE_STYLES
    weights = [len(c.split()) for c in raw_chunks]
    total_w = sum(weights) or len(raw_chunks)

    units: List[CaptionUnit] = []
    t = 0.0
    for chunk, w in zip(raw_chunks, weights):
        share = (w / total_w) * duration
        # keep each unit readable: clamp between 0.55s and 2.6s where possible
        share = max(0.5, min(share if share > 0 else duration / len(raw_chunks), 3.2))
        display = chunk.upper() if upper else chunk
        units.append(CaptionUnit(
            text=display,
            start=round(t, 2),
            duration=round(share, 2),
            emphasis=normalize_emphasis(emphasis_words, chunk),
        ))
        t += share
    # fix drift so captions end exactly at clip end
    if units:
        drift = duration - t
        units[-1].duration = round(max(0.4, units[-1].duration + drift), 2)
    return units


def style_allows_uppercase(style: str) -> bool:
    return style in UPPERCASE_STYLES


# ── Caption styling & PNG rendering (used by FFmpeg export) ────
#
# Captions are rendered to transparent PNGs with Pillow using Nagrik's bundled
# brand fonts, then burned into the video with the universal `overlay` filter.
# This avoids any libass/drawtext dependency — works on every FFmpeg build and
# gives pixel-perfect typography.

from pathlib import Path as _Path
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

GOLD_RGB: Tuple[int, int, int, int] = (212, 165, 55, 255)      # #D4A537
CREAM_RGB: Tuple[int, int, int, int] = (245, 235, 216, 255)    # #F5EBD8
WHITE_RGB: Tuple[int, int, int, int] = (255, 255, 255, 255)

CAPTION_STYLES = {
    "clean": {
        "font": "inter", "size": 62, "fill": WHITE_RGB,
        "outline": 4, "outline_colour": (0, 0, 0, 200),
        "shadow": 3, "shadow_colour": (0, 0, 0, 120),
        "uppercase": False, "emphasis_colour": GOLD_RGB,
        "bottom_offset": 360, "line_spacing": 1.24,
        "label": "Clean",
    },
    "bold_editorial": {
        "font": "display", "size": 106, "fill": WHITE_RGB,
        "outline": 7, "outline_colour": (0, 0, 0, 170),
        "shadow": 6, "shadow_colour": (0, 0, 0, 110),
        "uppercase": True, "emphasis_colour": WHITE_RGB,
        "bottom_offset": 320, "line_spacing": 1.08,
        "label": "Bold Editorial",
    },
    "highlight": {
        "font": "display", "size": 100, "fill": WHITE_RGB,
        "outline": 6, "outline_colour": (0, 0, 0, 180),
        "shadow": 6, "shadow_colour": (0, 0, 0, 110),
        "uppercase": True, "emphasis_colour": GOLD_RGB,
        "bottom_offset": 330, "line_spacing": 1.1,
        "label": "Highlight",
    },
    "nagrik": {
        "font": "display", "size": 102, "fill": CREAM_RGB,
        "outline": 9, "outline_colour": (46, 8, 18, 240),          # deep burgundy
        "shadow": 7, "shadow_colour": (10, 2, 4, 110),
        "uppercase": True, "emphasis_colour": GOLD_RGB,
        "bottom_offset": 350, "line_spacing": 1.1,
        "label": "Nagrik Default",
    },
}

_FONTS_DIR = _Path(__file__).resolve().parents[1] / "assets" / "fonts"
_font_cache = {}


def get_caption_style(style_id: str) -> dict:
    return CAPTION_STYLES.get(style_id, CAPTION_STYLES["nagrik"])


def _load_font(kind: str, size: int):
    key = (kind, size)
    if key not in _font_cache:
        files = {"display": "Anton-Regular.ttf", "inter": "Inter.ttf",
                 "devanagari": "NotoSansDevanagari-Bold.ttf"}
        _font_cache[key] = ImageFont.truetype(str(_FONTS_DIR / files[kind]), size)
    return _font_cache[key]


def _pick_font(text: str, style: dict):
    """Use a Devanagari face when Hindi glyphs are present."""
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return _load_font("devanagari", max(56, int(style["size"] * 0.92)))
    if style["font"] == "inter":
        f = _load_font("inter", style["size"])
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
        return f
    return _load_font("display", style["size"])


def render_caption_png(unit_text: str, emphasis: List[str], style_id: str,
                       out_path: Path, width: int = 1080) -> None:
    """Render one caption unit as a transparent PNG sized for the 1080x1920 canvas."""
    style = get_caption_style(style_id)
    text = unit_text.upper() if style.get("uppercase") else unit_text
    font = _pick_font(text, style)

    probe = Image.new("RGBA", (8, 8))
    draw_probe = ImageDraw.Draw(probe)
    space_w = draw_probe.textlength(" ", font=font)

    emph_set = {e.lower() for e in emphasis or []}
    words = []
    for w in text.split():
        color = style["emphasis_colour"] if w.lower().strip(".,!?\"'():;—–") in emph_set else style["fill"]
        words.append((w, color))

    max_width = width - 140
    lines: List[List[Tuple[str, tuple]]] = []
    cur: List[Tuple[str, tuple]] = []
    cur_px = 0.0
    for word, color in words:
        wpx = draw_probe.textlength(word, font=font)
        add = wpx if not cur else wpx + space_w
        if cur and cur_px + add > max_width:
            lines.append(cur)
            cur, cur_px = [(word, color)], wpx
        else:
            cur.append((word, color))
            cur_px += add
    if cur:
        lines.append(cur)

    line_h = int(style["size"] * style.get("line_spacing", 1.15))
    pad = style.get("outline", 6) + style.get("shadow", 4) + 8
    img_h = line_h * len(lines) + pad * 2
    img = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    y = pad
    for ln in lines:
        total_w = sum(d.textlength(w, font=font) for w, _ in ln) + space_w * (len(ln) - 1)
        x = (width - total_w) / 2
        for word, color in ln:
            common = dict(font=font,
                          stroke_width=style.get("outline", 0),
                          stroke_fill=style.get("outline_colour"))
            sc = style.get("shadow_colour")
            if sc:
                d.text((x + style["shadow"], y + style["shadow"]), word, fill=sc, **common)
            d.text((x, y), word, fill=color, **common)
            x += d.textlength(word, font=font) + space_w
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def caption_png_height(style_id: str) -> int:
    """Nominal height used for overlay positioning math."""
    style = get_caption_style(style_id)
    pad = style.get("outline", 6) + style.get("shadow", 4) + 8
    return pad * 2 + int(style["size"] * style.get("line_spacing", 1.15)) * 3


def build_caption_overlays(
    timeline_captions: List[dict],
    style_id: str,
    work_dir: Path,
) -> List[dict]:
    """Render every caption unit to PNG.

    timeline_captions: absolute-time events [{"text","start","duration","emphasis"}]
    Returns [{"png": Path, "start": float, "end": float}].
    """
    overlays: List[dict] = []
    work_dir.mkdir(parents=True, exist_ok=True)
    for i, cap in enumerate(timeline_captions):
        text = (cap.get("text") or "").strip()
        if not text:
            continue
        png = work_dir / f"cap_{i:03d}.png"
        render_caption_png(text, cap.get("emphasis", []), style_id, png)
        start = max(0.0, float(cap.get("start", 0)))
        dur = max(0.35, float(cap.get("duration", 1.5)))
        overlays.append({"png": png, "start": round(start, 2),
                         "end": round(start + dur - 0.04, 2)})
    return overlays
