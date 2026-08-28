"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import PreviewPlayer from "@/components/PreviewPlayer";
import ProcessingScreen from "@/components/ProcessingScreen";
import TimelinePanel from "@/components/TimelinePanel";
import {
  API_URL,
  exportReel,
  getProject,
  regenerate,
  saveTimeline,
  setCaptionStyle,
  setMusic,
} from "@/lib/api";
import type { Project, TimelineItem } from "@/lib/types";
import { fmtBytes } from "@/lib/format";

const CAPTION_STYLE_OPTIONS = [
  { id: "nagrik", label: "Nagrik Default", desc: "Cream & gold · brand style" },
  { id: "bold_editorial", label: "Bold Editorial", desc: "Big white impact type" },
  { id: "highlight", label: "Highlight", desc: "White with gold key words" },
  { id: "clean", label: "Clean", desc: "Understated sans" },
];

const MUSIC_OPTIONS = [
  ["auto", "Auto (match tone)"],
  ["serious_news", "Serious News"],
  ["investigative", "Investigative"],
  ["energetic", "Energetic"],
  ["emotional", "Emotional"],
  ["civic", "Civic"],
  ["modern", "Modern"],
  ["minimal", "Minimal"],
];

function MusicPreviewRow({
  label,
  file,
  category,
  active,
  onSelect,
}: {
  label: string;
  file: string | null;
  category: string;
  active: boolean;
  onSelect: () => void;
}) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const togglePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!file) return;
    if (!audioRef.current) {
      audioRef.current = new Audio(`${API_URL}/api/assets/music/${file}`);
      audioRef.current.loop = false;
      audioRef.current.volume = 0.6;
      audioRef.current.onended = () => setPlaying(false);
    }
    if (playing) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
    } else {
      audioRef.current.play().catch(() => {});
      setPlaying(true);
    }
  };
  return (
    <div
      onClick={onSelect}
      className={`flex cursor-pointer items-center gap-2 border px-2 py-1.5 transition ${
        active ? "border-gold bg-gold/10" : "border-line hover:border-gold/30 hover:bg-coal2"
      }`}
    >
      <button
        onClick={togglePreview}
        disabled={!file}
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-sm text-[10px] ${
          !file ? "bg-coal2 text-muted/40" : playing ? "bg-gold text-ink" : "bg-coal2 text-gold hover:bg-gold hover:text-ink"
        }`}
        title={file ? (playing ? "Stop preview" : "Preview") : "No audio"}
      >
        {playing ? "■" : "▶"}
      </button>
      <span className={`flex-1 text-xs ${active ? "font-bold text-cream" : "text-sand"}`}>{label}</span>
      {active && <span className="text-xs text-gold">✓</span>}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-line bg-coal/60 p-5">
      <h3 className="label-caps mb-3 !text-gold/80">{title}</h3>
      {children}
    </section>
  );
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* ── polling loop ──────────────────────────────────────── */
  const refresh = useCallback(async () => {
    try {
      setProject(await getProject(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    refresh();
    pollRef.current = setInterval(async () => {
      try {
        const p = await getProject(id);
        setProject((prev) => (prev ? p : p));
        if (!["processing"].includes(p.status) && p.render.status !== "rendering") {
          // keep polling lightly anyway for multi-tab freshness
        }
      } catch {
        /* transient */
      }
    }, 1600);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id, refresh]);

  async function doExport() {
    setActionError(null);
    try {
      await exportReel(id);
      refresh();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  async function withBusy(label: string, fn: () => Promise<void>) {
    setBusyAction(label);
    setActionError(null);
    try {
      await fn();
    } catch (e) {
      const err = e as Error & { hint?: string };
      setActionError(err.message + (err.hint ? ` — ${err.hint}` : ""));
    } finally {
      setBusyAction("");
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-red-300">{error}</p>
        <Link href="/projects" className="btn-ghost mt-6">← All projects</Link>
      </div>
    );
  }
  if (!project) {
    return <div className="px-6 py-24 text-center text-sm text-muted">Loading reel…</div>;
  }

  /* ── processing state ──────────────────────────────────── */
  if (project.status === "processing") {
    return <ProcessingScreen project={project} />;
  }

  /* ── error state ───────────────────────────────────────── */
  const configProblem =
    project.error?.code === "configuration" || /not configured/i.test(project.error?.message ?? "");
  if (project.status === "error" && project.timeline.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-20">
        <p className="label-caps !text-red-400">Generation failed</p>
        <h1 className="mt-4 font-display text-4xl uppercase tracking-wide text-cream">{project.title}</h1>
        <div className="panel mt-8 space-y-3 border-red-900/40 p-6">
          <p className="text-sm leading-relaxed text-red-200">{project.error?.message}</p>
          {project.error?.hint && (
            <p className="border-t border-line pt-3 text-xs leading-relaxed text-sand">
              💡 {project.error.hint}
            </p>
          )}
          {configProblem && (
            <p className="border-t border-line pt-3 text-xs leading-relaxed text-muted">
              Configure providers in your <code>.env</code> file at the repo root
              (LLM_API_KEY etc.), restart the backend, then retry.
            </p>
          )}
        </div>
        <div className="mt-6 flex gap-3">
          <button
            onClick={() => withBusy("regen-story", async () => setProject(await regenerate(id, "story")))}
            disabled={!!busyAction}
            className="btn-gold"
          >
            ↻ Try again
          </button>
          <Link href="/settings" className="btn-ghost">Open settings</Link>
          <Link href="/create" className="btn-ghost">New reel</Link>
        </div>
      </div>
    );
  }

  /* ── ready / exported state: the editor ────────────────── */
  const exportedUrl =
    project.render.output_path
      ? `${API_URL}/api/media/${id}/${project.render.output_path}`
      : null;

  async function handleTimelineChange(items: TimelineItem[], save = true) {
    setProject({ ...project!, timeline: items });
    if (save) {
      try {
        await saveTimeline(id, items);
      } catch (e) {
        setActionError((e as Error).message);
      }
    }
  }

  return (
    <div className="mx-auto max-w-[1500px] px-6 pb-24">
      {/* header row */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line py-6">
        <Link href="/projects" className="text-xs font-semibold uppercase tracking-[0.18em] text-muted hover:text-gold">
          ← Projects
        </Link>
        <div className="min-w-0">
          <h1 className="truncate font-display text-2xl uppercase tracking-wide text-cream md:text-3xl">
            {project.title}
          </h1>
          <p className="mt-0.5 text-xs text-muted">
            {project.settings.duration_target}s target · {project.settings.language} ·{" "}
            {project.settings.tone} · {project.settings.platform}
            {project.music && <> · 🎵 {project.music.category.replace("_", " ")}</>}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {busyAction && (
            <span className="flex items-center gap-2 text-xs text-goldsoft">
              <span className="inline-block h-2 w-2 animate-pulse-dot rounded-full bg-gold" /> {busyAction}…
            </span>
          )}
          <button
            onClick={() => withBusy("regenerating story", async () => setProject(await regenerate(id, "story")))}
            disabled={!!busyAction}
            className="btn-ghost"
            title="Rewrite the whole script from the same overview"
          >
            ↻ Regenerate Story
          </button>
          <button
            onClick={() => withBusy("regenerating captions", async () => setProject(await regenerate(id, "captions")))}
            disabled={!!busyAction}
            className="btn-ghost"
          >
            ↻ Captions
          </button>
          <button onClick={doExport} disabled={project.render.status === "rendering"} className="btn-gold">
            Export Reel ↓
          </button>
        </div>
      </div>

      {actionError && (
        <div className="mt-4 border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">{actionError}</div>
      )}

      {/* main grid */}
      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(320px,420px)_1fr_minmax(260px,320px)]">
        {/* LEFT · preview */}
        <div className="justify-self-center">
          {project.render.status === "done" && exportedUrl ? (
            <PreviewPlayer
              projectId={id}
              timeline={[]}
              videos={[]}
              captionStyle=""
              watermark={false}
              frame={false}
              exportedUrl={exportedUrl}
            />
          ) : (
            <PreviewPlayer
              projectId={id}
              timeline={project.timeline}
              videos={project.videos}
              captionStyle={project.settings.caption_style}
              watermark={project.settings.watermark}
              frame={!!project.settings.frame}
              music={project.render.status === "rendering" ? null : project.music}
            />
          )}
        </div>

        {/* CENTER · timeline */}
        <div>
          {project.render.status === "rendering" && (
            <div className="mb-6 border border-gold/30 bg-coal p-5">
              <p className="label-caps !text-gold">Rendering…</p>
              <p className="mt-1 text-sm text-cream">{project.render.stage}</p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-coal2">
                <div
                  className="h-full rounded-full bg-gold transition-all duration-700"
                  style={{ width: `${Math.round((project.render.progress ?? 0) * 100)}%` }}
                />
              </div>
              <p className="mt-2 text-right font-mono text-xs text-muted">
                {Math.round((project.render.progress ?? 0) * 100)}%
              </p>
            </div>
          )}

          {project.render.status === "done" && project.render.output_path && (
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border border-emerald-800/50 bg-emerald-950/25 p-5">
              <div>
                <p className="text-sm font-bold text-emerald-300">✓ Reel rendered</p>
                <p className="mt-0.5 text-xs text-muted">
                  H.264 MP4 · 1080×1920 · {fmtBytes(project.render.size_bytes)}
                </p>
              </div>
              <a href={`${API_URL}/api/projects/${id}/download`} className="btn-gold" download>
                ⬇ Download Reel
              </a>
            </div>
          )}

          {project.render.status === "error" && (
            <div className="mb-6 border border-red-900/50 bg-red-950/30 p-5">
              <p className="text-sm font-bold text-red-300">Render failed</p>
              <p className="mt-1 break-words text-xs leading-relaxed text-red-200/90">{project.render.error}</p>
            </div>
          )}

          <TimelinePanel
            project={project}
            selectedId={selected}
            onSelect={setSelected}
            onChange={handleTimelineChange}
            onRegenerateSection={async (index, instruction) =>
              withBusy("rewriting section", async () => {
                setProject(await regenerate(id, "section", index, instruction));
              })
            }
          />

          {/* transcript + fact audit */}
          {(project.transcript?.segments?.length || project.story?.source_facts?.length) && (
            <details className="mt-6 border border-line bg-coal/60">
              <summary className="cursor-pointer px-5 py-4 text-sm font-semibold uppercase tracking-[0.16em] text-sand hover:text-gold">
                Source facts &amp; transcript audit
              </summary>
              <div className="space-y-5 border-t border-line px-5 py-5">
                {project.story?.source_facts?.length ? (
                  <div>
                    <p className="label-caps mb-2">Source facts (from your overview)</p>
                    <ul className="space-y-1.5">
                      {project.story.source_facts.map((f, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs leading-relaxed">
                          <span
                            className={`mt-0.5 shrink-0 rounded-sm px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                              f.origin === "user_overview"
                                ? "bg-emerald-900/50 text-emerald-300"
                                : "bg-amber-900/50 text-amber-300"
                            }`}
                          >
                            {f.origin === "user_overview" ? "verified" : "review"}
                          </span>
                          <span className="text-sand">{f.fact}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {project.story?.creative_note && (
                  <div>
                    <p className="label-caps mb-2">Creative copy added by AI</p>
                    <p className="text-xs italic leading-relaxed text-muted">{project.story.creative_note}</p>
                  </div>
                )}
                {project.story?.warnings?.length ? (
                  <div>
                    <p className="label-caps mb-2 !text-amber-400">Warnings</p>
                    <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-amber-200/80">
                      {project.story.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                ) : null}
                {project.transcript?.segments?.length ? (
                  <div>
                    <p className="label-caps mb-2">
                      Footage transcript ({project.transcript.provider})
                      {project.transcript.language ? ` · ${project.transcript.language}` : ""}
                    </p>
                    <div className="max-h-56 space-y-1 overflow-y-auto pr-2">
                      {project.transcript.segments.map((s, i) => (
                        <p key={i} className="font-mono text-[11px] leading-relaxed text-muted">
                          [{Math.floor(s.start / 60)}:{String(Math.floor(s.start % 60)).padStart(2, "0")}] {s.text}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </details>
          )}
        </div>

        {/* RIGHT · controls */}
        <div className="space-y-5">
          <Panel title="Caption style">
            <div className="space-y-2">
              {CAPTION_STYLE_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() =>
                    withBusy(`switching captions`, async () => {
                      await setCaptionStyle(id, opt.id);
                      refresh();
                    })
                  }
                  className={`block w-full border px-4 py-3 text-left transition ${
                    project.settings.caption_style === opt.id
                      ? "border-gold/60 bg-gold/10"
                      : "border-line hover:border-gold/30 hover:bg-coal2"
                  }`}
                >
                  <span
                    className={`block text-sm uppercase leading-tight ${
                      opt.id === "nagrik" ? "font-display text-cream" : "font-bold text-cream"
                    }`}
                  >
                    {opt.label}
                    {opt.id === "nagrik" && <span className="ml-2 text-gold">✦</span>}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-muted">{opt.desc}</span>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="Background music">
            {project.music && (
              <p className="mb-3 border-l-2 border-gold/60 pl-3 text-xs italic leading-relaxed text-sand">
                🎵 {project.music.reason}
              </p>
            )}
            {/* track previews */}
            <div className="mb-4 space-y-1.5">
              {[
                ["civic", "Civic", "civic.m4a"],
                ["serious_news", "Serious News", "serious_news.m4a"],
                ["investigative", "Investigative", "investigative.m4a"],
                ["energetic", "Energetic", "energetic.m4a"],
                ["emotional", "Emotional", "emotional.m4a"],
                ["modern", "Modern", "modern.m4a"],
                ["minimal", "Minimal", "minimal.m4a"],
              ].map(([cat, label, file]) => (
                <MusicPreviewRow
                  key={cat}
                  label={label}
                  file={file}
                  category={cat}
                  active={project.music?.category === cat}
                  onSelect={() =>
                    withBusy("changing music", async () => {
                      await setMusic(id, cat);
                      refresh();
                    })
                  }
                />
              ))}
              <MusicPreviewRow
                label="No music"
                file={null}
                category="none"
                active={project.music?.category === "none"}
                onSelect={() =>
                  withBusy("removing music", async () => {
                    await setMusic(id, "none");
                    refresh();
                  })
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted">Or auto-match to tone:</span>
              <button
                onClick={() =>
                  withBusy("auto-selecting music", async () => {
                    await setMusic(id, "auto");
                    refresh();
                  })
                }
                className={`rounded-sm border px-2 py-1 text-xs ${project.music?.category && MUSIC_OPTIONS.some(([v])=>v===project.music?.category) ? "border-line text-sand" : "border-gold bg-gold/10 text-gold"}`}
              >
                Auto
              </button>
            </div>
            {project.render.status === "idle" && project.render.stage.includes("Music changed") && (
              <p className="mt-3 rounded-sm bg-gold/10 px-3 py-2 text-xs font-semibold text-gold">
                ♪ Music changed — hit <span className="underline">Export Reel</span> to re-render with the new track.
              </p>
            )}
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              Tap ▶ to preview each bed. Selected track plays in the preview and is burned into the export. Auto-ducks under speech.
            </p>
          </Panel>

          <Panel title="Branding & audio">
            <label className="flex cursor-pointer items-center justify-between py-1.5">
              <span className="text-sm text-sand">नागरिक watermark</span>
              <input
                type="checkbox"
                checked={project.settings.watermark}
                onChange={async (e) => {
                  const next = { ...project!.settings, watermark: e.target.checked };
                  setProject({ ...project!, settings: next });
                  await fetch(`${API_URL}/api/projects/${id}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ settings: next }),
                  });
                  refresh();
                }}
                className="h-4 w-4 accent-[#D4A537]"
              />
            </label>
            <label className="flex cursor-pointer items-center justify-between py-1.5">
              <span className="text-sm text-sand">Branded frame</span>
              <input
                type="checkbox"
                checked={!!project.settings.frame}
                onChange={async (e) => {
                  const next = { ...project!.settings, frame: e.target.checked };
                  // auto-disable watermark when frame is on to avoid double branding
                  if (e.target.checked) next.watermark = false;
                  setProject({ ...project!, settings: next });
                  await fetch(`${API_URL}/api/projects/${id}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ settings: next }),
                  });
                  refresh();
                }}
                className="h-4 w-4 accent-[#D4A537]"
              />
            </label>
            {project.settings.frame && (
              <p className="mt-1 text-[11px] leading-relaxed text-gold/70">
                Burgundy header with gold “नागरिक • Civic Sense India” + thin gold/burgundy border — visible in preview and export.
              </p>
            )}

            <div className="mt-4 border-t border-line pt-4">
              <p className="label-caps mb-2 !text-cream/80">Original audio</p>
              <div className="space-y-1.5">
                <button
                  onClick={async () => {
                    const next = { ...project!.settings, voiceover: "original" as const };
                    setProject({ ...project!, settings: next });
                    await fetch(`${API_URL}/api/projects/${id}`, {
                      method: "PATCH",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ settings: next }),
                    });
                    refresh();
                  }}
                  className={`flex w-full items-center justify-between border px-3 py-2 text-left text-xs transition ${
                    project.settings.voiceover !== "off" ? "border-gold bg-gold/10 text-cream" : "border-line text-sand hover:border-gold/30"
                  }`}
                >
                  <span>Keep original audio <span className="text-muted">— streets, interviews, ambient sound</span></span>
                  {project.settings.voiceover !== "off" && <span className="text-gold">✓</span>}
                </button>
                <button
                  onClick={async () => {
                    const next = { ...project!.settings, voiceover: "off" as const };
                    setProject({ ...project!, settings: next });
                    await fetch(`${API_URL}/api/projects/${id}`, {
                      method: "PATCH",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ settings: next }),
                    });
                    refresh();
                  }}
                  className={`flex w-full items-center justify-between border px-3 py-2 text-left text-xs transition ${
                    project.settings.voiceover === "off" ? "border-gold bg-gold/10 text-cream" : "border-line text-sand hover:border-gold/30"
                  }`}
                >
                  <span>Remove original audio <span className="text-muted">— music + captions only</span></span>
                  {project.settings.voiceover === "off" && <span className="text-gold">✓</span>}
                </button>
              </div>
              {project.settings.voiceover === "off" && (
                <p className="mt-2 rounded-sm bg-gold/10 px-3 py-2 text-xs font-semibold text-gold">
                  🔇 Original audio will be stripped — re-export to apply.
                </p>
              )}
              {project.settings.voiceover === "ai" && (
                <p className="mt-2 border-l-2 border-gold/50 pl-3 text-[11px] italic text-goldsoft">
                  AI voiceover will be generated on export.
                </p>
              )}
              {project.render.status === "idle" && project.render.stage.includes("Audio") && (
                <p className="mt-2 rounded-sm bg-gold/10 px-3 py-1.5 text-xs text-gold">{project.render.stage}</p>
              )}
            </div>
          </Panel>

          <Panel title="The story so far">
            <p className="text-xs leading-relaxed text-sand">{project.story?.story}</p>
            {project.story?.hook && (
              <p className="mt-3 border-l-2 border-gold/60 pl-3 text-xs leading-relaxed text-goldsoft">
                Hook: “{project.story.hook}”
              </p>
            )}
            {project.story?.cta && (
              <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-muted">CTA · {project.story.cta}</p>
            )}
          </Panel>

          <Panel title="How AI is used here">
            <ul className="space-y-2 text-xs leading-relaxed text-muted">
              <li><span className="font-semibold text-sand">Story → Script:</span> LLM (<code className="text-sand/80">{project.story ? "structured JSON" : "LLM"}</code>) turns your overview into hook → context → key facts → impact → CTA. Never invents stats/quotes — audited in “Source facts” below.</li>
              <li><span className="font-semibold text-sand">Footage → Text:</span> Whisper STT transcribes your raw video into timestamped transcript.</li>
              <li><span className="font-semibold text-sand">Clips:</span> Ranked by transcript-keyword overlap + silence/scene detection (heuristic, not LLM).</li>
              <li><span className="font-semibold text-sand">Captions:</span> LLM provides emphasis words; chunking/style is deterministic.</li>
              <li><span className="font-semibold text-sand">Music:</span> Rule-based tone → category mapping; audio ducking is signal processing.</li>
            </ul>
            <p className="mt-3 text-[11px] text-muted/70">Without a valid <code>LLM_API_KEY</code> the story step uses a deterministic template fallback (see Warnings) so the rest of the pipeline stays demo-able.</p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
