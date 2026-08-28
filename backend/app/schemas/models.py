"""Pydantic schemas shared across services and API."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Settings / inputs ─────────────────────────────────────────
class ProjectSettings(BaseModel):
    duration_target: int = 45            # seconds: 15/30/45/60/custom
    language: str = "English"            # English | Hindi | Hinglish (extensible)
    tone: str = "Civic Awareness"        # Breaking News | Informative | Investigative | Civic Awareness | Neutral | Youth-focused | Serious | Explainer
    platform: str = "9:16"               # Instagram Reels | YouTube Shorts | 9:16
    caption_style: str = "nagrik"        # clean | bold_editorial | highlight | nagrik
    watermark: bool = True
    voiceover: str = "original"          # original | off | ai
    music_category: str = "auto"         # auto | serious_news | investigative | energetic | emotional | civic | modern | minimal | none
    frame: bool = False                  # branded Nagrik frame (burgundy/gold) around 9:16


class VideoMeta(BaseModel):
    id: str
    filename: str
    path: str                            # relative path inside project dir
    duration: float = 0.0
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    has_audio: bool = False
    fps: float = 30.0
    thumbnail: Optional[str] = None      # relative path


# ── Transcript & analysis ─────────────────────────────────────
class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    provider: str = ""
    language: Optional[str] = None
    segments: List[TranscriptSegment] = Field(default_factory=list)
    error: Optional[str] = None


class Moment(BaseModel):
    """A scored window of raw footage."""
    start: float
    end: float
    score: float                          # 0..1 importance
    tags: List[str] = Field(default_factory=list)   # e.g. speech, silence, scene_change
    transcript: Optional[str] = None


class Analysis(BaseModel):
    moments: List[Moment] = Field(default_factory=list)
    silence: List[List[float]] = Field(default_factory=list)
    scene_changes: List[float] = Field(default_factory=list)


# ── Story (LLM output) ────────────────────────────────────────
class StorySegment(BaseModel):
    order: int
    section: str = "context"              # hook | context | development | key_fact | impact | ending
    duration: float = 4.0
    voiceover: str = ""
    caption: str = ""                     # large overlay text
    visual_instruction: str = ""
    emphasis_words: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


class SourceFact(BaseModel):
    fact: str
    origin: str = "user_overview"         # user_overview only — AI never adds facts


class Story(BaseModel):
    hook: str = ""
    headline: str = ""
    story: str = ""
    segments: List[StorySegment] = Field(default_factory=list)
    ending: str = ""
    cta: str = ""
    source_facts: List[SourceFact] = Field(default_factory=list)
    creative_note: str = ""               # LLM self-audit: where it added creative framing
    warnings: List[str] = Field(default_factory=list)


# ── Timeline ──────────────────────────────────────────────────
class CaptionUnit(BaseModel):
    text: str
    start: float                          # relative to timeline item start
    duration: float
    emphasis: List[str] = Field(default_factory=list)


class ClipRef(BaseModel):
    video_id: str
    filename: str = ""
    start: float
    end: float


class TimelineItem(BaseModel):
    id: str
    type: str                             # hook | context | development | key_fact | impact | ending
    label: str = ""                       # display label e.g. HOOK
    caption: str = ""
    voiceover: str = ""
    emphasis_words: List[str] = Field(default_factory=list)
    visual_instruction: str = ""
    clip: Optional[ClipRef] = None
    duration: float = 4.0
    captions: List[CaptionUnit] = Field(default_factory=list)
    source_facts_used: List[str] = Field(default_factory=list)


class MusicSelection(BaseModel):
    category: str = "minimal"
    track: str = ""                       # file name in assets/music
    reason: str = ""


# ── Pipeline state ────────────────────────────────────────────
class StepState(BaseModel):
    state: str = "pending"                # pending | running | done | skipped | error
    message: str = ""


class RenderState(BaseModel):
    status: str = "idle"                  # idle | rendering | done | error
    progress: float = 0.0                 # 0..1
    stage: str = ""
    output_path: Optional[str] = None
    size_bytes: int = 0
    error: Optional[str] = None


class Project(BaseModel):
    id: str
    title: str = "Untitled Reel"
    created_at: str = ""
    updated_at: str = ""
    status: str = "draft"                 # draft | processing | ready | error | exported
    overview: str = ""
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    videos: List[VideoMeta] = Field(default_factory=list)
    transcript: Optional[Transcript] = None
    analysis: Optional[Analysis] = None
    story: Optional[Story] = None
    timeline: List[TimelineItem] = Field(default_factory=list)
    music: Optional[MusicSelection] = None
    steps: Dict[str, StepState] = Field(default_factory=dict)
    render: RenderState = Field(default_factory=RenderState)
    error: Optional[Dict[str, Any]] = None

    def touch(self, ts: str) -> None:
        self.updated_at = ts


# ── API request bodies ────────────────────────────────────────
class ProjectCreate(BaseModel):
    title: str = "Untitled Reel"
    overview: str = ""
    settings: ProjectSettings = Field(default_factory=ProjectSettings)


class ProjectPatch(BaseModel):
    title: Optional[str] = None
    overview: Optional[str] = None
    settings: Optional[ProjectSettings] = None


class TimelinePatch(BaseModel):
    items: List[TimelineItem]


class MusicPatch(BaseModel):
    category: str


class CaptionStylePatch(BaseModel):
    style: str


def step_names() -> List[str]:
    return [
        "overview",
        "transcription",
        "moments",
        "story",
        "clips",
        "captions",
        "music",
        "preview",
    ]
