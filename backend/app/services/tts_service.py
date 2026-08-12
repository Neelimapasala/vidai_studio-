import asyncio
import logging
import os
import subprocess
from pathlib import Path

from app.providers.base_tts_provider import BaseTTSProvider
from app.utils.prompts import WORDS_PER_SECOND

logger = logging.getLogger("vidai.tts")

TTS_API_KEY = os.getenv("TTS_API_KEY", "").strip()


class OfflineTTSProvider(BaseTTSProvider):
    """Uses the pyttsx3 + espeak-ng offline engine - no internet or API key
    required, so voice-over always works out of the box."""

    def _pick_voice_id(self, engine, voice: str, language: str):
        try:
            voices = engine.getProperty("voices")
        except Exception:
            return None
        if not voices:
            return None

        lang_hint = {"English": "en", "Telugu": "te", "Hindi": "hi"}.get(language, "en")
        # Prefer a voice matching language; else any voice.
        candidates = [v for v in voices if lang_hint in (v.id or "").lower()] or voices

        wants_female = voice.lower() == "female"
        wants_male = voice.lower() == "male"
        if wants_female:
            for v in candidates:
                name = (v.name or v.id or "").lower()
                if "f" in name or "female" in name:
                    return v.id
        if wants_male:
            for v in candidates:
                name = (v.name or v.id or "").lower()
                if "m" in name or "male" in name:
                    return v.id
        return candidates[0].id

    def _synth_sync(self, text: str, out_path: Path, voice: str, language: str) -> Path:
        import pyttsx3

        engine = pyttsx3.init()
        rate = engine.getProperty("rate")
        engine.setProperty("rate", int(rate * 0.95))
        voice_id = self._pick_voice_id(engine, voice, language)
        if voice_id:
            engine.setProperty("voice", voice_id)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        engine.stop()
        return out_path

    async def synthesize(self, text: str, out_path: Path, voice: str, language: str) -> Path:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._synth_sync, text, out_path, voice, language
        )


offline_tts_provider = OfflineTTSProvider()


from app.utils.ffmpeg import ffmpeg_executable


def _make_silent_audio(out_path: Path, duration: float) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg_executable(), "-y", "-f", "lavfi",
            "-i", f"anullsrc=r=24000:cl=mono",
            "-t", str(max(0.5, duration)),
            "-q:a", "9",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path


async def generate_narration_audio(
    text: str, out_path: Path, voice: str, language: str, fallback_duration: float
) -> tuple[Path, bool]:
    """Returns (path, used_real_voice). Never raises - always produces a
    usable audio file so rendering can proceed."""
    try:
        path = await offline_tts_provider.synthesize(text, out_path, voice, language)
        if path.exists() and path.stat().st_size > 44:  # bigger than empty wav header
            return path, True
        raise RuntimeError("empty audio output")
    except Exception as exc:
        logger.warning("TTS failed (%s) - using silent placeholder audio", exc)
        est_duration = max(
            fallback_duration, len(text.split()) / WORDS_PER_SECOND
        )
        return _make_silent_audio(out_path, est_duration), False
