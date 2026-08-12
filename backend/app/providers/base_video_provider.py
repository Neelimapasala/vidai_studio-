from abc import ABC, abstractmethod
from pathlib import Path


class BaseVideoProvider(ABC):
    """Interface for a real text/image-to-video generation provider.

    Not implemented by default (real video-gen APIs are paid). When absent,
    video_service.py automatically falls back to the Ken Burns image-motion
    pipeline so the app always produces a working MP4.
    """

    @abstractmethod
    async def generate_clip(
        self, prompt: str, out_path: Path, duration: float, width: int, height: int
    ) -> Path:
        raise NotImplementedError
