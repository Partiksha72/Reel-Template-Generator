"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, mediaUrl } from "@/lib/api";
import type { CaptionUnit, MusicSelection, TimelineItem, VideoMeta } from "@/lib/types";
import { fmtDuration } from "@/lib/format";

interface Props {
  projectId: string;
  timeline: TimelineItem[];
  videos: VideoMeta[];
  captionStyle: string;
  watermark: boolean;
  frame?: boolean;
  music?: MusicSelection | null;
  exportedUrl?: string | null;
}

/** Client-side mirror of backend caption styles (preview approximation). */
const STYLE_PRESETS: Record<
  string,
  { family: "display" | "body"; weight: number; shadowColor: string; shadowBlur: number; outline: number }
> = {
  clean: { family: "body", weight: 800, shadowColor: "rgba(0,0,0,0.55)", shadowBlur: 8, outline: 4 },
  bold_editorial: { family: "display", weight: 400, shadowColor: "rgba(0,0,0,0.62)", shadowBlur: 10, outline: 7 },
  highlight: { family: "display", weight: 400, shadowColor: "rgba(0,0,0,0.62)", shadowBlur: 10, outline: 6 },
  nagrik: { family: "display", weight: 400, shadowColor: "#2E0812", shadowBlur: 12, outline: 9 },
};

function outlineShadow(color: string, n: number, blur: number): string {
  const parts: string[] = [];
  for (let dx = -n; dx <= n; dx += Math.max(1, n / 3)) {
    for (let dy = -n; dy <= n; dy += Math.max(1, n / 3)) {
      if (dx === 0 && dy === 0) continue;
      parts.push(`${dx}px ${dy}px 0 ${color}`);
    }
  }
  parts.push(`0 ${Math.round(n / 2)}px ${blur}px rgba(0,0,0,0.45)`);
  return parts.join(",");
}

export default function PreviewPlayer({
  projectId,
  timeline,
  videos,
  captionStyle,
  watermark,
  frame = false,
  music,
  exportedUrl,
}: Props) {
  const [playing, setPlaying] = useState(false);
  const [itemIdx, setItemIdx] = useState(0);
  const [itemTime, setItemTime] = useState(0);
  const [stageW, setStageW] = useState(360);

  const stageRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const items = useMemo(() => timeline.filter((t) => t.clip), [timeline]);
  const totalDur = items.reduce((a, i) => a + i.duration, 0);
  const videosById = useMemo(() => Object.fromEntries(videos.map((v) => [v.id, v])), [videos]);
  const currentItem = items[Math.min(itemIdx, items.length - 1)];

  /* ── responsive stage measurement ─────────────────────── */
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setStageW(el.clientWidth));
    ro.observe(el);
    setStageW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  /* ── load current clip ────────────────────────────────── */
  useEffect(() => {
    const v = videoRef.current;
    const item = items[Math.min(itemIdx, items.length - 1)];
    if (!v || !item?.clip) return;
    const meta = videosById[item.clip.video_id];
    if (!meta) return;
    const url = mediaUrl(projectId, meta.path);
    const needsSrcChange = !v.src.endsWith(meta.path);
    const startAt = () => {
      v.currentTime = item.clip!.start;
      setItemTime(0);
      if (playing) v.play().catch(() => undefined);
    };
    if (needsSrcChange) {
      v.src = url;
      v.load();
      v.onloadedmetadata = () => startAt();
    } else {
      startAt();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemIdx, projectId]);

  /* ── playback clock ───────────────────────────────────── */
  useEffect(() => {
    if (!playing || !currentItem?.clip || exportedUrl) return;
    let raf = 0;
    const tick = () => {
      const v = videoRef.current;
      if (v && currentItem.clip) {
        const local = v.currentTime - currentItem.clip.start;
        setItemTime(Math.max(0, local));
        // duck music while a caption (speech) is visible
        const a = audioRef.current;
        if (a && music) {
          const speaking = currentItem.captions.some(
            (u) => local >= u.start && local <= u.start + u.duration
          );
          const target = speaking ? 0.14 : 0.55;
          a.volume += (target - a.volume) * 0.08;
        }
        if (local >= currentItem.duration - 0.03) {
          if (itemIdx < items.length - 1) {
            setItemIdx(itemIdx + 1);
            raf = requestAnimationFrame(tick);
            return;
          }
          setPlaying(false);
          v.pause();
          return;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, itemIdx, items, currentItem, music, exportedUrl]);

  /* ── transport ────────────────────────────────────────── */
  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    const a = audioRef.current;
    if (!v) return;
    if (playing) {
      v.pause();
      a?.pause();
      setPlaying(false);
    } else {
      if (v.ended || v.currentTime >= (currentItem?.clip?.end ?? 0)) {
        v.currentTime = currentItem?.clip?.start ?? 0;
      }
      v.play().catch(() => undefined);
      if (a && music) a.play().catch(() => undefined);
      setPlaying(true);
    }
  }, [playing, currentItem, music]);

  const restart = useCallback(() => {
    setItemIdx(0);
    const v = videoRef.current;
    if (v) {
      v.src = "";
      setPlaying(false);
      setTimeout(() => {
        setItemIdx(0);
        togglePlayRef.current?.();
      }, 60);
    }
  }, []);
  const togglePlayRef = useRef<() => void>(null!);
  togglePlayRef.current = togglePlay;

  const jumpTo = useCallback((idx: number) => {
    setItemTime(0);
    setItemIdx(idx);
    setPlaying(true);
  }, []);

  /* ── derived render data ──────────────────────────────── */
  const preset = STYLE_PRESETS[captionStyle] ?? STYLE_PRESETS.nagrik;
  const capFontPx = stageW * (preset.family === "display" ? 0.093 : 0.066);
  const activeCaption: CaptionUnit | null =
    currentItem?.captions.find(
      (u) => itemTime >= u.start && itemTime < u.start + u.duration
    ) ?? null;

  const before = items.slice(0, itemIdx).reduce((a, i) => a + i.duration, 0);
  const globalTime = before + itemTime;

  function renderCaptionText(text: string, emphasis: string[]) {
    if (!emphasis.length) return <>{text}</>;
    const re = new RegExp(`(${emphasis.map((e) => e.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
    return text.split(re).map((part, i) =>
      emphasis.some((e) => e.toLowerCase() === part.toLowerCase()) ? (
        <span key={i} className="text-gold">{part}</span>
      ) : (
        <span key={i}>{part}</span>
      )
    );
  }

  /* ══ exported mode: plain native player ═══════════════ */
  if (exportedUrl) {
    return (
      <div className="flex flex-col items-center gap-4">
        <div
          ref={stageRef}
          className="relative aspect-[9/16] max-h-[78vh] overflow-hidden bg-black"
          style={{ borderRadius: 6 }}
        >
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video src={exportedUrl} controls autoPlay className="h-full w-full object-contain" />
        </div>
        <p className="text-xs uppercase tracking-[0.22em] text-muted">Exported reel · H.264 MP4</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex aspect-[9/16] max-h-[70vh] items-center justify-center border border-line bg-coal text-sm text-muted">
        Nothing to preview yet
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      {/* ── 9:16 stage ─────────────────────────────────── */}
      <div
        ref={stageRef}
        onClick={togglePlay}
        className="relative aspect-[9/16] w-full max-w-[340px] cursor-pointer select-none overflow-hidden bg-black shadow-2xl shadow-black/60 md:max-h-[74vh]"
        style={{ borderRadius: 6 }}
      >
        <video
          ref={videoRef}
          playsInline
          muted={false}
          preload="auto"
          className="absolute inset-0 h-full w-full object-cover"
          onPause={() => playing && setPlaying(false)}
        />

        {/* subtle vignette for caption legibility */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/45 to-transparent" />

        {/* frame (branded header + border) — hides floating watermark to avoid double branding */}
        {frame && (
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute inset-x-0 top-0 flex h-[38px] items-center gap-2 bg-[#3A0A16] px-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[#D4A537] text-[9px] font-bold text-[#E9C878]">ना</span>
              <span className="font-devanagari text-xs font-bold leading-none text-[#E9C878]">नागरिक</span>
              <span className="ml-auto text-[6px] uppercase tracking-[0.28em] text-cream/70">Civic Sense India</span>
            </div>
            <div className="absolute inset-0 top-[38px] border-x-[6px] border-b-[6px] border-[#3A0A16]" />
            <div className="absolute inset-0 top-[40px] border-x border-b border-[#D4A537]/50 mx-[6px] mb-[6px]" />
            <div className="absolute left-0 right-0 top-[38px] h-[2px] bg-[#D4A537]" />
          </div>
        )}

        {/* watermark — hidden when frame is on (frame already contains branding) */}
        {watermark && !frame && (
          <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-1.5 rounded-sm bg-black/25 px-2 py-1 backdrop-blur-[2px]" style={{ opacity: 0.88 }}>
            <svg viewBox="0 0 64 64" className="h-5 w-5" aria-hidden>
              <circle cx="32" cy="32" r="26" fill="none" stroke="#D4A537" strokeWidth="5" />
              <text
                x="32"
                y="35"
                textAnchor="middle"
                fill="#E9C878"
                style={{ fontFamily: "'Noto Sans Devanagari','Devanagari Sangam MN',sans-serif", fontWeight: 700, fontSize: 26 }}
              >
                ना
              </text>
            </svg>
            <span className="leading-none">
              <span className="block font-devanagari text-[11px] font-bold text-goldsoft">नागरिक</span>
              <span className="block text-[5px] uppercase tracking-[0.28em] text-cream/80">Civic Sense India</span>
            </span>
          </div>
        )}

        {/* caption */}
        {activeCaption && (
          <div className="caption-pop pointer-events-none absolute inset-x-4 bottom-[13%] flex justify-center" key={`${itemIdx}-${activeCaption.start}`}>
            <p
              className={`text-center leading-[1.08] ${preset.family === "display" ? "font-display" : "font-body"}`}
              style={{
                fontSize: capFontPx,
                fontWeight: preset.weight,
                color: captionStyle === "nagrik" ? "#F5EBD8" : "#FFFFFF",
                textShadow: outlineShadow(preset.shadowColor, preset.outline, preset.shadowBlur),
                letterSpacing: preset.family === "display" ? "0.02em" : "0",
                textTransform: captionStyle === "clean" ? "none" : "uppercase",
              }}
            >
              {renderCaptionText(activeCaption.text, activeCaption.emphasis)}
            </p>
          </div>
        )}

        {/* paused state */}
        {!playing && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/25 transition">
            <span className="flex h-14 w-14 items-center justify-center rounded-full border border-gold/70 bg-black/40 backdrop-blur-sm">
              <svg viewBox="0 0 24 24" className="ml-1 h-6 w-6 fill-gold"><path d="M8 5v14l11-7z" /></svg>
            </span>
          </div>
        )}

        {/* progress */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-white/10">
          <div className="h-full bg-gold" style={{ width: `${totalDur ? (globalTime / totalDur) * 100 : 0}%` }} />
        </div>
      </div>

      {/* music element — key forces reload when track changes */}
      {music?.track ? (
        <audio
          key={music.track}
          ref={audioRef}
          src={`${API_URL}/api/assets/music/${encodeURIComponent(music.track)}`}
          loop
          preload="auto"
        />
      ) : null}

      {/* ── transport controls ─────────────────────────── */}
      <div className="flex w-full max-w-[340px] flex-wrap items-center gap-3">
        <button
          onClick={togglePlay}
          className="btn-gold !min-w-[104px] !px-4 !py-2 text-xs"
        >
          {playing ? "❚❚ Pause" : "▶ Play"}
        </button>
        <button onClick={restart} className="btn-ghost !px-3 !py-2 text-xs">
          ↻ Restart
        </button>
        <span className="ml-auto font-mono text-xs text-muted">
          {fmtDuration(globalTime)} / {fmtDuration(totalDur)}
        </span>
      </div>

      {/* segment scrubber */}
      <div className="flex h-9 w-full max-w-[340px] gap-px overflow-hidden rounded-sm border border-line">
        {items.map((it, idx) => (
          <button
            key={it.id}
            onClick={(e) => {
              e.stopPropagation();
              jumpTo(idx);
            }}
            title={`${it.label} · ${fmtDuration(it.duration)}`}
            style={{ flexGrow: it.duration }}
            className={`group relative text-[8px] font-bold uppercase tracking-[0.14em] transition ${
              idx === itemIdx
                ? "bg-gold text-ink"
                : "bg-coal2 text-muted hover:bg-coal3 hover:text-sand"
            }`}
          >
            <span className="absolute inset-0 flex items-center justify-center truncate px-1">
              {idx === itemIdx ? it.label : ""}
            </span>
          </button>
        ))}
      </div>

      <p className="text-[10px] leading-relaxed tracking-wide text-muted">
        Preview streams your original footage in sequence · Export burns captions, branding &amp; music into a real MP4
      </p>
    </div>
  );
}
