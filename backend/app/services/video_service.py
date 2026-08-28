"""Video intake: validation, metadata, thumbnails."""
import re
from pathlib import Path
from typing import List

from ..core.errors import NagrikError
from ..core.storage import Storage, new_id
from ..schemas.models import VideoMeta
from ..utils.ffmpeg import extract_thumbnail, probe_media

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
MAX_DURATION_SECONDS = 60 * 30  # 30 min per clip, keeps local processing sane


def sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:120] or "video"


def add_video(storage: Storage, project_id: str, src_tmp: Path, original_name: str) -> VideoMeta:
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise NagrikError(
            status_code=415, code="unsupported_media",
            message=f"Unsupported video format '{ext or original_name}'.",
            hint="Upload MP4, MOV or WebM files.",
        )

    fname = f"{new_id()}_{sanitize_filename(original_name)}"
    path = storage.save_upload(project_id, fname, src_tmp)
    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise NagrikError(status_code=400, code="empty_file", message="Uploaded file is empty.")

    try:
        info = probe_media(path)
    except Exception as exc:
        raise NagrikError(
            status_code=415, code="unreadable_media",
            message=f"Could not read '{Path(original_name).name}' — it may be corrupted.",
            detail=str(exc)[:300],
        )

    if not info.get("has_video"):
        raise NagrikError(status_code=415, code="no_video_stream", message="File contains no video stream.")
    if info["duration"] <= 0:
        raise NagrikError(status_code=415, code="zero_duration", message="Video duration could not be determined.")
    if info["duration"] > MAX_DURATION_SECONDS:
        raise NagrikError(
            status_code=413, code="too_long",
            message="Video is longer than 30 minutes.",
            hint="Trim long recordings into shorter clips before uploading.",
        )

    thumb_rel = None
    thumb_path = Path("thumbs") / f"{fname}.jpg"     # persistent: survives render cleanup
    at = min(1.5, info["duration"] / 2)
    if extract_thumbnail(path, storage.abs_path(project_id, thumb_path), at_seconds=at):
        thumb_rel = str(thumb_path)

    return VideoMeta(
        id=fname.rsplit(".", 1)[0],
        filename=Path(original_name).name,
        path=str(Path("uploads") / fname),
        duration=info["duration"],
        width=info["width"],
        height=info["height"],
        size_bytes=size_bytes,
        has_audio=info["has_audio"],
        fps=info["fps"],
        thumbnail=thumb_rel,
    )


def total_duration(videos: List[VideoMeta]) -> float:
    return sum(v.duration for v in videos)
