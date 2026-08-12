import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import jobs
from app.models.scene import SceneRegenerateRequest
from app.models.video import JobStatus, VideoCreateRequest
from app.services import caption_service, tts_service
from app.services.groq_service import GroqGenerationError, GroqNotConfigured
from app.utils.file_manager import job_dir

router = APIRouter(prefix="/api/video")


@router.post("/create", response_model=JobStatus)
async def create_video(req: VideoCreateRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    jobs.JOBS[job_id] = JobStatus(job_id=job_id, status="queued", stage="Queued", progress=0)
    background_tasks.add_task(jobs.run_video_pipeline, job_id, req)
    return jobs.JOBS[job_id]


@router.post("/script")
async def generate_script_only(req: VideoCreateRequest):
    """Preview the AI-generated script/scene plan without rendering media."""
    try:
        script, used_groq = await jobs._get_script(req)
    except (GroqNotConfigured, GroqGenerationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"script": script.model_dump(), "used_groq": used_groq}


@router.post("/scenes")
async def plan_scenes(req: VideoCreateRequest):
    """Alias of /script that returns just the scene list - useful when the
    frontend already has a script and only needs the scene breakdown."""
    try:
        script, used_groq = await jobs._get_script(req)
    except (GroqNotConfigured, GroqGenerationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"scenes": [s.model_dump() for s in script.scenes], "used_groq": used_groq}


class RegenerateSceneBody(SceneRegenerateRequest):
    video_id: str


@router.post("/scene/{scene_number}/regenerate")
async def regenerate_scene(scene_number: int, body: RegenerateSceneBody):
    try:
        record = await jobs.regenerate_single_scene(
            body.video_id,
            scene_number,
            {"visual_prompt": body.visual_prompt, "narration": body.narration},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Couldn't regenerate that scene. Please try again.",
        )
    return record.model_dump()


class VoiceRequest(BaseModel):
    text: str
    voice: str = "Neutral"
    language: str = "English"


@router.post("/voice")
async def generate_voice(body: VoiceRequest):
    """Utility endpoint: synthesize a one-off narration clip."""
    out_path = job_dir("adhoc", "audio") / f"{uuid.uuid4().hex[:8]}.wav"
    path, used_real_voice = await tts_service.generate_narration_audio(
        body.text, out_path, body.voice, body.language, fallback_duration=2.0
    )
    return {"audio_path": str(path), "used_real_voice": used_real_voice}


class CaptionsRequest(BaseModel):
    video_id: str


@router.post("/captions")
async def get_captions(body: CaptionsRequest):
    record = jobs.get_video(body.video_id)
    if not record:
        raise HTTPException(status_code=404, detail="Video not found")
    srt = caption_service.build_srt(record.scenes, [s.duration for s in record.scenes])
    return {"srt": srt}


class RenderRequest(BaseModel):
    video_id: str


@router.post("/render")
async def rerender_video(body: RenderRequest):
    """Re-render the final MP4 from current (possibly edited) scene clips."""
    workspace = jobs.WORKSPACES.get(body.video_id)
    record = jobs.get_video(body.video_id)
    if not workspace or not record:
        raise HTTPException(status_code=404, detail="Video not found")
    from app.services import video_renderer

    clip_paths = [Path(p) for p in workspace["clips"]]
    final_path = Path(workspace["work_dir"]) / "final.mp4"
    srt_path = Path(workspace["srt_path"]) if workspace.get("srt_path") else None
    await video_renderer.render_final_video(
        clip_paths, srt_path, Path(workspace["work_dir"]), final_path,
        add_music=workspace["request"].get("background_music", False),
    )
    record.video_path = str(final_path)
    return record.model_dump()


@router.get("/status/{job_id}", response_model=JobStatus)
async def video_status(job_id: str):
    status = jobs.get_job(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.get("/{video_id}")
async def get_video(video_id: str):
    record = jobs.get_video(video_id)
    if not record:
        raise HTTPException(status_code=404, detail="Video not found")
    return record.model_dump()


@router.get("/{video_id}/download")
async def download_video(video_id: str):
    record = jobs.get_video(video_id)
    if not record or not record.video_path or not Path(record.video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(
        record.video_path,
        media_type="video/mp4",
        filename=f"{record.title[:40].strip().replace(' ', '_') or 'vidai_video'}.mp4",
    )
