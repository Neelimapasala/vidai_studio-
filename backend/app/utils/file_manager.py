import os
import shutil
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
STORAGE_DIR = BASE_DIR / "storage"
IMAGES_DIR = STORAGE_DIR / "images"
AUDIO_DIR = STORAGE_DIR / "audio"
VIDEOS_DIR = STORAGE_DIR / "videos"
SUBTITLES_DIR = STORAGE_DIR / "subtitles"

for d in (IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, SUBTITLES_DIR):
    d.mkdir(parents=True, exist_ok=True)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def job_dir(job_id: str, kind: str) -> Path:
    """Return (and create) a per-job subdirectory under a storage kind."""
    mapping = {
        "images": IMAGES_DIR,
        "audio": AUDIO_DIR,
        "videos": VIDEOS_DIR,
        "subtitles": SUBTITLES_DIR,
    }
    root = mapping[kind]
    path = root / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_job(job_id: str) -> None:
    for root in (IMAGES_DIR, AUDIO_DIR, VIDEOS_DIR, SUBTITLES_DIR):
        p = root / job_id
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
