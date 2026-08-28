"""Nagrik backend entry point."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .core.config import ffmpeg_available
from .core.errors import NagrikError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

app = FastAPI(title="Nagrik API", version="0.1.0", docs_url="/api/docs")

# Local dev: the Next.js frontend runs on a different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NagrikError)
async def nagrik_error_handler(request: Request, exc: NagrikError):
    return JSONResponse(status_code=exc.status_code, content=exc.payload)


app.include_router(router)


@app.on_event("startup")
def startup_check():
    ok, path, version = ffmpeg_available()
    if not ok:
        logging.getLogger("nagrik").error(
            "FFmpeg not found! Nagrik cannot process video without it.\n"
            "  macOS:   brew install ffmpeg\n"
            "  Debian/Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: winget install Gyan.FFmpeg"
        )
