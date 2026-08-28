"""Nagrik REST API."""
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..core.config import ffmpeg_available, get_settings
from ..core.errors import NagrikError
from ..core.storage import get_storage
from ..schemas.models import (
    MusicPatch, MusicSelection, ProjectCreate, ProjectPatch,
    RenderState, TimelinePatch,
)
from ..services import audio_service, caption_service
from ..services.project_service import ProjectStore, run_generation
from ..services.llm_service import llm_status
from ..services.rendering_service import RenderError, render_reel
from ..services.story_service import regenerate_section
from ..services.transcription_service import stt_status
from ..services.tts_service import tts_status
from ..services.video_service import add_video

router = APIRouter(prefix="/api")


def store() -> ProjectStore:
    return ProjectStore(get_storage())


# ── system ─────────────────────────────────────────────────────

@router.get("/health")
def health():
    ok, _, version = ffmpeg_available()
    settings = get_settings()
    return {
        "status": "ok",
        "app": "Nagrik",
        "ffmpeg": {"available": ok, "version": version},
        "providers": {"llm": llm_status(), "stt": stt_status(), "tts": tts_status()},
        "music_categories": audio_service.categories(),
        "caption_styles": [
            {"id": k, **v} for k, v in caption_service.CAPTION_STYLES.items()
        ],
        "limits": {"max_upload_mb": settings.max_upload_mb},
    }


# ── projects ───────────────────────────────────────────────────

@router.post("/projects")
def create_project(body: ProjectCreate):
    project = store().create(body)
    return project.model_dump()


@router.get("/projects")
def list_projects():
    return [p.model_dump() for p in store().list_all()]


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    p = store().get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    return p.model_dump()


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    prev_voiceover = p.settings.voiceover if p.settings else None
    prev_watermark = p.settings.watermark if p.settings else None
    prev_frame = p.settings.frame if p.settings else None
    if body.title is not None:
        p.title = body.title[:120]
    if body.overview is not None:
        p.overview = body.overview
    if body.settings is not None:
        # invalidate export if audio/branding/frame changed
        if (prev_voiceover is not None and body.settings.voiceover != prev_voiceover) or \
           (prev_watermark is not None and body.settings.watermark != prev_watermark) or \
           (prev_frame is not None and body.settings.frame != prev_frame):
            if p.render.status == "done":
                p.render.status = "idle"
                p.render.stage = "Audio/branding/frame changed — re-export to apply"
        p.settings = body.settings
    s.save(p)
    return p.model_dump()


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    if not store().delete(project_id):
        raise HTTPException(404, "Project not found.")
    return {"ok": True}


# ── footage upload ─────────────────────────────────────────────

@router.post("/projects/{project_id}/videos")
async def upload_videos(project_id: str, files: list[UploadFile] = File(...)):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    added = []
    errors = []
    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in {".mp4", ".mov", ".webm", ".m4v"}:
            errors.append({"file": f.filename, "message": "Unsupported format — use MP4, MOV or WebM."})
            continue
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
            tmp_path = Path(tf.name)
            size = 0
            try:
                while chunk := await f.read(4 * 1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise NagrikError(
                            status_code=413, code="too_large",
                            message=f"'{f.filename}' exceeds the {settings.max_upload_mb} MB limit.",
                        )
                    tf.write(chunk)
            except NagrikError as exc:
                tmp_path.unlink(missing_ok=True)
                errors.append({"file": f.filename, "message": exc.detail})
                continue
            finally:
                await f.close()
        try:
            meta = add_video(get_storage(), project_id, tmp_path, f.filename or "video.mp4")
            # replace if same file re-uploaded (by filename+size)
            existing = next((v for v in p.videos if v.filename == meta.filename), None)
            if existing:
                p.videos.remove(existing)
            p.videos.append(meta)
            added.append(meta.model_dump())
        except NagrikError as exc:
            errors.append({"file": f.filename, "message": exc.payload["message"],
                           "hint": exc.hint})
        finally:
            tmp_path.unlink(missing_ok=True)
    s.save(p)
    return {"videos": [v.model_dump() for v in p.videos], "added": added, "errors": errors}


@router.delete("/projects/{project_id}/videos/{video_id}")
def delete_video(project_id: str, video_id: str):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    p.videos = [v for v in p.videos if v.id != video_id]
    s.save(p)
    return {"ok": True}


# ── generation pipeline ────────────────────────────────────────

@router.post("/projects/{project_id}/generate")
def generate(project_id: str):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    if not p.videos:
        raise HTTPException(400, "Upload at least one video before generating.")
    if not p.overview.strip() and not p.videos:
        raise HTTPException(400, "Add a story overview first.")
    if p.status == "processing":
        return {"ok": True, "status": "already_running"}
    t = threading.Thread(target=run_generation, args=(s, project_id), daemon=True)
    t.start()
    return {"ok": True, "status": "started"}


# ── timeline editing ───────────────────────────────────────────

@router.put("/projects/{project_id}/timeline")
def put_timeline(project_id: str, body: TimelinePatch):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    p.timeline = body.items
    s.save(p)
    return {"ok": True}


@router.post("/projects/{project_id}/timeline/move")
def move_item(project_id: str, body: dict):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    item_id, direction = body.get("id"), body.get("direction", "up")
    idx = next((i for i, it in enumerate(p.timeline) if it.id == item_id), -1)
    if idx < 0:
        raise HTTPException(404, "Timeline item not found.")
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(p.timeline):
        p.timeline[idx], p.timeline[swap] = p.timeline[swap], p.timeline[idx]
    s.save(p)
    return {"ok": True}


@router.delete("/projects/{project_id}/timeline/{item_id}")
def delete_item(project_id: str, item_id: str):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    p.timeline = [it for it in p.timeline if it.id != item_id]
    s.save(p)
    return {"ok": True}


# ── regeneration ───────────────────────────────────────────────

def _regenerate_wrapper(project_id: str, kind: str, section_index: int = -1, instruction: str = ""):
    """Runs synchronously (single LLM call) so the UI can show a spinner."""
    s = store()
    p = s.get(project_id)
    if not p or not p.story:
        raise HTTPException(404, "Nothing generated yet.")
    try:
        if kind == "story":
            p.status = "processing"
            s.save(p)
            run_generation(s, project_id)
            return store().get(project_id).model_dump()
        elif kind == "captions":
            style = p.settings.caption_style
            for item in p.timeline:
                item.captions = caption_service.build_captions(
                    item.voiceover, item.caption, item.duration, style, item.emphasis_words)
            s.save(p)
            return p.model_dump()
        elif kind == "section":
            if not (0 <= section_index < len(p.story.segments)):
                raise HTTPException(404, "Section not found.")
            seg = regenerate_section(p.story, section_index, instruction)
            # sync into matching timeline item
            item = p.timeline[section_index] if section_index < len(p.timeline) else None
            if item:
                item.voiceover = seg.voiceover
                item.caption = seg.caption
                item.emphasis_words = seg.emphasis_words
                item.visual_instruction = seg.visual_instruction
                item.captions = caption_service.build_captions(
                    seg.voiceover, seg.caption, item.duration,
                    p.settings.caption_style, seg.emphasis_words)
            s.save(p)
            return p.model_dump()
    except NagrikError as exc:
        raise HTTPException(exc.status_code, detail=exc.payload)


@router.post("/projects/{project_id}/regenerate/story")
def regenerate_story(project_id: str):
    result = _regenerate_wrapper(project_id, "story")
    return {"ok": True, "project": result}


@router.post("/projects/{project_id}/regenerate/captions")
def regenerate_captions(project_id: str):
    return {"ok": True, "project": _regenerate_wrapper(project_id, "captions")}


@router.post("/projects/{project_id}/regenerate/section/{index}")
def regenerate_section_api(project_id: str, index: int, body: Optional[dict] = None):
    instruction = (body or {}).get("instruction", "")
    return {"ok": True, "project": _regenerate_wrapper(project_id, "section", index, instruction)}


# ── music / captions style ─────────────────────────────────────

@router.post("/projects/{project_id}/music")
def set_music(project_id: str, body: MusicPatch):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    # support "none" to remove music entirely
    if body.category == "none":
        p.music = MusicSelection(category="none", track="", reason="No music — clean audio")
        p.settings.music_category = "none"
        # invalidate previous export so user must re-export to hear the change
        if p.render.status == "done":
            p.render.status = "idle"
            p.render.stage = "Music changed — re-export to apply"
        s.save(p)
        return {"ok": True, "music": p.music.model_dump()}
    category, reason = audio_service.recommend(p.settings)
    if body.category != "auto":
        category, reason = body.category, f"Manually selected — {body.category.replace('_', ' ').title()}."
    track = audio_service.resolve_track(category)
    p.music = MusicSelection(
        category=category, track=track.name if track else "", reason=reason)
    p.settings.music_category = category
    # changing music invalidates previous export
    if p.render.status == "done":
        p.render.status = "idle"
        p.render.stage = "Music changed — re-export to apply"
    s.save(p)
    return {"ok": True, "music": p.music.model_dump()}


@router.post("/projects/{project_id}/caption-style")
def set_caption_style(project_id: str, body: dict):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    style = body.get("style", "nagrik")
    if style not in caption_service.CAPTION_STYLES:
        raise HTTPException(400, "Unknown caption style.")
    p.settings.caption_style = style
    for item in p.timeline:
        item.captions = caption_service.build_captions(
            item.voiceover, item.caption, item.duration, style, item.emphasis_words)
    if p.render.status == "done":
        p.render.status = "idle"
        p.render.stage = "Caption style changed — re-export to apply"
    s.save(p)
    return {"ok": True}


# ── export / render ────────────────────────────────────────────

_render_threads = {}


@router.post("/projects/{project_id}/export")
def export_reel(project_id: str):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    if not p.timeline:
        raise HTTPException(400, "Generate a reel before exporting.")
    if p.render.status == "rendering":
        return {"ok": True, "status": "already_running"}
    p.render = RenderState(status="rendering", progress=0.0, stage="Preparing footage")
    p.error = None
    s.save(p)

    def work():
        storage = get_storage()
        project_dir = storage.project_dir(project_id)

        def on_stage(stage: str, progress: float):
            proj = s.get(project_id)
            if proj is None or proj.render.status != "rendering":
                return  # deleted or cancelled
            proj.render.progress = progress
            proj.render.stage = stage
            s.save(proj)

        try:
            proj = s.get(project_id)
            out = render_reel(proj, project_dir, on_stage)
            fresh = s.get(project_id)
            fresh.render.status = "done"
            fresh.render.progress = 1.0
            fresh.render.stage = "Done"
            fresh.render.output_path = str(out.relative_to(project_dir))
            fresh.render.size_bytes = out.stat().st_size
            fresh.status = "exported"
            s.save(fresh)
        except (RenderError, Exception) as exc:
            fresh = s.get(project_id)
            fresh.render.status = "error"
            fresh.render.stage = ""
            fresh.render.error = str(exc)[:500]
            s.save(fresh)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    return {"ok": True, "status": "started"}


@router.post("/projects/{project_id}/export/cancel")
def cancel_export(project_id: str):
    s = store()
    p = s.get(project_id)
    if not p:
        raise HTTPException(404, "Project not found.")
    if p.render.status == "rendering":
        p.render.status = "idle"
        p.render.stage = "Cancelled"
        s.save(p)
    return {"ok": True}


@router.get("/projects/{project_id}/download")
def download_reel(project_id: str):
    p = store().get(project_id)
    if not p or not p.render.output_path:
        raise HTTPException(404, "No exported reel yet.")
    path = get_storage().project_dir(project_id) / p.render.output_path
    if not path.exists():
        raise HTTPException(404, "Exported file missing.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


# ── media serving ──────────────────────────────────────────────

@router.get("/media/{project_id}/{relpath:path}")
def serve_media(project_id: str, relpath: str):
    base = get_storage().project_dir(project_id, create=False)
    path = (base / relpath).resolve()
    if not str(path).startswith(str(base.resolve())) or not path.exists():
        raise HTTPException(404)
    media_types = {
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
        ".jpg": "image/jpeg", ".png": "image/png", ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
    }
    mt = media_types.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=mt)


@router.get("/assets/music/{name}")
def serve_music(name: str):
    """Royalty-free bundled music beds for the in-browser preview."""
    safe = Path(name).name
    path = get_settings().assets_dir / "music" / safe
    if not path.exists() or ".." in name:
        raise HTTPException(404)
    mt = {"m4a": "audio/mp4", ".mp3": "audio/mpeg"}.get(path.suffix.lower(), "audio/mpeg")
    return FileResponse(path, media_type=mt)
