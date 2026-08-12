from abc import ABC, abstractmethod
from pathlib import Path


class BaseImageProvider(ABC):
    """Interface every image-generation provider must implement.

    Swap in a real provider (e.g. Stability AI, Replicate, OpenAI Images) by
    implementing this interface and wiring it up in image_service.py -
    nothing else in the app needs to change.
    """

    @abstractmethod
    async def generate_image(
        self, prompt: str, out_path: Path, width: int, height: int
    ) -> Path:
        """Generate an image for `prompt` and save it to `out_path`.

        Must return the path to the saved image. Must raise on failure so
        the caller can fall back gracefully.
        """
        raise NotImplementedError
