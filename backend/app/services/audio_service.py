"""Background music: registry, tone→category recommendation, track resolution.

All bundled tracks are procedurally synthesized (royalty-free) — see
scripts/generate_music.py. Users can drop extra royalty-free .m4a/.mp3/.wav
files into app/assets/music/<category>/ to extend the library.
"""
from pathlib import Path
from typing import Dict, List, Optional

from ..core.config import get_settings
from ..schemas.models import ProjectSettings

TONE_TO_CATEGORY = {
    "breaking news": "energetic",
    "investigative": "investigative",
    "civic awareness": "civic",
    "informative": "modern",
    "explainer": "modern",
    "youth-focused": "energetic",
    "serious": "serious_news",
    "neutral": "minimal",
}

CATEGORY_LABELS = {
    "serious_news": "Serious News",
    "investigative": "Investigative",
    "energetic": "Energetic",
    "emotional": "Emotional",
    "civic": "Civic",
    "modern": "Modern",
    "minimal": "Minimal",
}


def music_dir() -> Path:
    return get_settings().assets_dir / "music"


def available_tracks() -> Dict[str, List[str]]:
    """category -> [file names]. Flat files map by stem; <category>/ folders also work."""
    out: Dict[str, List[str]] = {}
    root = music_dir()
    if not root.exists():
        return out
    exts = {".m4a", ".mp3", ".wav", ".aac"}
    for item in sorted(root.iterdir()):
        if item.is_file() and item.suffix.lower() in exts:
            cat = item.stem.lower()
            if cat in CATEGORY_LABELS:
                out.setdefault(cat, []).append(item.name)
        elif item.is_dir():
            files = [f.name for f in sorted(item.iterdir()) if f.suffix.lower() in exts]
            if files:
                out.setdefault(item.name, []).extend(files)
    return out


def resolve_track(category: str) -> Optional[Path]:
    lib = available_tracks()
    files = lib.get(category) or []
    if not files:
        # fall back through a sensible chain
        for fallback in ("minimal", "modern", "civic"):
            if lib.get(fallback):
                files = lib[fallback]
                break
    if not files:
        return None
    return music_dir() / files[0]


def recommend(settings: ProjectSettings) -> tuple:
    """Return (category, reason)."""
    chosen = (settings.music_category or "auto").lower()
    if chosen == "none":
        return "none", "No music — clean audio."
    if chosen != "auto" and chosen in CATEGORY_LABELS:
        return chosen, f"Manually selected — {CATEGORY_LABELS[chosen]} category."
    tone = (settings.tone or "").lower()
    for key, cat in TONE_TO_CATEGORY.items():
        if key in tone:
            return cat, f"Matched to '{settings.tone}' tone."
    return "minimal", "Neutral tone — kept it minimal."


def categories() -> List[dict]:
    lib = available_tracks()
    return [
        {"id": cat, "label": CATEGORY_LABELS.get(cat, cat.title()), "tracks": tracks}
        for cat, tracks in sorted(lib.items())
    ]
