"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  createProject,
  generateReel,
  getHealth,
  uploadVideos,
} from "@/lib/api";
import type { ProjectSettings } from "@/lib/types";
import { fmtBytes, fmtDuration } from "@/lib/format";

const STEPS = ["01 STORY", "02 FOOTAGE", "03 AI EDIT", "04 REVIEW", "05 EXPORT"];

const TONES = [
  "Civic Awareness",
  "Breaking News",
  "Informative",
  "Investigative",
  "Neutral",
  "Youth-focused",
  "Serious",
  "Explainer",
];
const LANGUAGES = ["English", "Hindi", "Hinglish"];
const DURATIONS = [15, 30, 45, 60];

interface LocalFile {
  file: File;
  url: string;
  duration?: number;
  width?: number;
  height?: number;
}

function probeVideo(f: File): Promise<{ url: string; duration?: number; width?: number; height?: number }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(f);
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => {
      resolve({
        url,
        duration: v.duration,
        width: v.videoWidth,
        height: v.videoHeight,
      });
      URL.revokeObjectURL(url);
    };
    v.onerror = () => resolve({ url });
    v.src = url;
  });
}

export default function CreateReelPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  const [overview, setOverview] = useState("");
  const [files, setFiles] = useState<LocalFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [settings, setSettings] = useState<ProjectSettings>({
    duration_target: 45,
    language: "English",
    tone: "Civic Awareness",
    platform: "Instagram Reels",
    caption_style: "nagrik",
    watermark: true,
    voiceover: "original",
    music_category: "auto",
    frame: false,
  });
  const [customDuration, setCustomDuration] = useState("");

  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState("");
  const [pct, setPct] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const [ffmpegOk, setFfmpegOk] = useState(true);
  useEffect(() => {
    getHealth()
      .then((h) => setFfmpegOk(h.ffmpeg.available))
      .catch(() => setError("Nagrik's backend isn't reachable. Start it with `make api` or see README."));
  }, []);

  const addFiles = useCallback(async (list: FileList | File[]) => {
    const incoming = Array.from(list);
    const ok = incoming.filter((f) => /\.(mp4|mov|webm|m4v)$/i.test(f.name));
    if (ok.length !== incoming.length)
      setError("Some files were skipped — only MP4, MOV and WebM are supported.");
    else setError(null);
    const probed = await Promise.all(
      ok.map(async (file) => ({ file, ...(await probeVideo(file)) }))
    );
    setFiles((prev) => [...prev, ...probed]);
  }, []);

  async function handleGenerate() {
    if (busy) return;
    if (!overview.trim() && files.length === 0) {
      setError("Add your story overview or upload footage first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setPhase("Creating project…");
      const project = await createProject({
        title: title.trim() || "Untitled Reel",
        overview: overview.trim(),
        settings: {
          ...settings,
          duration_target: customDuration
            ? Math.max(10, Math.min(180, parseInt(customDuration, 10) || 45))
            : settings.duration_target,
        },
      });

      if (files.length > 0) {
        setPhase(`Uploading ${files.length} video${files.length > 1 ? "s" : ""}…`);
        const res = await uploadVideos(project.id, files.map((f) => f.file), (p) => {
          setPct(p);
        });
        if (res.errors?.length) {
          throw new Error(res.errors[0].message);
        }
      }

      setPhase("Starting AI edit…");
      await generateReel(project.id);
      router.push(`/projects/${project.id}`);
    } catch (e) {
      setError((e as Error & { hint?: string }).message || "Something went wrong.");
      setBusy(false);
      setPhase("");
    }
  }

  const totalFootage = files.reduce((a, f) => a + (f.duration ?? 0), 0);

  return (
    <div className="mx-auto max-w-5xl px-6 pb-24">
      {/* step strip */}
      <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line pb-5">
        {STEPS.map((s, i) => (
          <span
            key={s}
            className={`font-display text-xs tracking-[0.2em] ${
              i === 0 ? "text-gold" : "text-muted/70"
            }`}
          >
            {s}
          </span>
        ))}
      </div>

      <h1 className="mt-8 font-display text-4xl uppercase tracking-wide text-cream">
        New Reel
      </h1>
      <p className="mt-2 text-sm text-muted">
        Two inputs are all Nagrik needs — what happened, and what you filmed.
      </p>

      {/* ── story ─────────────────────────────────────── */}
      <section className="mt-8 space-y-5">
        <div>
          <label className="label-caps">Reel title</label>
          <input
            className="input-dark mt-2 !py-3 text-base"
            placeholder="e.g. Delhi's New Parking Rules"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={120}
          />
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label className="label-caps">What&apos;s the story?</label>
            <span className="text-[11px] text-muted">{overview.trim().split(/\s+/).filter(Boolean).length} words</span>
          </div>
          <textarea
            className="input-dark mt-2 min-h-[170px] resize-y leading-relaxed"
            placeholder={"Paste the news summary, context, facts, or your rough video overview here...\n\nExample: A new civic policy has been announced in Delhi. The policy will affect how parking is managed in major residential and commercial areas. Residents have raised concerns about implementation and enforcement."}
            value={overview}
            onChange={(e) => setOverview(e.target.value)}
          />
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Rough notes, bullet points or article summaries all work. Nagrik uses{" "}
            <span className="text-sand">only these facts</span> — it never invents statistics,
            quotes or names.
          </p>
        </div>
      </section>

      {/* ── footage ───────────────────────────────────── */}
      <section className="mt-10">
        <label className="label-caps">Raw footage</label>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
          className={`mt-3 cursor-pointer border border-dashed px-8 py-12 text-center transition ${
            dragging ? "border-gold bg-gold/5" : "border-line hover:border-gold/40 hover:bg-coal"
          }`}
        >
          <svg viewBox="0 0 24 24" className="mx-auto h-9 w-9 text-gold" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 17v2a1 1 0 001 1h14a1 1 0 001-1v-2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="mt-4 text-sm font-semibold text-cream">
            Drag &amp; drop videos here, or click to browse
          </p>
          <p className="mt-1 text-xs text-muted">MP4 · MOV · WebM — multiple files supported</p>
          <input
            ref={inputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.m4v"
            multiple
            hidden
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
        </div>

        {!ffmpegOk && (
          <p className="mt-3 border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-300">
            FFmpeg was not found on this machine — uploads work but processing/export won&apos;t.
            Install it with <code className="text-red-200">brew install ffmpeg</code>.
          </p>
        )}

        {files.length > 0 && (
          <ul className="mt-4 space-y-2">
            {files.map((f, i) => (
              <li key={`${f.file.name}-${i}`} className="flex items-center gap-4 border border-line bg-coal p-3">
                <div className="h-14 w-24 shrink-0 overflow-hidden bg-ink">
                  {f.url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <video src={f.url} className="h-full w-full object-cover" muted preload="metadata" />
                  ) : null}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-cream">{f.file.name}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {fmtBytes(f.file.size)}
                    {f.duration ? <> · {fmtDuration(f.duration)}</> : null}
                    {f.width ? <> · {f.width}×{f.height}</> : null}
                  </p>
                </div>
                <button
                  onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  className="shrink-0 rounded-sm px-2 py-1 text-xs uppercase tracking-wider text-muted transition hover:bg-coal2 hover:text-red-300"
                >
                  Remove
                </button>
              </li>
            ))}
            <li className="pt-1 text-right text-xs text-muted">
              {files.length} clip{files.length > 1 ? "s" : ""} · {fmtDuration(totalFootage)} of footage
            </li>
          </ul>
        )}
      </section>

      {/* ── options ───────────────────────────────────── */}
      <section className="mt-10">
        <button
          onClick={() => setAdvanced(!advanced)}
          className="flex items-center gap-3 text-sm font-bold uppercase tracking-[0.18em] text-sand transition hover:text-gold"
        >
          <span className={`transition ${advanced ? "rotate-90" : ""}`}>▸</span>
          Advanced options
        </button>

        {advanced && (
          <div className="animate-rise mt-5 grid gap-6 border border-line bg-coal p-6 md:grid-cols-2">
            <div>
              <label className="label-caps">Reel duration</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {DURATIONS.map((d) => (
                  <button
                    key={d}
                    onClick={() => { setSettings({ ...settings, duration_target: d }); setCustomDuration(""); }}
                    className={`border px-4 py-2 text-xs font-bold uppercase tracking-wider transition ${
                      settings.duration_target === d && !customDuration
                        ? "border-gold bg-gold text-ink"
                        : "border-line text-sand hover:border-gold/40"
                    }`}
                  >
                    {d}s
                  </button>
                ))}
                <input
                  className="w-20 border border-line bg-ink px-3 py-2 text-xs text-cream placeholder:text-muted focus:border-gold/60 focus:outline-none"
                  placeholder="Custom"
                  value={customDuration}
                  onChange={(e) => setCustomDuration(e.target.value.replace(/[^0-9]/g, ""))}
                />
              </div>
            </div>

            <div>
              <label className="label-caps">Language</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {LANGUAGES.map((l) => (
                  <button
                    key={l}
                    onClick={() => setSettings({ ...settings, language: l })}
                    className={`border px-4 py-2 text-xs font-bold uppercase tracking-wider transition ${
                      settings.language === l
                        ? "border-gold bg-gold text-ink"
                        : "border-line text-sand hover:border-gold/40"
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="label-caps">Tone</label>
              <select
                className="input-dark mt-2"
                value={settings.tone}
                onChange={(e) => setSettings({ ...settings, tone: e.target.value })}
              >
                {TONES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>

            <div>
              <label className="label-caps">Platform</label>
              <select
                className="input-dark mt-2"
                value={settings.platform}
                onChange={(e) => setSettings({ ...settings, platform: e.target.value })}
              >
                <option>Instagram Reels</option>
                <option>YouTube Shorts</option>
                <option>Generic 9:16</option>
              </select>
              <p className="mt-1 text-[11px] text-muted">All outputs render vertical 9:16.</p>
            </div>

            <div>
              <label className="label-caps">Voiceover</label>
              <select
                className="input-dark mt-2"
                value={settings.voiceover}
                onChange={(e) => setSettings({ ...settings, voiceover: e.target.value })}
              >
                <option value="original">Use original audio</option>
                <option value="off">No audio (captions + music)</option>
                <option value="ai">AI voiceover (needs TTS provider)</option>
              </select>
            </div>

            <div>
              <label className="label-caps">Music mood</label>
              <select
                className="input-dark mt-2"
                value={settings.music_category}
                onChange={(e) => setSettings({ ...settings, music_category: e.target.value })}
              >
                <option value="auto">Auto — match to tone</option>
                <option value="serious_news">Serious News</option>
                <option value="investigative">Investigative</option>
                <option value="energetic">Energetic</option>
                <option value="emotional">Emotional</option>
                <option value="civic">Civic</option>
                <option value="modern">Modern</option>
                <option value="minimal">Minimal</option>
                <option value="none">No music — clean audio</option>
              </select>
              <p className="mt-1 text-[11px] text-muted">Choose “No music” to export voice/captions only.</p>
            </div>

            <div className="space-y-4 md:col-span-2 border-t border-line pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="label-caps">नागरिक watermark</label>
                  <p className="mt-1 text-[11px] text-muted">Small corner mark on the exported reel.</p>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, watermark: !settings.watermark })}
                  role="switch"
                  aria-checked={settings.watermark}
                  className={`relative h-6 w-11 shrink-0 rounded-full border transition ${
                    settings.watermark ? "border-gold bg-gold/80" : "border-line bg-coal2"
                  }`}
                >
                  <span
                    className={`absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-ink transition ${
                      settings.watermark ? "left-6" : "left-1"
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <label className="label-caps">Branded frame</label>
                  <p className="mt-1 text-[11px] text-muted">Full 9:16 border + header in Nagrik burgundy & gold.</p>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, frame: !settings.frame })}
                  role="switch"
                  aria-checked={settings.frame}
                  className={`relative h-6 w-11 shrink-0 rounded-full border transition ${
                    settings.frame ? "border-gold bg-gold/80" : "border-line bg-coal2"
                  }`}
                >
                  <span
                    className={`absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-ink transition ${
                      settings.frame ? "left-6" : "left-1"
                    }`}
                  />
                </button>
              </div>
              {settings.frame && (
                <div className="rounded-sm border border-gold/20 bg-gold/5 px-3 py-2">
                  <p className="text-[11px] leading-relaxed text-sand">
                    Framed reel will have a <span className="font-semibold text-gold">burgundy header</span> with
                    {" “नागरिक • CIVIC SENSE INDIA”"} and a thin gold border — visible in preview and export.
                    Disable watermark when frame is on to avoid double branding.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {/* ── error / actions ──────────────────────────── */}
      {error && (
        <div className="mt-8 border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="sticky bottom-0 mt-10 border-t border-line bg-ink/90 py-5 backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <div className="min-h-5 text-xs text-muted">
            {busy && phase && (
              <span className="flex items-center gap-2">
                <span className="inline-block h-2 w-2 animate-pulse-dot rounded-full bg-gold" />
                {phase} {pct > 0 && pct < 100 ? `${pct}%` : ""}
              </span>
            )}
          </div>
          <button
            disabled={busy}
            onClick={handleGenerate}
            className="btn-gold !px-8 !py-3.5 text-base"
          >
            {busy ? "Working…" : "Generate Reel ✦"}
          </button>
        </div>
      </div>
    </div>
  );
}
