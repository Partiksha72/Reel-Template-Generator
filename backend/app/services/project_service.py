"""Project persistence (JSON on local disk) + generation pipeline orchestration."""
import datetime as _dt
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Optional

from ..core.errors import NagrikError
from ..core.storage import Storage, new_id
from ..schemas.models import (
    Analysis, MusicSelection, Project, ProjectCreate,
    StepState, TimelineItem, Transcript, step_names,
)
from . import audio_service, caption_service, clip_selection_service
from .story_service import generate_story
from .tts_service import get_tts_provider
from .video_service import total_duration


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class ProjectStore:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    # ── CRUD ───────────────────────────────────────────────────
    def _path(self, project_id: str) -> Path:
        return self.storage.project_dir(project_id) / "project.json"

    def save(self, project: Project) -> None:
        project.updated_at = now_iso()
        self._path(project.id).write_text(project.model_dump_json(indent=1), encoding="utf-8")

    def get(self, project_id: str) -> Optional[Project]:
        p = self._path(project_id)
        if not p.exists():
            return None
        try:
            return Project.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_all(self) -> List[Project]:
        root = self.storage.root / "projects"
        out: List[Project] = []
        if root.exists():
            for d in sorted(root.iterdir(), reverse=True):
                proj = self.get(d.name)
                if proj:
                    out.append(proj)
        out.sort(key=lambda x: x.created_at, reverse=True)
        return out

    def delete(self, project_id: str) -> bool:
        if self.get(project_id) is None:
            return False
        self.storage.delete_project(project_id)
        return True

    def create(self, body: ProjectCreate) -> Project:
        pid = new_id()
        project = Project(
            id=pid, title=body.title or "Untitled Reel", overview=body.overview,
            settings=body.settings, created_at=now_iso(),
            steps={name: StepState() for name in step_names()},
        )
        self.save(project)
        return project

    # ── helpers ────────────────────────────────────────────────
    @staticmethod
    def set_step(project: Project, name: str, state: str, message: str = "") -> None:
        project.steps[name] = StepState(state=state, message=message)


# ── generation pipeline (runs in background thread) ───────────

_pipeline_locks: Dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _lock_for(project_id: str) -> threading.Lock:
    with _registry_lock:
        if project_id not in _pipeline_locks:
            _pipeline_locks[project_id] = threading.Lock()
        return _pipeline_locks[project_id]


def run_generation(store: ProjectStore, project_id: str) -> None:
    """Full pipeline: transcribe → moments → story → clips → captions → music."""
    with _lock_for(project_id):
        project = store.get(project_id)
        if project is None:
            return
        project.status = "processing"
        project.error = None
        for name in step_names():
            store.set_step(project, name, "pending")
        store.save(project)

        try:
            _run_steps(store, project)
            project.status = "ready" if project.timeline else "error"
            if not project.timeline and project.error is None:
                project.error = {"step": "clips", "message": "No usable clips were produced."}
        except NagrikError as exc:
            project.status = "error"
            project.error = {"step": _failing_step(project), "message": exc.detail or exc.code,
                             "hint": getattr(exc, "hint", ""), "code": exc.code}
        except Exception as exc:  # pragma: no cover
            project.status = "error"
            project.error = {"step": _failing_step(project),
                             "message": f"{type(exc).__name__}: {exc}",
                             "detail": traceback.format_exc()[-600:]}
        store.save(project)


def _failing_step(project: Project) -> str:
    for name, st in project.steps.items():
        if st.state == "running":
            return name
    return "story"


def _run_steps(store: ProjectStore, project: Project) -> None:
    from .transcription_service import get_stt_provider

    project_dir = store.storage.project_dir(project.id)

    # 1 · overview
    store.set_step(project, "overview", "running")
    if not project.overview.strip():
        store.set_step(project, "overview", "done",
                       "No story overview provided — using transcript only.")
    else:
        words = len(project.overview.split())
        store.set_step(project, "overview", "done", f"Read {words} words of context.")
    store.save(project)

    # 2 · transcription
    store.set_step(project, "transcription", "running")
    store.save(project)
    transcript = None
    if total_duration(project.videos) > 0:
        provider = get_stt_provider()
        if not provider.configured():
            store.set_step(project, "transcription", "skipped", provider.configuration_hint())
        elif len(project.videos) == 1:
            src = project_dir / project.videos[0].path
            try:
                transcript = provider.transcribe(src, language=project.settings.language)
                store.set_step(project, "transcription", "done",
                               f"{len(transcript.segments)} spoken segments ({transcript.provider}).")
            except NagrikError as exc:
                transcript = None
                store.set_step(project, "transcription", "skipped",
                               exc.payload.get("message", "Transcription failed.") +
                               (f" Hint: {exc.hint}" if exc.hint else ""))
        else:
            # multi-file: transcribe each and offset timestamps
            all_segments = []
            offset = 0.0
            last_error = ""
            for v in project.videos:
                src = project_dir / v.path
                try:
                    t = provider.transcribe(src, language=project.settings.language)
                    for seg in t.segments:
                        seg.start += offset
                        seg.end += offset
                        all_segments.append(seg)
                except NagrikError as exc:
                    last_error = exc.payload.get("message", "")
                offset += v.duration
            if all_segments:
                transcript = Transcript(segments=all_segments, provider=getattr(provider, "name", ""))
                store.set_step(project, "transcription", "done",
                               f"{len(all_segments)} spoken segments across {len(project.videos)} files.")
            else:
                store.set_step(project, "transcription", "skipped",
                               last_error or "No speech detected across uploaded files.")

    # extract compressed audio once for STT providers that need it (local whisper reads directly)
    project.transcript = transcript
    store.save(project)

    # 3 · visual analysis / moments
    store.set_step(project, "moments", "running")
    store.save(project)
    from ..utils.ffmpeg import detect_scene_changes, detect_silences
    silences: List[List[float]] = []
    scenes: List[float] = []
    cursor = 0.0
    for v in project.videos:
        src = project_dir / v.path
        try:
            if v.has_audio:
                for a, b in detect_silences(src, v.duration):
                    if b - a > 0.35:
                        silences.append([round(a + cursor, 2), round(b + cursor, 2)])
            scenes.extend([round(s + cursor, 2) for s in detect_scene_changes(src)])
        except Exception:
            pass  # non-fatal: selection falls back to even spacing
        cursor += v.duration
        cursor += v.duration
    moments = clip_selection_service.build_analysis_moments(project.videos, transcript)
    project.analysis = Analysis(moments=moments, silence=silences, scene_changes=scenes)
    n_found = len(moments)
    store.set_step(project, "moments", "done",
                   f"Mapped {n_found} candidate windows, {len(silences)} quiet zones.")
    store.save(project)

    # 4 · story via LLM
    store.set_step(project, "story", "running")
    store.save(project)
    transcript_summary = ""
    if transcript and transcript.segments:
        joined = " ".join(seg.text for seg in transcript.segments)[:1500]
        transcript_summary = joined
    project.story = generate_story(
        project.overview, project.settings, transcript_summary=transcript_summary,
    )
    # normalize segment durations toward the target length (LLMs drift)
    seg_sum = sum(s.duration for s in project.story.segments)
    target = float(project.settings.duration_target)
    if seg_sum > 0 and 0.4 <= (target / seg_sum) <= 1.8:
        for s in project.story.segments:
            s.duration = round(min(12.0, max(1.5, s.duration * (target / seg_sum))), 1)
    n_segs = len(project.story.segments)
    warn = f" · {len(project.story.warnings)} fact warnings" if project.story.warnings else ""
    store.set_step(project, "story", "done",
                   f"Scripted {n_segs} sections{warn}.")
    store.save(project)

    # 5 · clip selection
    store.set_step(project, "clips", "running")
    store.save(project)
    ranges = {}
    cursor = 0.0
    for v in project.videos:
        ranges[v.id] = (cursor, cursor + v.duration)
        cursor += v.duration
    selector = clip_selection_service.ClipSelector(
        project.videos, transcript, project.analysis, video_ranges=ranges,
    )
    picks, selected_moments = selector.build_timeline(project.story)
    if not picks:
        raise NagrikError(status_code=422, code="no_clips",
                          message="Could not select any footage.",
                          hint="Upload at least one video longer than ~2 seconds.")
    timeline: List[TimelineItem] = []
    for seg, pick in zip(project.story.segments, picks):
        item = TimelineItem(
            id=new_id(),
            type=seg.section,
            label=seg.section.replace("_", " ").upper(),
            caption=seg.caption,
            voiceover=seg.voiceover,
            emphasis_words=list(seg.emphasis_words),
            visual_instruction=seg.visual_instruction,
            duration=float(pick["duration"]),
            source_facts_used=[sf.fact for sf in project.story.source_facts[:3]],
        )
        from ..schemas.models import ClipRef
        item.clip = ClipRef(video_id=pick["video_id"], filename=pick.get("filename", ""),
                            start=pick["start"], end=pick["end"])
        timeline.append(item)
    project.timeline = timeline
    store.set_step(project, "clips", "done",
                   f"Matched {len(picks)} clips (avg relevance "
                   f"{sum(p['score'] for p in picks) / max(1, len(picks)):.2f}).")
    store.save(project)

    # 6 · captions
    store.set_step(project, "captions", "running")
    store.save(project)
    style = project.settings.caption_style
    units_total = 0
    for item in project.timeline:
        item.captions = caption_service.build_captions(
            item.voiceover, item.caption, item.duration, style, item.emphasis_words,
        )
        units_total += len(item.captions)
    store.set_step(project, "captions", "done",
                   f"Built {units_total} caption units ({style} style).")
    store.save(project)

    # 7 · music
    store.set_step(project, "music", "running")
    store.save(project)
    category, reason = audio_service.recommend(project.settings)
    track_path = audio_service.resolve_track(category)
    project.music = MusicSelection(
        category=category,
        track=track_path.name if track_path else "",
        reason=reason,
    )
    store.set_step(project, "music", "done",
                   f"{category.replace('_', ' ').title()} — {reason}")
    store.save(project)

    # 7b · AI voiceover (optional)
    if project.settings.voiceover == "ai":
        tts_provider = get_tts_provider()
        if not tts_provider.configured():
            store.set_step(project, "voiceover", "error",
                           "AI voiceover needs a TTS provider — falling back to original audio. "
                           + tts_provider.configuration_hint())
            project.settings.voiceover = "original"
        else:
            work = project_dir / "work"
            work.mkdir(parents=True, exist_ok=True)
            ok = 0
            err = ""
            for item in project.timeline:
                text = item.voiceover or item.caption
                if not text:
                    continue
                dest = work / f"tts_{item.id}.mp3"
                try:
                    tts_provider.synthesize(text, dest)
                    from .tts_service import fit_audio_to_slot
                    fit_audio_to_slot(dest, item.duration)
                    ok += 1
                except NagrikError as exc:
                    err = exc.payload.get("message", "TTS failed")
            if ok:
                store.set_step(project, "voiceover", "done", f"Generated {ok} voiceover clips.")
                if err:
                    store.set_step(project, "voiceover", "done",
                                   f"Generated {ok} voiceover clips ({err}).")
            else:
                project.settings.voiceover = "original"
                store.set_step(project, "voiceover", "error",
                               "Voiceover failed — using original audio." + (f" ({err})" if err else ""))

    # 8 · preview plan (the editor plays source clips directly; nothing to pre-render)
    store.set_step(project, "preview", "done", "Preview ready.")
