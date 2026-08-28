"""Speech-to-text abstraction.

Providers:
  local  -> faster-whisper running on this machine (no API key needed)
  openai -> OpenAI Whisper API

Both return a normalized Transcript. Failures raise ConfigurationError or
NagrikError with the *actual* underlying error surfaced in `detail`.
"""
import tempfile
from pathlib import Path
from typing import List, Optional

from ..core.config import get_settings
from ..core.errors import ConfigurationError, NagrikError
from ..schemas.models import Transcript, TranscriptSegment


class STTProvider:
    name = "base"

    def configured(self) -> bool:
        return True

    def configuration_hint(self) -> str:
        return ""

    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Transcript:
        raise NotImplementedError


class LocalWhisperProvider(STTProvider):
    name = "whisper-local"

    def __init__(self) -> None:
        self._model = None
        self._model_size = None

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ConfigurationError(
                "Local transcription (faster-whisper)",
                hint="Install backend dependencies:  cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt",
            ) from exc
        settings = get_settings()
        size = settings.stt_model or "base"
        if self._model is None or self._model_size != size:
            try:
                # int8 keeps CPU memory low; first run downloads the model (~75MB for base)
                self._model = WhisperModel(size, device="cpu", compute_type="int8")
                self._model_size = size
            except Exception as exc:
                raise NagrikError(
                    status_code=500, code="stt_model_load_failed",
                    message="Could not load the local Whisper model.",
                    detail=str(exc)[:400],
                    hint="Check your internet connection — the model is downloaded on first use.",
                )
        return self._model

    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Transcript:
        model = self._load_model()
        lang_map = {"hindi": "hi", "english": "en", "hinglish": None}
        whisper_lang = lang_map.get((language or "").lower())
        try:
            segments_iter, info = model.transcribe(
                str(audio_path), language=whisper_lang, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
            )
            segments: List[TranscriptSegment] = []
            for seg in segments_iter:
                text = seg.text.strip()
                if text:
                    segments.append(TranscriptSegment(
                        start=round(seg.start, 2), end=round(seg.end, 2), text=text,
                    ))
            return Transcript(provider=self.name, language=getattr(info, "language", None), segments=segments)
        except ConfigurationError:
            raise
        except Exception as exc:
            raise NagrikError(
                status_code=500, code="transcription_failed",
                message="Speech transcription failed.",
                detail=str(exc)[:400],
                hint="You can continue without a transcript — clip selection will fall back to visual analysis.",
            )


class OpenAIWhisperProvider(STTProvider):
    name = "openai-whisper-api"

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.stt_api_key or s.llm_api_key)

    def configuration_hint(self) -> str:
        return "Set STT_API_KEY (or LLM_API_KEY) in your .env file to use OpenAI Whisper."

    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Transcript:
        if not self.configured():
            raise ConfigurationError("OpenAI Whisper (STT)", hint=self.configuration_hint())
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ConfigurationError(
                "OpenAI SDK", hint="pip install -r requirements.txt",
            ) from exc
        s = get_settings()
        client = OpenAI(api_key=s.stt_api_key or s.llm_api_key, base_url=s.llm_base_url or None)

        # The API accepts files up to 25MB; extract compressed mono audio first.
        with tempfile.TemporaryDirectory(prefix="nagrik_stt_") as td:
            compressed = Path(td) / "audio.mp3"
            import subprocess
            proc = subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-i", str(audio_path),
                "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(compressed),
            ], capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise NagrikError(status_code=500, code="audio_extract_failed",
                                  message="Could not extract audio for transcription.",
                                  detail=proc.stderr[:300])
            try:
                with compressed.open("rb") as f:
                    kwargs = {"model": "whisper-1", "file": f,
                              "response_format": "verbose_json", "timestamp_granularities[]": ["segment"]}
                    lang_map = {"hindi": "hi", "english": "en"}
                    wl = lang_map.get((language or "").lower())
                    if wl:
                        kwargs["language"] = wl
                    result = client.audio.transcriptions.create(**kwargs)
            except Exception as exc:
                raise NagrikError(
                    status_code=502, code="transcription_failed",
                    message="The speech-to-text service returned an error.",
                    detail=str(exc)[:400],
                )
        segments = [
            TranscriptSegment(start=round(float(s.start), 2), end=round(float(s.end), 2), text=s.text.strip())
            for s in getattr(result, "segments", []) or []
            if s.text and s.text.strip()
        ]
        return Transcript(provider=self.name, language=getattr(result, "language", None), segments=segments)


def get_stt_provider() -> STTProvider:
    s = get_settings()
    if s.stt_provider == "openai":
        return OpenAIWhisperProvider()
    return LocalWhisperProvider()


def stt_status() -> dict:
    p = get_stt_provider()
    return {
        "provider": p.name,
        "configured": p.configured(),
        "hint": "" if p.configured() else p.configuration_hint(),
    }
