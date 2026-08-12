import json
import logging
import os
import re

from pydantic import ValidationError

from app.models.video import VideoScript
from app.utils.prompts import (
    build_repair_prompt,
    build_script_system_prompt,
    build_script_user_prompt,
)

logger = logging.getLogger("vidai.groq")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class GroqNotConfigured(Exception):
    pass


class GroqGenerationError(Exception):
    pass


def _extract_json(text: str) -> str:
    """Strip markdown fences / stray prose and isolate the JSON object."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


class GroqService:
    def __init__(self) -> None:
        self._client = None
        if GROQ_API_KEY:
            try:
                from groq import AsyncGroq

                self._client = AsyncGroq(api_key=GROQ_API_KEY)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize Groq client: %s", exc)
                self._client = None

    @property
    def configured(self) -> bool:
        return self._client is not None

    async def _chat(self, system: str, user: str) -> str:
        if not self._client:
            raise GroqNotConfigured("GROQ_API_KEY is not set")
        response = await self._client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    async def generate_script(
        self,
        idea: str,
        duration: int,
        style: str,
        voice: str,
        language: str,
        aspect_ratio: str,
    ) -> VideoScript:
        if not self._client:
            raise GroqNotConfigured("GROQ_API_KEY is not set")

        system = build_script_system_prompt()
        user = build_script_user_prompt(
            idea, duration, style, voice, language, aspect_ratio
        )

        raw = await self._chat(system, user)
        parsed, err = self._try_parse(raw)
        if parsed:
            return parsed

        # Attempt one repair round-trip
        logger.info("Groq JSON failed validation once, attempting repair: %s", err)
        repair_prompt = build_repair_prompt(raw, err or "invalid JSON")
        try:
            raw2 = await self._chat(system, repair_prompt)
        except Exception as exc:
            raise GroqGenerationError(f"Groq request failed during repair: {exc}")

        parsed2, err2 = self._try_parse(raw2)
        if parsed2:
            return parsed2

        raise GroqGenerationError(
            f"Groq returned invalid script JSON after repair attempt: {err2}"
        )

    @staticmethod
    def _try_parse(raw: str):
        try:
            cleaned = _extract_json(raw)
            data = json.loads(cleaned)
            # normalize scene numbers if missing
            for i, s in enumerate(data.get("scenes", []), start=1):
                s.setdefault("scene_number", i)
                s.setdefault("media_type", "image")
                s.setdefault("transition", "fade")
            script = VideoScript(**data)
            return script, None
        except (json.JSONDecodeError, ValidationError, TypeError, KeyError) as exc:
            return None, str(exc)


groq_service = GroqService()
