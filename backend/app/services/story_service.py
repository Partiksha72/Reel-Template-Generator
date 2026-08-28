"""Story generation: turns the user's overview into a structured, fact-safe reel script.

Fact-safety contract enforced here:
  * The prompt forbids inventing statistics, quotes, names, dates or claims.
  * Every generated segment carries `keywords` used later for clip matching.
  * `source_facts` lists only facts traceable to the user's overview.
  * `creative_note` records where creative (non-factual) language was applied.
"""
import re
from typing import Any, Dict, List

from ..core.errors import NagrikError
from ..schemas.models import ProjectSettings, SourceFact, Story, StorySegment
from .llm_service import LLMProvider

VALID_SECTIONS = {"hook", "context", "development", "key_fact", "impact", "ending"}

SYSTEM_PROMPT = """You are the senior scriptwriter for NAGRIK (नागरिक), a premium Indian civic-news reel studio.
You turn raw notes about a civic/news story into a tight short-form vertical video script.

STRICT FACT-SAFETY RULES (highest priority):
- Use ONLY facts present in the user's overview. NEVER invent statistics, quotes, names, dates, numbers, places or claims.
- Do not exaggerate or sensationalize. Preserve uncertainty ("reportedly", "according to the overview").
- If key information is missing, phrase neutrally (e.g. "details are still emerging") — do NOT fill gaps.
- Clearly separate factual statements from creative framing. In "creative_note", list where you added purely stylistic/creative language.

EDITORIAL STYLE (Brut-inspired but original):
- Structure: HOOK (0-3s curiosity) → CONTEXT → DEVELOPMENT / KEY FACTS → IMPACT on ordinary citizens → ENDING + CTA.
- Short punchy sentences. Present tense where honest. Mobile-first phrasing.
- Captions are LARGE on-screen text: max ~8 words, strong, no punctuation-heavy sentences.
- The hook must create genuine curiosity WITHOUT misrepresenting the story.
- End with a civic CTA like "Would this work in your city?" or "Follow Nagrik for more civic updates."

OUTPUT: one JSON object, exactly this shape:
{
  "hook": "...",
  "headline": "...",
  "story": "one-paragraph summary of the reel",
  "segments": [
    {
      "order": 1,
      "section": "hook|context|development|key_fact|impact|ending",
      "duration": <seconds as number, summing to the target duration>,
      "voiceover": "<spoken line(s) for this segment>",
      "caption": "<large on-screen caption, <=8 words>",
      "visual_instruction": "<what kind of footage should play>",
      "emphasis_words": ["<1-3 words from caption to visually emphasize>"],
      "keywords": ["<4-6 search keywords to find matching raw footage>"]
    }
  ],
  "ending": "...",
  "cta": "...",
  "source_facts": ["<each distinct fact you used, copied faithfully from the overview>"],
  "creative_note": "<where you added creative language beyond the given facts>",
  "warnings": ["<anything you could not verify or had to phrase neutrally>"]
}

Segment count guidance: {segment_count} segments for a {target_seconds}-second reel. Segment durations must sum to approximately {target_seconds} seconds.
Language: write in {language}. Tone: {tone}. Platform aspect: {platform}.
"""


def _target_segments(target_seconds: int) -> int:
    return max(4, min(9, round(target_seconds / 7)))



def _fallback_story(overview: str, settings: "ProjectSettings") -> Story:
    """Deterministic template story — runs with no API key so the whole pipeline stays usable."""
    import re as _re2
    txt = overview.strip()
    # Extract headline-ish first sentence
    first = _re2.split(r'[.!?]+', txt)[0].strip()[:80] if txt else "Civic update"
    words = _re2.findall(r"[A-Za-z\u0900-\u097F]{4,}", txt.lower())
    # lightweight keywords: most frequent non-stopword tokens
    from .llm_service import extract_keywords as _xk
    kws = _xk(txt, top_n=12)
    def pick(n): return kws[n % len(kws)] if kws else "civic"

    target = int(settings.duration_target or 30)
    n_seg = max(4, min(6, round(target / 7)))
    # Split overview into sentences for source facts
    sents = [ss.strip() for ss in _re2.split(r'[.!?]+', txt) if ss.strip()][:8]
    facts = [SourceFact(fact=ss[:280]) for ss in sents[:4]] or [SourceFact(fact=first)]

    # Build sections with editorial pacing
    templates = [
        ("hook",       3.5, f"{first[:55]}.",         "THIS JUST HAPPENED",      "wide city establishing shot"),
        ("context",    5.0, sents[0] if len(sents)>0 else txt[:120], "HERE'S WHAT WE KNOW", "signage / street context"),
        ("key_fact",   5.0, sents[1] if len(sents)>1 else txt[80:200], "WHAT IT MEANS FOR YOU", "residents / crowd"),
        ("impact",     5.5, sents[2] if len(sents)>2 else "Citizens are watching how this unfolds.", "RESIDENTS HAVE QUESTIONS", "interview / daily life"),
        ("ending",     4.0, "Would this work in your city?", "WOULD THIS WORK IN YOUR CITY?" , "wide city closing shot"),
    ]
    # Trim/pad to n_seg
    templates = templates[:n_seg]
    # Scale durations to target
    total = sum(t[1] for t in templates)
    scale = target / total if total else 1
    segs = []
    for i, (section, dur, voice, caption, visual) in enumerate(templates):
        d = round(max(2.0, min(10.0, dur*scale)), 1)
        cap = caption[:52]
        toks = _re2.findall(r"[A-Za-z0-9\u0900-\u097F]+", cap)
        emph = [toks[-1]] if toks else []
        kwords = [pick(i*2), pick(i*2+1), pick(i+3), "civic"]
        segs.append(StorySegment(order=i+1, section=section, duration=d,
                                 voiceover=voice[:220], caption=cap,
                                 visual_instruction=visual,
                                 emphasis_words=emph[:2], keywords=kwords[:6]))
    return Story(hook=segs[0].voiceover, headline=first, story=txt[:500],
                 segments=segs, ending=segs[-1].voiceover,
                 cta="Follow Nagrik for more civic updates.",
                 source_facts=facts,
                 creative_note="Template fallback — add an LLM key for richer editorial copy.",
                 warnings=["Using template story engine (no LLM key). Add LLM_API_KEY for AI-polished scripts."])


def build_user_prompt(overview: str, settings: ProjectSettings, has_transcript_brief: str = "") -> str:
    return f"""TARGET DURATION: {settings.duration_target} seconds
LANGUAGE: {settings.language}
TONE: {settings.tone}
PLATFORM: {settings.platform}

=== STORY OVERVIEW (the ONLY source of facts) ===
{overview.strip() or "(no overview provided — ask for neutral framing)"}
===
{has_transcript_brief}
Write the JSON object now."""


def generate_story(
    overview: str,
    settings: ProjectSettings,
    transcript_summary: str = "",
) -> Story:
    provider = LLMProvider()
    system = (
        SYSTEM_PROMPT
        .replace("{segment_count}", str(_target_segments(settings.duration_target)))
        .replace("{target_seconds}", str(settings.duration_target))
        .replace("{language}", settings.language)
        .replace("{tone}", settings.tone)
        .replace("{platform}", settings.platform)
    )
    transcript_block = ""
    if transcript_summary:
        transcript_block = (
            "=== FOOTAGE TRANSCRIPT (context about what was recorded; also user-provided material) ===\n"
            f"{transcript_summary}\n===\n"
        )
    try:
        data = provider.complete_json(system, build_user_prompt(overview, settings, transcript_block))
        story = validate_story(data)
        story = audit_facts(story, overview)
        return story
    except Exception as exc:
        # Any LLM error -> deterministic fallback so the pipeline stays end-to-end usable
        # Preserve the original error as a warning when possible
        fb = _fallback_story(overview, settings)
        msg = str(getattr(exc, 'detail', str(exc)))[:220] if hasattr(exc, 'detail') or exc else ''
        if msg:
            fb.warnings.append(f"LLM unavailable ({msg[:120]}); used template story instead.")
        return fb


def validate_story(data: Dict[str, Any]) -> Story:
    if not isinstance(data, dict):
        raise NagrikError(502, "llm_bad_json", "The AI returned an unexpected story structure.")
    segments_raw = data.get("segments") or []
    if not isinstance(segments_raw, list) or len(segments_raw) == 0:
        raise NagrikError(502, "llm_bad_json", "The AI returned no story segments.",
                          hint="Click 'Regenerate Story' to try again.")

    segments: List[StorySegment] = []
    order = 0
    for seg in segments_raw[:12]:
        if not isinstance(seg, dict):
            continue
        order += 1
        section = str(seg.get("section") or "context").lower().strip()
        if section not in VALID_SECTIONS:
            section = "context"
        duration = _to_float(seg.get("duration"), 4.0)
        segments.append(StorySegment(
            order=order,
            section=section,
            duration=max(1.5, min(15.0, duration)),
            voiceover=str(seg.get("voiceover") or "").strip(),
            caption=str(seg.get("caption") or seg.get("voiceover") or "").strip(),
            visual_instruction=str(seg.get("visual_instruction") or "").strip(),
            emphasis_words=[str(w)[:40] for w in (seg.get("emphasis_words") or [])][:4],
            keywords=[str(k)[:60] for k in (seg.get("keywords") or [])][:8],
        ))

    if len(segments) == 0:
        raise NagrikError(502, "llm_bad_json", "The AI story had no usable segments.")

    facts = [SourceFact(fact=str(f)[:500]) for f in (data.get("source_facts") or []) if str(f).strip()]
    warnings = [str(w)[:300] for w in (data.get("warnings") or []) if str(w).strip()]

    return Story(
        hook=str(data.get("hook") or segments[0].voiceover or "").strip(),
        headline=str(data.get("headline") or "").strip()[:120],
        story=str(data.get("story") or "").strip(),
        segments=segments,
        ending=str(data.get("ending") or segments[-1].voiceover or "").strip(),
        cta=str(data.get("cta") or "Follow Nagrik for more civic updates.").strip(),
        source_facts=facts,
        creative_note=str(data.get("creative_note") or "").strip()[:1000],
        warnings=warnings,
    )


def audit_facts(story: Story, overview: str) -> Story:
    """Flag generated claims that don't appear (even fuzzily) in the user's overview."""
    if not overview.strip():
        return story
    ov_words = set(re.findall(r"[a-zA-Z\u0900-\u097F]{4,}", overview.lower()))
    audited: List[SourceFact] = []
    flagged = 0
    for sf in story.source_facts:
        fact_words = re.findall(r"[a-zA-Z\u0900-\u097F]{4,}", sf.fact.lower())
        if not fact_words:
            continue
        overlap = sum(1 for w in fact_words if w in ov_words) / len(fact_words)
        origin = "user_overview" if overlap >= 0.34 else "needs_review"
        if origin == "needs_review":
            flagged += 1
        audited.append(SourceFact(fact=sf.fact, origin=origin))
    story.source_facts = audited
    if flagged:
        story.warnings.append(
            f"{flagged} stated fact(s) could not be confidently traced to your overview — review them before publishing."
        )
    return story


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def regenerate_section(story: Story, index: int, instruction: str) -> StorySegment:
    """Regenerate a single story segment via the LLM while keeping the rest stable."""
    seg = story.segments[index]
    provider = LLMProvider()
    system = (
        "You rewrite ONE segment of a civic news reel script. Keep facts identical — never add new facts, "
        "numbers, quotes or names. Respond with ONLY a JSON object: "
        '{"voiceover":"...","caption":"...","emphasis_words":["..."],"visual_instruction":"...","keywords":["..."]}'
    )
    user = (
        f"Full story context: {story.story}\n\n"
        f"Section type: {seg.section}\n"
        f"Current voiceover: {seg.voiceover}\n"
        f"Current caption: {seg.caption}\n\n"
        f"Rewrite instruction: {instruction or 'Make it sharper and more engaging.'}"
    )
    try:
        data = provider.complete_json(system, user, max_tokens=400, temperature=0.7)
    except Exception:
        # Fallback: light rephrase (shuffle emphasis/caption casing)
        seg.caption = seg.caption.upper() if seg.caption else seg.caption
        if seg.emphasis_words:
            seg.emphasis_words = list(reversed(seg.emphasis_words))
        return seg
    seg.voiceover = str(data.get("voiceover") or seg.voiceover).strip()
    seg.caption = str(data.get("caption") or seg.caption).strip()
    seg.emphasis_words = [str(w)[:40] for w in (data.get("emphasis_words") or seg.emphasis_words)][:4]
    seg.visual_instruction = str(data.get("visual_instruction") or seg.visual_instruction).strip()
    seg.keywords = [str(k)[:60] for k in (data.get("keywords") or seg.keywords)][:8]
    return seg
