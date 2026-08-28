"""FFmpeg rendering orchestration.

Two honest passes with real progress (parsed from ffmpeg's own `time=` output,
never fabricated):
  Pass A "Processing clips" — trim/scale/crop every timeline clip to a
                             1080x1920 30fps base and concat A/V.
  Pass B "Rendering"        — burn ASS captions, overlay the Nagrik watermark
                              and mix speech + ducked music into the final MP4.
"""
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..core.config import get_settings
from ..schemas.models import Project, TimelineItem

W = 1080
H = 1920
FPS = 30


class RenderError(RuntimeError):
    pass


def cancel_check(should_cancel) -> None:
    if should_cancel and should_cancel():
        raise RenderError("Render cancelled.")


def _run_ffmpeg_with_progress(
    cmd: List[str], total_seconds: float, on_progress: Callable[[float], None]
) -> None:
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, bufsize=1,
    )
    time_re = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")
    tail_lines: List[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        stripped = line.strip()
        if stripped and not stripped.startswith(("frame=", "size=", "fps=")):
            tail_lines.append(stripped)
            tail_lines = tail_lines[-12:]
        m = time_re.search(line)
        if m and total_seconds > 0:
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            on_progress(min(1.0, max(0.0, t / total_seconds)))
    code = process.wait()
    if code != 0:
        detail = "\n".join(tail_lines[-8:])
        raise RenderError(f"ffmpeg exited with code {code}.\n{detail}")


def _probe_ok(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _has_audio_stream(path: Path) -> bool:
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "a", "-show_entries",
             "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return bool(proc.stdout.strip())
    except Exception:
        return False


def _escape_filter_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:")


def render_reel(
    project: Project,
    project_dir: Path,
    on_stage: Callable[[str, float], None],
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Path:
    """Render the reel; returns path to the final mp4."""
    work = project_dir / "work"
    renders = project_dir / "renders"
    renders.mkdir(parents=True, exist_ok=True)

    items = [it for it in project.timeline if it.clip and it.duration >= 0.4]
    if not items:
        raise RenderError("Nothing to render — the timeline has no clips.")

    total_duration = sum(it.duration for it in items)
    video_paths: Dict[str, Path] = {v.id: project_dir / v.path for v in project.videos}

    # ── validate all sources up front ──────────────────────────
    on_stage("Preparing footage", 0.01)
    for it in items:
        p = video_paths.get(it.clip.video_id)
        if not p or not _probe_ok(p):
            raise RenderError(f"Source footage for '{it.label or it.type}' is missing ({it.clip.video_id}).")

    # ── pass A ──────────────────────────────────────────────────
    on_stage("Processing clips", 0.05)
    base_path = work / "base.mp4"

    def progress_a(frac: float) -> None:
        on_stage("Processing clips", 0.05 + frac * 0.40)

    _render_base(items, video_paths, base_path, total_duration, progress_a, should_cancel)

    # ── pass B ──────────────────────────────────────────────────
    on_stage("Rendering (captions · branding · audio)", 0.48)

    def progress_b(frac: float) -> None:
        on_stage("Rendering (captions · branding · audio)", 0.48 + frac * 0.47)

    safe_title = re.sub(r"[^A-Za-z0-9]+", "_", project.title or "Reel").strip("_")[:60]
    final_path = renders / f"Nagrik_{safe_title}.mp4"
    _render_final(project, items, base_path, project_dir, work, final_path,
                  total_duration, progress_b, should_cancel)

    # ── cleanup temp artifacts ─────────────────────────────────
    on_stage("Finalizing", 0.97)
    try:
        if work.exists():
            shutil.rmtree(work)
    except OSError:
        pass
    on_stage("Done", 1.0)
    return final_path


# ── pass A: normalized base ────────────────────────────────────

def _render_base(items: List[TimelineItem], video_paths: Dict[str, Path], out: Path,
                 total: float, progress, should_cancel) -> None:
    cmd: List[str] = ["ffmpeg", "-y", "-v", "warning", "-stats"]
    v_filters: List[str] = []
    a_filters: List[str] = []

    input_idx = 0
    for i, it in enumerate(items):
        cancel_check(should_cancel)
        src = video_paths[it.clip.video_id]
        has_audio = _has_audio_stream(src)
        start = max(0.0, float(it.clip.start))
        dur = float(it.duration)
        # video input
        cmd += ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
        v_filters.append(
            f"[{input_idx}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},fps={FPS},setsar=1[v{i}]"
        )
        video_input_idx = input_idx
        input_idx += 1
        if has_audio:
            a_filters.append(f"[{video_input_idx}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}]")
        else:
            # placeholder silence so concat stays aligned
            cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
            a_filters.append(f"[{input_idx}:a]aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
            input_idx += 1

    n = len(items)
    graph = ";".join(v_filters + a_filters)
    # concat consumes interleaved pairs: [v0][a0][v1][a1]…
    graph += ";" + "".join(f"[v{i}][a{i}]" for i in range(n))
    graph += f"concat=n={n}:v=1:a=1[vout][aout]"
    cmd += ["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out)]
    try:
        _run_ffmpeg_with_progress(cmd, total, progress)
    except RenderError as exc:
        raise RenderError(f"While processing footage: {exc}") from exc


# ── pass B: captions, branding, audio mix ──────────────────────

def _build_caption_events(project: Project, items: List[TimelineItem]) -> List[dict]:
    events: List[dict] = []
    t = 0.0
    for it in items:
        for unit in it.captions:
            if unit.text and unit.text.strip():
                events.append({
                    "text": unit.text,
                    "start": t + float(unit.start),
                    "duration": float(unit.duration),
                    "emphasis": list(unit.emphasis),
                })
        t += float(it.duration)
    return events


def _render_final(project: Project, items: List[TimelineItem], base: Path,
                  project_dir: Path, work: Path, out: Path, total: float,
                  progress, should_cancel) -> None:
    cancel_check(should_cancel)
    from .caption_service import build_caption_overlays, get_caption_style

    settings = get_settings()

    # ── captions → transparent PNGs ────────────────────────────
    overlays = build_caption_overlays(
        _build_caption_events(project, items),
        project.settings.caption_style,
        work,
    )

    # ── inputs: base video, caption PNGs, watermark, then audio ─
    inputs: List[List[str]] = [["-i", str(base)]]
    chain: List[str] = []
    for ov in overlays:
        inputs.append(["-i", str(ov["png"])])

    wm_idx = None
    # If frame is enabled, it already contains the channel header — hide the
    # floating watermark to avoid double-branding.
    show_watermark = project.settings.watermark and not project.settings.frame
    watermark = settings.assets_dir / "watermark" / "watermark.png"
    if show_watermark and watermark.exists():
        wm_scaled = work / "watermark_small.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(watermark),
             "-vf", "scale=300:-1,format=rgba", str(wm_scaled)],
            check=True, capture_output=True, timeout=60,
        )
        wm_idx = len(inputs)
        inputs.append(["-i", str(wm_scaled)])

    # Branded frame (top header + side/bottom borders) — final video overlay
    frame_idx = None
    frame_path = settings.assets_dir / "frame" / "frame.png"
    if project.settings.frame and frame_path.exists():
        frame_idx = len(inputs)
        inputs.append(["-i", str(frame_path)])

    # ── speech source decision ─────────────────────────────────
    #   None -> silent, "[0:a]" -> footage audio, "[speech]" -> TTS mix
    speech_label: Optional[str]
    if project.settings.voiceover == "off":
        speech_label = None
    elif project.settings.voiceover == "ai":
        available = [(it, project_dir / "work" / f"tts_{it.id}.mp3")
                     for it in items if (project_dir / "work" / f"tts_{it.id}.mp3").exists()]
        if len(available) >= max(1, len(items) // 2):
            offset = 0.0
            labels: List[str] = []
            for it, tf in available:
                ms = int(offset * 1000)
                idx = len(inputs)
                inputs.append(["-i", str(tf)])
                chain.append(
                    f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,"
                    f"adelay={ms}|{ms}[tts{idx}]"
                )
                labels.append(f"[tts{idx}]")
                offset += float(it.duration)
            chain.append(
                "".join(labels) +
                f"amix=inputs={len(labels)}:duration=longest:normalize=0,volume=1.35[speech]"
            )
            speech_label = "[speech]"
        else:
            # AI voiceover requested but clips missing — fall back to footage audio
            speech_label = "[0:a]"
    else:
        speech_label = "[0:a]"

    # music input (always last)
    music_idx = None
    music_file: Optional[Path] = None
    if project.music and project.music.track:
        cand = settings.assets_dir / "music" / project.music.track
        if cand.exists():
            music_file = cand
    if music_file:
        music_idx = len(inputs)
        inputs.append(["-stream_loop", "-1", "-i", str(music_file)])

    # ── audio graph ────────────────────────────────────────────
    if music_file:
        base_vol = {"minimal": 0.5, "emotional": 0.45}.get(
            (project.music.category if project.music else ""), 0.38)
        fade_start = max(0.0, total - 1.6)
        chain.append(
            f"[{music_idx}:a]volume={base_vol},afade=t=in:d=1.2,"
            f"afade=t=out:st={fade_start:.2f}:d=1.6[musicraw]"
        )
        if speech_label:
            # split speech: one copy keys the ducking, the other is mixed
            chain.append(f"{speech_label}asplit=2[spk_key][spk_mix]")
            chain.append("[musicraw][spk_key]sidechaincompress=threshold=0.02:ratio=10:"
                         "attack=25:release=450:makeup=1[mduck]")
            chain.append("[spk_mix][mduck]amix=inputs=2:duration=first:normalize=0,"
                         "alimiter=limit=0.95[aout]")
        else:
            chain.append("[musicraw]alimiter=limit=0.9[aout]")
        audio_map = "[aout]"
    elif speech_label:
        chain.append(f"{speech_label}alimiter=limit=0.95[aout]")
        audio_map = "[aout]"
    else:
        inputs.append(["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo"])
        audio_map = f"[{len(inputs) - 1}:a]"

    # ── video graph: overlay each caption PNG in its time window ─
    style_cfg = get_caption_style(project.settings.caption_style)
    bottom = style_cfg.get("bottom_offset", 340)
    prev = "[0:v]"
    for n, ov in enumerate(overlays):
        idx = 1 + n                                   # caption input index
        out_lbl = f"[vcap{n}]"
        chain.append(
            f"{prev}[{idx}:v]overlay=(main_w-overlay_w)/2:"
            f"main_h-overlay_h-{bottom}:enable='between(t,{ov['start']},{ov['end']})'"
            + out_lbl
        )
        prev = out_lbl

    # watermark (skipped when frame is active — frame has its own header)
    if wm_idx is not None:
        chain.append(f"{prev}[{wm_idx}:v]overlay=40:40[wmv]")
        prev = "[wmv]"

    # branded frame — always last, covers the full canvas
    if frame_idx is not None:
        chain.append(f"{prev}[{frame_idx}:v]overlay=0:0[vfin]")
        video_map = "[vfin]"
    elif overlays or wm_idx is not None:
        # rename last video label to vfin
        chain[-1] = chain[-1].replace(prev, "[vfin]")
        video_map = "[vfin]"
    else:
        chain.append("[0:v]null[vfin]")
        video_map = "[vfin]"

    cmd: List[str] = ["ffmpeg", "-y", "-v", "warning", "-stats"]
    for part in inputs:
        cmd += part
    cmd += ["-filter_complex", ";".join(chain),
            "-map", video_map, "-map", audio_map,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-r", str(FPS), "-movflags", "+faststart", str(out)]

    cancel_check(should_cancel)
    try:
        _run_ffmpeg_with_progress(cmd, total, progress)
    except RenderError as exc:
        raise RenderError(f"While rendering: {exc}") from exc
