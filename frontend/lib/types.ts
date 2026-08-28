export interface ProjectSettings {
  duration_target: number;
  language: string;
  tone: string;
  platform: string;
  caption_style: string;
  watermark: boolean;
  voiceover: string;
  music_category: string;
  frame: boolean;
}

export interface VideoMeta {
  id: string;
  filename: string;
  path: string;
  duration: number;
  width: number;
  height: number;
  size_bytes: number;
  has_audio: boolean;
  fps: number;
  thumbnail: string | null;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  provider: string;
  language?: string | null;
  segments: TranscriptSegment[];
  error?: string | null;
}

export interface SourceFact {
  fact: string;
  origin: string;
}

export interface StorySegment {
  order: number;
  section: string;
  duration: number;
  voiceover: string;
  caption: string;
  visual_instruction: string;
  emphasis_words: string[];
  keywords: string[];
}

export interface Story {
  hook: string;
  headline: string;
  story: string;
  segments: StorySegment[];
  ending: string;
  cta: string;
  source_facts: SourceFact[];
  creative_note: string;
  warnings: string[];
}

export interface CaptionUnit {
  text: string;
  start: number;
  duration: number;
  emphasis: string[];
}

export interface ClipRef {
  video_id: string;
  filename: string;
  start: number;
  end: number;
}

export interface TimelineItem {
  id: string;
  type: string;
  label: string;
  caption: string;
  voiceover: string;
  emphasis_words: string[];
  visual_instruction: string;
  clip: ClipRef | null;
  duration: number;
  captions: CaptionUnit[];
  source_facts_used: string[];
}

export interface MusicSelection {
  category: string;
  track: string;
  reason: string;
}

export interface StepState {
  state: "pending" | "running" | "done" | "skipped" | "error";
  message: string;
}

export interface RenderState {
  status: "idle" | "rendering" | "done" | "error";
  progress: number;
  stage: string;
  output_path: string | null;
  size_bytes: number;
  error: string | null;
}

export interface Project {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  status: "draft" | "processing" | "ready" | "error" | "exported";
  overview: string;
  settings: ProjectSettings;
  videos: VideoMeta[];
  transcript?: Transcript | null;
  story?: Story | null;
  timeline: TimelineItem[];
  music?: MusicSelection | null;
  steps: Record<string, StepState>;
  render: RenderState;
  error: { step?: string; message?: string; hint?: string; code?: string } | null;
}

export interface HealthInfo {
  status: string;
  ffmpeg: { available: boolean; version: string | null };
  providers: {
    llm: ProviderStatus;
    stt: ProviderStatus;
    tts: ProviderStatus;
  };
  music_categories: MusicCategory[];
  caption_styles: CaptionStyleDef[];
  limits: { max_upload_mb: number };
}

export interface ProviderStatus {
  provider: string;
  configured: boolean;
  hint?: string;
  base_url?: string;
  model?: string;
}

export interface MusicCategory {
  id: string;
  label: string;
  tracks: string[];
}

export interface CaptionStyleDef {
  id: string;
  font: string;
  size: number;
  primary: string;
  emphasis_colour?: string;
  uppercase?: boolean;
}

export const STEP_LABELS: Record<string, string> = {
  overview: "Reading your story overview",
  transcription: "Transcribing footage",
  moments: "Finding important moments",
  story: "Writing the reel script",
  clips: "Matching footage",
  captions: "Building captions",
  music: "Scoring background music",
  preview: "Preparing preview",
};
