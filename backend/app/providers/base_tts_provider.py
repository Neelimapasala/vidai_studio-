from abc import ABC, abstractmethod
from pathlib import Path


class BaseTTSProvider(ABC):
    """Interface every text-to-speech provider must implement."""

    @abstractmethod
    async def synthesize(
        self, text: str, out_path: Path, voice: str, language: str
    ) -> Path:
        """Synthesize `text` to speech and save as a WAV/MP3 at `out_path`.

        Must return the path to the saved audio. Must raise on failure so
        the caller can fall back gracefully (e.g. to silent audio).
        """
        raise NotImplementedError
