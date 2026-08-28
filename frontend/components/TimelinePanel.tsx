"use client";

import { useState } from "react";
import { mediaUrl } from "@/lib/api";
import type { Project, TimelineItem } from "@/lib/types";
import { fmtDuration, fmtTime } from "@/lib/format";

interface Props {
  project: Project;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onChange: (items: TimelineItem[], save?: boolean) => void;
  onRegenerateSection: (index: number, instruction: string) => Promise<void>;
}

const SECTION_COLORS: Record<string, string> = {
  HOOK: "border-l-gold",
  CONTEXT: "border-l-sky-500/70",
  DEVELOPMENT: "border-l-violet-400/70",
  KEY_FACT: "border-l-emerald-400/70",
  IMPACT: "border-l-orange-400/70",
  ENDING: "border-l-rose-400/70",
};

export default function TimelinePanel({ project, selectedId, onSelect, onChange, onRegenerateSection }: Props) {
  const [editingCaption, setEditingCaption] = useState<string | null>(null);
  const [regenFor, setRegenFor] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");

  function updateItem(id: string, patch: Partial<TimelineItem>, save = true) {
    onChange(
      project.timeline.map((it) => (it.id === id ? { ...it, ...patch } : it)),
      save
    );
  }

  function move(id: string, dir: "up" | "down") {
    const items = [...project.timeline];
    const i = items.findIndex((x) => x.id === id);
    const j = dir === "up" ? i - 1 : i + 1;
    if (i < 0 || j < 0 || j >= items.length) return;
    [items[i], items[j]] = [items[j], items[i]];
    onChange(items);
  }

  function remove(id: string) {
    onChange(project.timeline.filter((it) => it.id !== id));
  }

  let tCursor = 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <h2 className="font-display text-lg uppercase tracking-wide text-cream">Story timeline</h2>
        <span className="text-[11px] uppercase tracking-[0.18em] text-muted">
          {project.timeline.length} sections · {fmtDuration(project.timeline.reduce((a, i) => a + i.duration, 0))}
        </span>
      </div>

      {project.timeline.map((item, index) => {
        const start = tCursor;
        tCursor += item.duration;
        const selected = item.id === selectedId;
        const video = project.videos.find((v) => v.id === item.clip?.video_id);

        return (
          <div
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={`cursor-pointer border border-line border-l-[3px] bg-coal p-4 transition hover:bg-coal2 ${
              SECTION_COLORS[item.label] ?? "border-l-gold/50"
            } ${selected ? "!border-gold/60 ring-1 ring-gold/30" : ""}`}
          >
            {/* header row */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-display text-xs tracking-[0.18em] text-gold">{item.label || item.type.toUpperCase()}</span>
              <span className="font-mono text-[11px] text-muted">
                {fmtTime(start)} → {fmtTime(start + item.duration)}
              </span>
              <span className="ml-auto flex items-center gap-1">
                <button onClick={(e) => { e.stopPropagation(); move(item.id, "up"); }} disabled={index === 0}
                  className="px-1.5 text-muted transition hover:text-gold disabled:opacity-25">▲</button>
                <button onClick={(e) => { e.stopPropagation(); move(item.id, "down"); }} disabled={index === project.timeline.length - 1}
                  className="px-1.5 text-muted transition hover:text-gold disabled:opacity-25">▼</button>
                <button onClick={(e) => { e.stopPropagation(); remove(item.id); }}
                  className="px-1.5 text-muted transition hover:text-red-300" title="Delete section">✕</button>
              </span>
            </div>

            {/* caption */}
            {editingCaption === item.id ? (
              <textarea
                autoFocus
                defaultValue={item.caption}
                onBlur={(e) => {
                  updateItem(item.id, { caption: e.target.value });
                  setEditingCaption(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) (e.target as HTMLTextAreaElement).blur();
                }}
                onClick={(e) => e.stopPropagation()}
                className="input-dark mt-2 min-h-[52px] py-2 text-sm"
              />
            ) : (
              <p
                onClick={(e) => { e.stopPropagation(); setEditingCaption(item.id); }}
                className="mt-2 font-display text-lg uppercase leading-snug tracking-wide text-cream"
                title="Click to edit caption"
              >
                {item.caption || <span className="text-muted">(no caption)</span>}
                <span className="ml-2 align-middle text-[10px] uppercase tracking-widest text-muted opacity-0 transition group-hover:opacity-100">
                  edit
                </span>
              </p>
            )}

            {/* voiceover line */}
            {item.voiceover && (
              <p className="mt-1 line-clamp-2 text-xs italic leading-relaxed text-muted">“{item.voiceover}”</p>
            )}

            {/* clip row */}
            {item.clip && video && (
              <div className="mt-3 flex items-center gap-3 border-t border-line pt-3">
                {video.thumbnail && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={mediaUrl(project.id, video.thumbnail)} alt="" className="h-10 w-[72px] shrink-0 rounded-sm object-cover" />
                )}
                <div className="min-w-0 flex-1 text-[11px] leading-tight text-muted">
                  <p className="truncate text-sand">{video.filename}</p>
                  <p className="font-mono">
                    in {fmtTime(item.clip.start)}–{fmtTime(item.clip.end)} · {fmtDuration(item.duration)}
                    {video.width ? <> · {video.width}×{video.height}</> : null}
                  </p>
                </div>
                {item.visual_instruction && (
                  <p className="hidden max-w-[180px] truncate text-right text-[10px] italic text-muted xl:block" title={item.visual_instruction}>
                    🎬 {item.visual_instruction}
                  </p>
                )}
              </div>
            )}

            {/* actions row */}
            <div
              onClick={(e) => e.stopPropagation()}
              className={`flex flex-wrap items-center gap-2 pt-3 ${selected ? "" : "hidden"}`}
            >
              <label className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted">
                Dur
                <input
                  type="number"
                  min={1.5}
                  max={20}
                  step={0.5}
                  value={item.duration}
                  onChange={(e) =>
                    updateItem(item.id, { duration: Math.max(1.5, Math.min(20, Number(e.target.value) || item.duration)) }, false)
                  }
                  onBlur={() => onChange(project.timeline, true)}
                  className="w-16 border border-line bg-ink px-2 py-1 font-mono text-xs text-cream focus:border-gold/60 focus:outline-none"
                />
                s
              </label>

              {project.videos.length > 1 && item.clip && (
                <select
                  value={item.clip.video_id}
                  onChange={(e) => {
                    const v = project.videos.find((x) => x.id === e.target.value);
                    if (v && item.clip)
                      updateItem(item.id, {
                        clip: { ...item.clip, video_id: v.id, filename: v.filename, start: 0, end: Math.min(v.duration, item.duration) },
                      });
                  }}
                  className="border border-line bg-ink px-2 py-1 text-xs text-sand focus:border-gold/60 focus:outline-none"
                >
                  {project.videos.map((v) => (
                    <option key={v.id} value={v.id}>{v.filename}</option>
                  ))}
                </select>
              )}

              {item.clip && (
                <>
                  <label className="text-[10px] uppercase tracking-wider text-muted">
                    In
                    <input
                      type="number"
                      step={0.5}
                      min={0}
                      max={Math.max(0, (video?.duration ?? 1) - 1)}
                      value={item.clip.start}
                      onChange={(e) => {
                        const s = Math.max(0, Number(e.target.value) || 0);
                        updateItem(item.id, {
                          clip: { ...item.clip!, start: s, end: Math.min(s + item.duration, video?.duration ?? s + item.duration) },
                        }, false);
                      }}
                      className="ml-1 w-[72px] border border-line bg-ink px-2 py-1 font-mono text-xs text-cream focus:border-gold/60 focus:outline-none"
                    />
                  </label>
                  <button
                    onClick={() => {
                      const shift = Math.max(0, item.clip!.start - 2);
                      updateItem(item.id, { clip: { ...item.clip!, start: shift, end: shift + item.duration } });
                    }}
                    className="btn-ghost !px-2 !py-1 !text-[10px]"
                    title="Shift clip earlier by 2s"
                  >« −2s</button>
                  <button
                    onClick={() => {
                      const maxStart = Math.max(0, (video?.duration ?? item.duration) - item.duration);
                      const shift = Math.min(maxStart, item.clip!.start + 2);
                      updateItem(item.id, { clip: { ...item.clip!, start: shift, end: shift + item.duration } });
                    }}
                    className="btn-ghost !px-2 !py-1 !text-[10px]"
                    title="Shift clip later by 2s"
                  >+2s »</button>
                </>
              )}

              <button
                onClick={() => { setRegenFor(regenFor === item.id ? null : item.id); setInstruction(""); }}
                className="btn-ghost !px-3 !py-1 !text-[10px]"
              >
                ✦ Regenerate section
              </button>

              {regenFor === item.id && (
                <div className="flex w-full items-center gap-2 pt-1">
                  <input
                    autoFocus
                    placeholder="e.g. 'Make it punchier' or 'Focus on commuters'"
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    onKeyDown={async (e) => {
                      if (e.key === "Enter") {
                        await onRegenerateSection(index, instruction);
                        setRegenFor(null);
                      }
                    }}
                    className="input-dark !py-1.5 flex-1 text-xs"
                  />
                  <button
                    onClick={async () => { await onRegenerateSection(index, instruction); setRegenFor(null); }}
                    className="btn-gold !px-3 !py-1.5 !text-[10px]"
                  >Rewrite</button>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
