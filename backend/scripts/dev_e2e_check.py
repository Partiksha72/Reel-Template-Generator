#!/usr/bin/env python3
"""End-to-end pipeline check for Nagrik.

Runs the REAL services (transcription, clip selection, captions, FFmpeg render)
against synthetic footage. The LLM story step is replaced with a canned valid
response so the check runs without any API key — everything else is production
code paths via the running API server + in-process pipeline.

    cd backend && .venv/bin/python scripts/dev_e2e_check.py
"""
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

API = "http://127.0.0.1:8000"
TMP = Path(tempfile.mkdtemp(prefix="nagrik_e2e_"))

STORY_JSON = {
    "hook": "Delhi just changed its parking rules.",
    "headline": "Delhi's New Parking Rules",
    "story": "A new civic policy changes how parking is managed across Delhi. Residents worry about enforcement.",
    "segments": [
        {"order": 1, "section": "hook", "duration": 3,
         "voiceover": "Delhi just changed its parking rules.",
         "caption": "DELHI'S PARKING RULES JUST CHANGED",
         "visual_instruction": "city street with parked cars",
         "emphasis_words": ["changed"],
         "keywords": ["delhi", "street", "cars", "parking"]},
        {"order": 2, "section": "context", "duration": 4,
         "voiceover": "A new civic policy will manage parking in major areas.",
         "caption": "A NEW CIVIC POLICY IS HERE",
         "visual_instruction": "officials or signage",
         "emphasis_words": ["policy"], "keywords": ["civic", "policy", "areas", "manage"]},
        {"order": 3, "section": "key_fact", "duration": 4,
         "voiceover": "It affects residential and commercial neighbourhoods.",
         "caption": "YOUR STREET IS AFFECTED",
         "visual_instruction": "residents speaking",
         "emphasis_words": ["affected"], "keywords": ["residential", "commercial", "neighbourhoods", "people"]},
        {"order": 4, "section": "impact", "duration": 4,
         "voiceover": "Residents have raised concerns about enforcement.",
         "caption": "RESIDENTS HAVE QUESTIONS",
         "visual_instruction": "crowd or interview",
         "emphasis_words": ["concerns"], "keywords": ["residents", "raised", "concerns", "enforcement"]},
        {"order": 5, "section": "ending", "duration": 3.5,
         "voiceover": "Would this work in your city?",
         "caption": "WOULD THIS WORK IN YOUR CITY?",
         "visual_instruction": "wide city shot",
         "emphasis_words": ["your"], "keywords": ["city", "wide", "view"]},
    ],
    "ending": "Would this work in your city?",
    "cta": "Follow Nagrik for more civic updates.",
    "source_facts": [
        "A new civic policy has been announced in Delhi.",
        "The policy affects parking management in residential and commercial areas.",
        "Residents have raised concerns about implementation and enforcement.",
    ],
    "creative_note": "Hook phrasing and captions are creative framing only.",
    "warnings": [],
}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 900), **kw)


def make_test_video(path: Path, seconds: int, freq: int):
    """Synthetic footage: moving test pattern + beeping audio with quiet gaps."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:duration={seconds}",
        "-f", "lavfi", "-i",
        f"sine=frequency={freq}:sample_rate=44100:duration={seconds},"
        f"volume='if(lt(mod(t,6),4),0.8,0.001)':eval=frame",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
        str(path),
    ]
    r = sh(cmd)
    assert r.returncode == 0, r.stderr[-400:]
    print(f"  ✓ {path.name} ({seconds}s)")


def api(method: str, path: str, raw_body=None, files=None):
    url = f"{API}{path}"
    if files:
        boundary = "----nagrikrandom1234567890"
        body = b""
        for field, (fname, data) in files.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\nContent-Type: video/mp4\r\n\r\n".encode() + data + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    else:
        data = json.dumps(raw_body).encode() if raw_body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=300) as res:
        return json.loads(res.read())


def main():
    print("── Nagrik E2E check ─────────────────────────────")

    # 0 · health
    h = api("GET", "/api/health")
    assert h["ffmpeg"]["available"], "FFmpeg missing"
    print(f"0 · health ok · ffmpeg {h['ffmpeg']['version']} · llm configured={h['providers']['llm']['configured']}")

    # 1 · synthetic footage
    print("1 · generating synthetic footage…")
    v1 = TMP / "field_footage_a.mp4"
    v2 = TMP / "field_footage_b.mp4"
    make_test_video(v1, 22, 330)
    make_test_video(v2, 12, 392)

    # 2 · create project + upload via HTTP
    proj = api("POST", "/api/projects", {
        "title": "E2E Parking Rules Reel",
        "overview": ("A new civic policy has been announced in Delhi. The policy will affect how parking "
                     "is managed in major residential and commercial areas. Residents have raised "
                     "concerns about implementation and enforcement."),
        "settings": {"duration_target": 30, "language": "English", "tone": "Civic Awareness",
                     "platform": "Instagram Reels", "caption_style": "nagrik", "watermark": True,
                     "voiceover": "original", "music_category": "auto"},
    })
    pid = proj["id"]
    print(f"2 · project {pid}")

    up = api("POST", f"/api/projects/{pid}/videos", files={
        "files": (v1.name, v1.read_bytes()),
    })
    assert len(up["videos"]) == 1, f"upload 1 failed: {up['errors']}"
    up2 = api("POST", f"/api/projects/{pid}/videos", files={
        "files": (v2.name, v2.read_bytes()),
    })
    all_videos = up2["videos"]
    assert len(all_videos) == 2, f"expected 2 videos, got {len(all_videos)}"
    assert all(v["duration"] > 10 for v in all_videos), up["errors"]
    print(f"   uploaded {len(all_videos)} clips:", [f'{v["filename"]} {v["width"]}x{v["height"]} {v["duration"]}s' for v in all_videos])

    # 3 · run the pipeline in-process with a canned LLM story (real STT/clips/captions/music)
    print("3 · running generation pipeline (canned LLM, real services)…")
    from app.services import project_service as ps
    from app.services.story_service import validate_story, audit_facts
    
    canned_story = audit_facts(validate_story(STORY_JSON), proj["overview"])

    from app.core.storage import get_storage
    ps.generate_story = lambda overview, s, transcript_summary="": canned_story
    store = ps.ProjectStore(get_storage())
    t0 = time.time()
    ps.run_generation(store, pid)
    dt = time.time() - t0
    p = store.get(pid)

    # error surfaced?
    if p.status == "error":
        print("   PIPELINE ERROR:", json.dumps(p.error, indent=1))
        for k, st in p.steps.items():
            print(f"     - {k}: {st.state} {st.message[:120]}")
        sys.exit(1)

    print(f"   pipeline finished in {dt:.1f}s · status={p.status}")
    for k, st in p.steps.items():
        print(f"     - {k}: {st.state} · {st.message[:100]}")
    total = sum(i.duration for i in p.timeline)
    print(f"   timeline: {len(p.timeline)} sections, {total:.1f}s total "
          f"(target {p.settings.duration_target}s)")
    assert len(p.timeline) >= 4, "too few timeline items"
    caps = [u.text for i in p.timeline for u in i.captions]
    print(f"   captions sample: {caps[:4]}")
    assert all(len(c.split()) <= 9 for c in caps), "caption too long"
    assert p.music and p.music.track, "music missing"

    # 4 · export via HTTP (background thread inside server) & poll
    print("4 · exporting reel…")
    api("POST", f"/api/projects/{pid}/export")
    deadline = time.time() + 600
    while time.time() < deadline:
        pj = api("GET", f"/api/projects/{pid}")
        r = pj["render"]
        sys.stdout.write(f"\r   {r['stage']:<44} {int(r['progress']*100):>3}%  ")
        sys.stdout.flush()
        if r["status"] in ("done", "error"):
            print()
            if r["status"] == "error":
                print("   RENDER ERROR:", r["error"])
                sys.exit(1)
            break
        time.sleep(2)

    # 5 · download & probe output
    out = TMP / "out_reel.mp4"
    with urllib.request.urlopen(f"{API}/api/projects/{pid}/download", timeout=300) as res, open(out, "wb") as f:
        f.write(res.read())
    pr = sh(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(out)])
    meta = json.loads(pr.stdout)
    vstream = next(s for s in meta["streams"] if s["codec_type"] == "video")
    astream = next((s for s in meta["streams"] if s["codec_type"] == "audio"), None)
    w, hh = int(vstream["width"]), int(vstream["height"])
    dur = float(meta["format"]["duration"])
    size_mb = out.stat().st_size / 1e6
    print(f"5 · output: {w}x{hh} @ {vstream.get('avg_frame_rate')} · {dur:.1f}s · {size_mb:.1f} MB · codec={vstream['codec_name']} · audio={'yes' if astream else 'NO'}")
    assert (w, hh) == (1080, 1920), "wrong resolution"
    assert abs(dur - total) < 2.5, f"duration mismatch: {dur:.1f} vs {total:.1f}"
    assert vstream["codec_name"] == "h264"
    assert astream is not None, "no audio track"

    print("\n✅ E2E CHECK PASSED — upload → transcribe → story → clips → captions → music → render → export\n")
    print(f"   project id: {pid}  (inspect at http://localhost:3000/projects/{pid})")


if __name__ == "__main__":
    main()
