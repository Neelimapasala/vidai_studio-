import shutil
from typing import Optional

try:
    from imageio_ffmpeg import get_ffmpeg_exe
except ImportError:
    get_ffmpeg_exe = None


def ffmpeg_executable() -> str:
    """Return a usable ffmpeg executable path, falling back to PATH or raw name."""
    if get_ffmpeg_exe is not None:
        try:
            return get_ffmpeg_exe()
        except Exception:
            pass
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe_executable() -> Optional[str]:
    """Return a usable ffprobe executable path if available."""
    return shutil.which("ffprobe")
