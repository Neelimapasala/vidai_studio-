from pathlib import Path
from typing import List

from app.models.scene import Scene


def _srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(scenes: List[Scene], durations: List[float]) -> str:
    """durations: actual per-scene duration (seconds), same order as scenes."""
    lines = []
    t = 0.0
    for i, (scene, dur) in enumerate(zip(scenes, durations), start=1):
        start = t
        end = t + dur
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}")
        lines.append(scene.caption.upper())
        lines.append("")
        t = end
    return "\n".join(lines)


def write_srt(scenes: List[Scene], durations: List[float], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_srt(scenes, durations), encoding="utf-8")
    return out_path
