"""Automatic clip selection.

Heuristic, deterministic matcher between story segments and raw footage:

1. Every transcript segment gets a relevance score against the story segment's
   keywords (token overlap, weighted by speech density).
2. Relevance is spread across the timeline as overlapping windows.
3. Windows inside detected silence are penalised; windows starting shortly
   after a hard scene change get a small bonus (clean visual cut points).
4. Best non-overlapping window per story segment wins; boundaries snap to the
   nearest silence edge when one is close.

Without any transcript it falls back to visually-driven selection: evenly
spaced, silence-free windows that start on scene changes where possible.
"""
from typing import Dict, List, Optional, Tuple

from ..schemas.models import Analysis, Moment, Story, Transcript, VideoMeta

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "have", "has", "are", "was", "were", "will",
    "your", "you", "from", "into", "about", "just", "what", "when", "here", "they", "their",
    "them", "there", "than", "then", "over", "under", "been", "being", "does", "did", "not",
}


def _tokens(text: str) -> List[str]:
    import re
    return [w for w in re.findall(r"[a-zA-Z\u0900-\u097F]{3,}", text.lower()) if w not in STOPWORDS]


def _overlap_score(story_keywords: List[str], text: str) -> float:
    if not story_keywords or not text:
        return 0.0
    kw = [k.lower() for k in story_keywords]
    words = _tokens(text)
    if not words:
        return 0.0
    hits = 0
    for k in kw:
        if k in words or any(k in w for w in words):
            hits += 1
    return hits / len(kw)


class ClipSelector:
    def __init__(
        self,
        videos: List[VideoMeta],
        transcript: Optional[Transcript],
        analysis: Optional[Analysis],
        video_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> None:
        """video_ranges maps each video id to its [start, end) span on the
        global timeline (used when several files were uploaded)."""
        self.videos = [v for v in videos if v.duration >= 1.2]
        self.transcript = transcript
        self.analysis = analysis or Analysis()
        cursor = 0.0
        self.ranges: Dict[str, Tuple[float, float]] = {}
        for v in self.videos:
            self.ranges[v.id] = video_ranges.get(v.id, (cursor, cursor + v.duration))
            cursor += v.duration

    # ── public ────────────────────────────────────────────────
    def build_timeline(self, story: Story) -> Tuple[List[dict], List[Moment]]:
        """Return list of {video_id, filename, path?, start, end} per story segment."""
        used: List[Tuple[str, float, float]] = []   # (video_id, start, end)
        picks: List[dict] = []
        all_moments: List[Moment] = []
        min_len = 1.6

        for seg in story.segments:
            want = max(min_len, float(seg.duration))
            best: Optional[dict] = None
            for video in self.videos:
                cand = self._best_window(video, seg, want, used)
                if cand and (best is None or cand["score"] > best["score"]):
                    best = cand
                    best["video_id"] = video.id
                    best["filename"] = video.filename
                    best["video_path"] = video.path
            if best is None:
                # extremely short footage: cycle what we have
                v = self.videos[0] if self.videos else None
                if v is None:
                    continue
                start = min(max(0.0, (seg.order - 1) * 2.0), max(0.0, v.duration - want))
                best = {"video_id": v.id, "filename": v.filename, "video_path": v.path,
                        "start": round(start, 2), "end": round(start + want, 2), "score": 0.0}
                used.append((v.id, start, start + want))
            else:
                used.append((best["video_id"], best["start"], best["end"]))
            all_moments.append(Moment(
                start=best["start"], end=best["end"], score=round(best.get("score", 0.0), 2),
                tags=["selected"], transcript=self._transcript_inside(best),
            ))
            picks.append({
                "video_id": best["video_id"],
                "filename": best.get("filename", ""),
                "video_path": best.get("video_path", ""),
                "start": round(best["start"], 2),
                "end": round(best["end"], 2),
                "duration": round(best["end"] - best["start"], 2),
                "score": round(best.get("score", 0.0), 2),
                "reasons": best.get("reasons", []),
            })
        return picks, all_moments

    def ranked_candidates(self, keywords: List[str], top_n: int = 10) -> List[dict]:
        """Expose ranking for UI/debugging."""
        out: List[dict] = []
        for v in self.videos:
            for start in range(0, max(1, int(v.duration)), 4):
                end = min(v.duration, start + 4)
                s = self._window_score(v.id, float(start), float(end), keywords)
                out.append({"video_id": v.id, "start": start, "end": round(end, 2), "score": round(s, 3)})
        out.sort(key=lambda c: c["score"], reverse=True)
        return out[:top_n]

    # ── internals ─────────────────────────────────────────────
    def _transcript_inside(self, window: dict) -> Optional[str]:
        g0 = self.ranges.get(window["video_id"], (0.0, 0.0))[0]
        gs, ge = g0 + window["start"], g0 + window["end"]
        parts = [ts["text"] for ts in self._speech_segments()
                 if ts["start"] < ge and ts["end"] > gs]
        return " ".join(parts)[:220] or None

    def _window_score(
        self, video_id: str, start: float, end: float, keywords: List[str]
    ) -> float:
        """Score a window using LOCAL (per-video) times; speech/silence are global."""
        score = 0.0
        g0 = self.ranges.get(video_id, (0.0, 0.0))[0]
        gs, ge = g0 + start, g0 + end

        # speech relevance
        for ts in self._speech_segments():
            if ts["start"] < ge and ts["end"] > gs:      # overlaps window (global time)
                ov = min(ts["end"], ge) - max(ts["start"], gs)
                rel = _overlap_score(keywords, ts["text"])
                if rel > 0:
                    dur = max(0.4, ts["end"] - ts["start"])
                    score += rel * min(1.5, ov / dur) * 1.6

        # silence penalty (silences stored in global time)
        for s_start, s_end in self.analysis.silence or []:
            inter = min(s_end, ge) - max(s_start, gs)
            if inter > 0:
                frac = inter / max(0.5, ge - gs)
                score -= frac * 0.9

        # scene-change bonus at window start
        for t in self.analysis.scene_changes or []:
            if abs(t - gs) <= 0.8:
                score += 0.15
                break

        # slight preference for earlier footage (establishing shots first)
        duration = self._video_duration(video_id)
        if duration > 0:
            score -= 0.08 * (start / duration)
        return score

    def _best_window(
        self, video: VideoMeta, seg, want: float, used: List[Tuple[str, float, float]]
    ) -> Optional[dict]:
        duration = video.duration
        step = 0.5
        best: Optional[dict] = None
        start = 0.0
        while start + want <= duration + 0.01:
            end = min(duration, start + want)
            if self._overlaps_used(video.id, start, end, used):
                start += step
                continue
            score = self._window_score(video.id, start, end, seg.keywords)
            snapped_s, snapped_e = self._snap_edges(video.id, start, end)
            if snapped_e - snapped_s >= want * 0.75 and not self._overlaps_used(video.id, snapped_s, snapped_e, used):
                score += 0.12  # reward clean cut points
                start_s, end_s = snapped_s, snapped_e
            else:
                start_s, end_s = start, end
            if best is None or score > best["score"]:
                best = {
                    "video_id": video.id, "filename": video.filename,
                    "video_path": video.path, "start": start_s, "end": end_s,
                    "score": score, "reasons": self._reasons_for(video.id, start_s, end_s),
                }
            start += step
        return best

    def _reasons_for(self, video_id: str, start: float, end: float) -> List[str]:
        reasons: List[str] = []
        g0 = self.ranges.get(video_id, (0.0, 0.0))[0]
        gs, ge = g0 + start, g0 + end
        for ts in self._speech_segments():
            if ts["start"] < ge and ts["end"] > gs and ts["text"].strip():
                reasons.append("speech")
                break
        for s_start, s_end in self.analysis.silence or []:
            if min(s_end, ge) - max(s_start, gs) > (ge - gs) * 0.5:
                reasons.append("quiet_zone")
                break
        else:
            reasons.append("clear_audio")
        return reasons or ["visual"]

    def _snap_edges(self, video_id: str, start: float, end: float) -> Tuple[float, float]:
        tol = 0.8
        g0 = self.ranges.get(video_id, (0.0, 0.0))[0]
        s, e = g0 + start, g0 + end
        for sil_start, sil_end in self.analysis.silence or []:
            if abs(sil_end - s) <= tol and sil_end < e:
                s = sil_end
            if abs(sil_start - e) <= tol and sil_start > s:
                e = sil_start
        return round(s - g0, 2), round(e - g0, 2)

    def _overlaps_used(self, video_id: str, start: float, end: float, used) -> bool:
        for vid, us, ue in used:
            if vid == video_id and start < ue - 0.15 and end > us + 0.15:
                return True
        return False

    def _speech_segments(self) -> List[dict]:
        if getattr(self, "_speech_cache", None) is not None:
            return self._speech_cache
        cache: List[dict] = []
        t = self.transcript
        if t and t.segments:
            for seg in t.segments:
                cache.append({"start": seg.start, "end": seg.end, "text": seg.text})
        self._speech_cache = cache
        return cache

    def _video_duration(self, video_id: str) -> float:
        for v in self.videos:
            if v.id == video_id:
                return v.duration
        return 0.0


def build_analysis_moments(videos: List[VideoMeta], transcript: Optional[Transcript]) -> List[Moment]:
    """High-information moments across all footage (used for UI + fallbacks)."""
    moments: List[Moment] = []
    for v in videos:
        tsegs = [
            seg for seg in (transcript.segments if transcript else [])
            if True
        ]
        # bucket transcript into ~8s blocks and score by information density
        block_dur = 8.0
        n_blocks = int(max(1, round(v.duration // block_dur)) + (1 if v.duration % block_dur else 0))
        for b in range(n_blocks):
            bs, be = b * block_dur, min(v.duration, (b + 1) * block_dur)
            text = " ".join(seg.text for seg in tsegs if seg.start < be and seg.end > bs)
            density = len(_tokens(text))
            score = min(1.0, 0.25 + density / 40.0)
            tags = ["speech"] if text.strip() else ["visual"]
            moments.append(Moment(start=bs, end=be, score=round(score, 2), tags=tags,
                                  transcript=text[:220] or None))
    return moments
