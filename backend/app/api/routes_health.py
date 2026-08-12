import shutil
import subprocess

from fastapi import APIRouter

from app.services.groq_service import groq_service
from app.utils.ffmpeg import ffmpeg_executable, ffprobe_executable

router = APIRouter()


def _binary_works(path: str) -> bool:
    """Actually try to run the binary, not just locate it - a stale PATH
    entry or a broken imageio-ffmpeg cache can otherwise report a false
    positive."""
    try:
        subprocess.run(
            [path, "-version"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        return True
    except Exception:
        return False


@router.get("/api/health")
async def health():
    ffmpeg_path = ffmpeg_executable()
    ffprobe_path = ffprobe_executable()
    return {
        "status": "ok",
        "groq_configured": groq_service.configured,
        "ffmpeg_available": _binary_works(ffmpeg_path),
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_available": bool(ffprobe_path) and _binary_works(ffprobe_path),
        "ffprobe_path": ffprobe_path or shutil.which("ffprobe"),
    }
