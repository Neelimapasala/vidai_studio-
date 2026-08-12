from fastapi import APIRouter, HTTPException

from app.models.video import VideoCreateRequest
from app.services.groq_service import groq_service, GroqNotConfigured, GroqGenerationError
from app.utils.prompts import build_script_system_prompt, build_script_user_prompt

router = APIRouter(prefix="/api/groq")


@router.post("/script")
async def groq_generate_script(req: VideoCreateRequest):
    """Generate a parsed script directly from Groq (no demo fallback)."""
    try:
        script = await groq_service.generate_script(
            idea=req.prompt,
            duration=req.duration,
            style=req.style,
            voice=req.voice,
            language=req.language,
            aspect_ratio=req.aspect_ratio,
        )
    except (GroqNotConfigured, GroqGenerationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"script": script.model_dump(), "used_groq": True}


@router.post("/raw")
async def groq_raw_output(req: VideoCreateRequest):
    """Return the raw Groq assistant text output (unparsed)."""
    if not groq_service.configured:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY is not configured")
    system = build_script_system_prompt()
    user = build_script_user_prompt(
        req.prompt, req.duration, req.style, req.voice, req.language, req.aspect_ratio
    )
    try:
        # Accessing the internal chat helper to get raw output
        raw = await groq_service._chat(system, user)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"raw": raw}
