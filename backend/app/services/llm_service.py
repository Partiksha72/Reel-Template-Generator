"""LLM abstraction over any OpenAI-compatible chat completions endpoint.

Works with OpenAI, Groq, Together, Ollama, LM Studio, etc. — only the base
URL, API key and model name change (see .env.example).
"""
import json
import re
from typing import Any, Dict, List

from ..core.config import get_settings
from ..core.errors import ConfigurationError, NagrikError


class LLMProvider:
    name = "openai-compatible"

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.llm_api_key) or "localhost" in s.llm_base_url or "127.0.0.1" in s.llm_base_url

    def configuration_hint(self) -> str:
        s = get_settings()
        return (
            f"Set LLM_API_KEY in your .env file for {s.llm_base_url} "
            f"(model: {s.llm_model}). See .env.example."
        )

    def complete_json(self, system: str, user: str, max_tokens: int = 2400, temperature: float = 0.4) -> Dict[str, Any]:
        settings = get_settings()
        if not self.configured():
            raise ConfigurationError("AI story generation (LLM)", hint=self.configuration_hint())
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ConfigurationError(
                "OpenAI SDK", hint="Install backend requirements: pip install -r requirements.txt",
            ) from exc

        client = OpenAI(api_key=settings.llm_api_key or "not-needed", base_url=settings.llm_base_url)
        try:
            resp = client.chat.completions.create(
                model=settings.llm_model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            # Some OpenAI-compatible providers reject response_format; retry without it.
            msg = str(exc)
            if "response_format" in msg or "json_object" in msg.lower():
                try:
                    resp = client.chat.completions.create(
                        model=settings.llm_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        messages=[
                            {"role": "system", "content": system + "\nRespond with ONLY a valid JSON object."},
                            {"role": "user", "content": user},
                        ],
                    )
                except Exception as exc2:
                    raise NagrikError(502, "llm_request_failed",
                                      "The AI service returned an error.", detail=str(exc2)[:400]) from exc2
            else:
                raise NagrikError(502, "llm_request_failed",
                                  "The AI service returned an error.",
                                  detail=msg[:400],
                                  hint="Check LLM_API_KEY / LLM_BASE_URL / LLM_MODEL in your .env file.") from exc

        content = resp.choices[0].message.content or ""
        return parse_json_loose(content)


def parse_json_loose(content: str) -> Dict[str, Any]:
    """Parse JSON from a model response, tolerating code fences and stray text."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise NagrikError(
            status_code=502, code="llm_bad_json",
            message="The AI returned a malformed story structure.",
            detail=f"{exc}: {text[:200]}…",
            hint="Try Regenerate Story — LLMs occasionally emit invalid JSON.",
        )


def llm_status() -> dict:
    p = LLMProvider()
    s = get_settings()
    return {
        "provider": p.name,
        "configured": p.configured(),
        "base_url": s.llm_base_url,
        "model": s.llm_model,
        "hint": "" if p.configured() else p.configuration_hint(),
    }


def extract_keywords(text: str, top_n: int = 8) -> List[str]:
    """Cheap local keyword extraction used by clip selection (not AI)."""
    stop = {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "at", "by",
        "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these",
        "those", "as", "has", "have", "had", "will", "would", "can", "could", "should", "do",
        "does", "did", "not", "no", "yes", "you", "your", "we", "our", "they", "their", "he",
        "she", "his", "her", "i", "me", "my", "what", "when", "where", "why", "how", "here",
        "about", "into", "over", "after", "before", "between", "under", "above", "so", "just",
        "very", "now", "new", "also", "some", "any", "all", "more", "most", "other", "than",
        "then", "them", "there", "from", "up", "out", "if", "while", "because",
    }
    words = re.findall(r"[a-zA-Z\u0900-\u097F]{3,}", text.lower())
    freq: Dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [w for w, _ in ranked[:top_n]]
