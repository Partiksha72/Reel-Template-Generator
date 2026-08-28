"""Text-to-speech abstraction (optional AI voiceover).

Providers:
  none   -> voiceover disabled
  openai -> OpenAI TTS API (modular: add more providers here)

Each generated clip is adjusted (tempo only, no pitch shift) to fit its
timeline slot so captions and visuals stay in sync.
"""
import subprocess
import tempfile
from pathlib import Path

from ..core.config import get_settings
from ..core.errors import ConfigurationError, NagrikError
from ..utils.ffmpeg import probe_media


class TTSProvider:
    name = "none"

    def configured(self) -> bool:
        return False

    def configuration_hint(self) -> str:
        return "Set TTS_PROVIDER=openai and TTS_API_KEY in your .env file."

    def synthesize(self, text: str, dest: Path) -> None:
        raise NotImplementedError


class OpenAITTSProvider(TTSProvider):
    name = "openai-tts"

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.tts_api_key or s.llm_api_key)

    def configuration_hint(self) -> str:
        return "Set TTS_API_KEY (or LLM_API_KEY) in your .env to enable AI voiceover."

    def synthesize(self, text: str, dest: Path) -> None:
        if not self.configured():
            raise ConfigurationError("AI voiceover (TTS)", hint=self.configuration_hint())
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ConfigurationError("OpenAI SDK", hint="pip install -r requirements.txt") from exc
        s = get_settings()
        client = OpenAI(api_key=s.tts_api_key or s.llm_api_key)
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_path = Path(tf.name)
            speech = client.audio.speech.create(
                model="tts-1", voice=s.tts_voice or "onyx", input=text[:4000], response_format="mp3",
            )
            speech.write_to_file(str(tmp_path))
            # normalize into the project's audio profile
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(tmp_path),
                 "-ar", "44100", "-ac", "2", "-b:a", "160k", str(dest)],
                check=True, capture_output=True, timeout=300,
            )
        except NagrikError:
            raise
        except Exception as exc:
            raise NagrikError(502, "tts_failed", "AI voiceover generation failed.",
                              detail=str(exc)[:400])
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass


def get_tts_provider() -> TTSProvider:
    s = get_settings()
    if s.tts_provider == "openai":
        return OpenAITTSProvider()
    return TTSProvider()


def tts_status() -> dict:
    p = get_tts_provider()
    return {"provider": p.name, "configured": p.configured(), "hint": "" if p.configured() else p.configuration_hint()}


def fit_audio_to_slot(src: Path, slot_seconds: float) -> float:
    """Slow down TTS audio at most 15% to better fit its slot. Returns new duration."""
    info = probe_media(src)
    dur = info["duration"]
    if dur <= 0 or slot_seconds <= 0:
        return dur
    target = slot_seconds * 0.97
    ratio = min(1.0, max(0.85, target / dur))
    if ratio >= 0.999:
        return dur
    tmp = src.with_suffix(".fit.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter:a", f"atempo={ratio:.4f}", str(tmp)],
        check=True, capture_output=True, timeout=120,
    )
    tmp.replace(src)
    return probe_media(src)["duration"]
