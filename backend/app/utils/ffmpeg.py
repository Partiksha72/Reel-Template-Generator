"""Thin, safe wrappers around ffmpeg/ffprobe subprocess calls."""
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def run(cmd: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ffprobe_json(path: Path) -> Dict[str, Any]:
    """Return parsed ffprobe output for a media file."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = run(cmd, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path.name}: {proc.stderr.strip()[:300]}")
    return json.loads(proc.stdout or "{}")


def probe_media(path: Path) -> Dict[str, Any]:
    """Extract the fields Nagrik needs from any media file."""
    data = ffprobe_json(path)
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or 0.0)
    width = height = 0
    fps = 30.0
    has_audio = False
    has_video = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not has_video:
            has_video = True
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
            try:
                num, _, den = rate.partition("/")
                fps = float(num) / float(den or 1) if float(den or 1) else 30.0
            except Exception:
                fps = 30.0
        elif stream.get("codec_type") == "audio":
            has_audio = True
    return {
        "duration": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "has_audio": has_audio,
        "has_video": has_video,
    }


def extract_thumbnail(path: Path, dest: Path, at_seconds: float = 1.0) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(0.0, at_seconds):.2f}", "-i", str(path),
        "-frames:v", "1", "-vf", "scale=360:-2",
        str(dest),
    ]
    proc = run(cmd, timeout=60)
    return proc.returncode == 0 and dest.exists()


def detect_silences(path: Path, duration: float, noise_db: int = -35) -> List[List[float]]:
    """Return [start, end] pairs of silent stretches."""
    if duration <= 0:
        return []
    cmd = [
        "ffmpeg", "-y", "-i", str(path), "-af",
        f"silencedetect=noise={noise_db}dB:d=0.45", "-f", "null", "-",
    ]
    proc = run(cmd, timeout=300)
    silences: List[List[float]] = []
    start: Optional[float] = None
    for line in (proc.stderr or "").splitlines():
        line = line.strip()
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[1].strip().split(" ")[0])
            except ValueError:
                start = None
        elif "silence_end:" in line and start is not None:
            try:
                end = float(line.split("silence_end:")[1].strip().split(" ")[0])
                silences.append([round(start, 2), round(end, 2)])
            except ValueError:
                pass
            start = None
    if start is not None:
        silences.append([round(start, 2), round(duration, 2)])
    return silences


def detect_scene_changes(path: Path, threshold: float = 0.32) -> List[float]:
    """Timestamps where hard scene changes occur."""
    cmd = [
        "ffmpeg", "-y", "-i", str(path), "-filter_complex",
        f"select='gt(scene,{threshold})',metadata=print", "-f", "null", "-",
    ]
    proc = run(cmd, timeout=600)
    times: List[float] = []
    for line in (proc.stderr or "").splitlines():
        # selected frames print "frame:N ... pts_time:X"; select already filtered them
        if "pts_time:" in line:
            try:
                t = float(line.split("pts_time:")[1].split()[0])
                times.append(round(t, 2))
            except (ValueError, IndexError):
                continue
    return sorted(set(times))
