"""Central configuration, loaded from environment / .env file."""
import os
import shutil
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    # LLM
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # STT
    stt_provider: str = "local"  # local | openai
    stt_model: str = "base"
    stt_api_key: str = ""

    # TTS
    tts_provider: str = "none"  # none | openai
    tts_voice: str = "onyx"
    tts_api_key: str = ""

    # Storage / server
    storage_backend: str = "local"
    data_dir: Path = Path("./data")
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    max_upload_mb: int = 2048

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parents[3] / p).resolve()
        return p

    @property
    def assets_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "assets"


def _load_env_file() -> None:
    """Minimal .env loader (repo root or backend/). Does not override existing env."""
    for candidate in (Path(__file__).resolve().parents[3] / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
            break


_load_env_file()

_ENV_MAP = {
    "LLM_PROVIDER": "llm_provider", "LLM_API_KEY": "llm_api_key", "LLM_BASE_URL": "llm_base_url",
    "LLM_MODEL": "llm_model", "STT_PROVIDER": "stt_provider", "STT_MODEL": "stt_model",
    "STT_API_KEY": "stt_api_key", "TTS_PROVIDER": "tts_provider", "TTS_VOICE": "tts_voice",
    "TTS_API_KEY": "tts_api_key", "STORAGE_BACKEND": "storage_backend", "DATA_DIR": "data_dir",
    "BACKEND_HOST": "backend_host", "BACKEND_PORT": "backend_port", "MAX_UPLOAD_MB": "max_upload_mb",
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw = {}
    for env_key, field in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None and val != "":
            raw[field] = val
    return Settings(**raw)


def ffmpeg_available() -> tuple:
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    version = None
    ok = bool(ff and fp)
    if ok:
        try:
            import subprocess
            out = subprocess.run([ff, "-version"], capture_output=True, text=True, timeout=10)
            version = out.stdout.splitlines()[0].replace("ffmpeg version ", "").split(" ")[0]
        except Exception:
            pass
    return ok, (ff or "ffmpeg"), version
