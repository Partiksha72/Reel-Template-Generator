# नागरिक — Nagrik

**Civic Sense India · AI-powered civic news reels**

Turn raw footage + a story overview into a polished, captioned, branded **9:16 reel** —
script, clip selection, captions, music and export handled by AI with a strict fact-safety contract.

```
RAW NEWS ──▶ STORY ──▶ EDIT ──▶ REEL
```

---

## What it does

| Stage | Detail |
|---|---|
| **Story** | Paste notes / article summary / bullet points. The LLM turns them into a structured reel script (hook → context → key facts → impact → CTA) as validated JSON. |
| **Footage** | Drag-and-drop MP4/MOV/WebM (multiple files). Metadata, duration, resolution and thumbnails are extracted via ffprobe. |
| **Transcription** | Local `faster-whisper` (no key needed) or OpenAI Whisper API. Timestamped segments feed clip matching. |
| **Clip selection** | Deterministic heuristic matcher: transcript↔script keyword relevance, silence avoidance, scene-change cut points. Fully editable afterwards. |
| **Captions** | 2–7-word mobile-first units, 4 styles (incl. branded **Nagrik Default**), gold emphasis words, rendered with bundled fonts and burned in via FFmpeg overlays. |
| **Music** | Royalty-free beds synthesized in-house (`serious_news`, `investigative`, `energetic`, `emotional`, `civic`, `modern`, `minimal`), auto-matched to tone and side-chain ducked under speech. |
| **Preview** | True 9:16 player that chains your source clips with live captions, watermark and music — before you commit to a render. |
| **Export** | Two-pass FFmpeg render to H.264 MP4 1080×1920 @30fps with real progress reporting, then download. |

### Fact safety (important)

Nagrik is a news product, so it never invents material:

- The story prompt forbids fabricated statistics, quotes, names, dates or claims.
- Every generated script carries an audit trail: **source facts** (traced back to your overview,
  flagged `verified` / `review`) vs **creative copy** (declared by the model).
- Missing information is phrased neutrally, never filled in.
- The editor shows the full audit panel; exports stay honest.

---

## Quick start

Requirements: **Python 3.9+**, **Node 18+**, **FFmpeg** (`brew install ffmpeg`).

```bash
# 1 · configure
cp .env.example .env          # then add your LLM_API_KEY (OpenAI, Groq, Ollama…)

# 2 · backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/generate_music.py       # once: synth royalty-free music beds
.venv/bin/python scripts/generate_watermark.py   # once: render brand watermark PNG
.venv/bin/uvicorn app.main:app --port 8000

# 3 · frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

Or use the Makefile:

```bash
make setup    # venv + deps + assets + npm install
make api      # backend on :8000
make web      # frontend on :3000
make e2e      # end-to-end pipeline check (no API key needed)
```

> **No LLM key?** Everything except story generation still works. The app shows a clear
> configuration error on the generation step instead of pretending — see `/settings`.
> Works with any OpenAI-compatible endpoint: set `LLM_BASE_URL`
> (e.g. `https://api.groq.com/openai/v1`) and `LLM_MODEL`.

---

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | Story generation (OpenAI-compatible) |
| `STT_PROVIDER` | `local` (faster-whisper, default) or `openai` |
| `STT_MODEL` | whisper size: tiny / base / small / medium |
| `TTS_PROVIDER` / `TTS_API_KEY` / `TTS_VOICE` | optional AI voiceover (`openai`) |
| `DATA_DIR` | local storage root (default `./data`) |
| `MAX_UPLOAD_MB` | upload limit (default 2048) |

Provider abstractions live in `backend/app/services/{llm,transcription,tts}_service.py` —
add a provider by implementing one small class.

---

## Project structure

```
backend/
  app/
    api/routes.py            REST API
    core/                    config (.env), storage abstraction, errors
    schemas/models.py        shared pydantic models (project, story, timeline…)
    services/
      video_service.py       validation, ffprobe metadata, thumbnails
      transcription_service.py  STT providers (local whisper / OpenAI)
      llm_service.py         OpenAI-compatible chat client + JSON parsing
      story_service.py       fact-safe prompts, JSON validation, fact audit
      clip_selection_service.py transcript/visual scoring → timeline
      caption_service.py     caption chunking, styles, Pillow PNG rendering
      audio_service.py       music registry + tone→category recommendation
      rendering_service.py   two-pass FFmpeg composition w/ progress
      tts_service.py         optional voiceover providers
      project_service.py     persistence + pipeline orchestration
    assets/                  fonts (OFL), music (generated), watermark
frontend/
  app/                       dashboard, create, projects, settings pages
  components/                PreviewPlayer, TimelinePanel, ProcessingScreen…
  lib/                       typed API client
scripts/                     asset generators + e2e check
```

## Design decisions

- **FFmpeg-only editing.** No heavy edit frameworks. Clips are normalized (scale/crop/fps)
  and concatenated in pass A; captions/watermark/audio mix happen in pass B. Progress is
  parsed from ffmpeg's own output — never faked.
- **PNG-overlay captions instead of libass.** Many FFmpeg builds ship without libass/drawtext;
  rendering captions as transparent PNGs with the bundled brand fonts works everywhere and
  gives pixel-perfect typography.
- **Local-first storage.** Projects are JSON on disk under `data/projects/<id>/`. The
  `Storage` interface is ready for S3/Azure implementations.
- **News ingestion later.** The pipeline takes an "overview" string; a future URL/RSS ingester
  only needs to produce that string. No MVP dependency.

## Regenerating assets

```bash
cd backend
.venv/bin/python scripts/generate_music.py       # royalty-free music beds → app/assets/music
.venv/bin/python scripts/generate_watermark.py   # watermark overlay → app/assets/watermark
```

Fonts are SIL-OFL licensed (Anton, Archivo Black, Inter, Noto Sans Devanagari).
Music beds are procedurally synthesized — no copyrighted material.

Replace `frontend/public/logo.svg` with the official logo file if provided; the UI mark
lives inline in `frontend/app/layout.tsx`.
