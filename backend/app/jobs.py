import logging
import os
from pathlib import Path
from typing import Dict, Optional

from app.models.scene import Scene
from app.models.video import JobStatus, VideoCreateRequest, VideoRecord
from app.services import caption_service, image_service, scene_service, tts_service, video_renderer
from app.services.groq_service import GroqGenerationError, GroqNotConfigured, groq_service
from app.utils.file_manager import job_dir, new_id

logger = logging.getLogger("vidai.jobs")

USE_DEMO_MODE = os.getenv("USE_DEMO_MODE", "true").lower() == "true"

JOBS: Dict[str, JobStatus] = {}
VIDEOS: Dict[str, VideoRecord] = {}
WORKSPACES: Dict[str, dict] = {}  # video_id -> {clips, srt_path, work_dir, request}


def _set_status(job_id: str, **kwargs) -> None:
    status = JOBS.get(job_id)
    if not status:
        return
    for k, v in kwargs.items():
        setattr(status, k, v)


def get_job(job_id: str) -> Optional[JobStatus]:
    return JOBS.get(job_id)


def get_video(video_id: str) -> Optional[VideoRecord]:
    return VIDEOS.get(video_id)


async def _get_script(req: VideoCreateRequest):
    """Try Groq; fall back to the offline sample script generator so the
    app always keeps working (demo mode)."""
    if groq_service.configured:
        try:
            script = await groq_service.generate_script(
                idea=req.prompt,
                duration=req.duration,
                style=req.style,
                voice=req.voice,
                language=req.language,
                aspect_ratio=req.aspect_ratio,
            )
            return script, True
        except (GroqNotConfigured, GroqGenerationError) as exc:
            logger.warning("Groq generation failed (%s)", exc)
            if not USE_DEMO_MODE:
                raise
        except Exception as exc:  # network errors, rate limits, etc.
            logger.warning("Groq request error (%s)", exc)
            if not USE_DEMO_MODE:
                raise GroqGenerationError(str(exc))

    if not USE_DEMO_MODE:
        raise GroqNotConfigured(
            "GROQ_API_KEY is not configured and USE_DEMO_MODE is false."
        )

    script = scene_service.build_sample_script(
        req.prompt, req.duration, req.style, req.voice, req.language
    )
    return script, False


async def run_video_pipeline(job_id: str, req: VideoCreateRequest) -> None:
    try:
        _set_status(job_id, status="processing", stage="Understanding your idea", progress=5)

        video_id = new_id()
        img_dir = job_dir(video_id, "images")
        audio_dir = job_dir(video_id, "audio")
        video_dir = job_dir(video_id, "videos")
        sub_dir = job_dir(video_id, "subtitles")

        _set_status(job_id, stage="Writing the script", progress=10)
        script, used_groq = await _get_script(req)
        script = scene_service.reconcile_scene_durations(script)

        _set_status(job_id, stage="Planning scenes", progress=20)
        width, height = video_renderer.ASPECT_DIMENSIONS.get(
            req.aspect_ratio, video_renderer.ASPECT_DIMENSIONS["9:16"]
        )

        n_scenes = len(script.scenes)
        clip_paths = []

        for idx, scene in enumerate(script.scenes):
            base = 25 + int((idx / max(1, n_scenes)) * 55)
            _set_status(
                job_id,
                stage=f"Generating visuals - scene {idx + 1} of {n_scenes}",
                progress=base,
            )
            image_path = img_dir / f"scene_{scene.scene_number}.png"
            await image_service.generate_scene_image(scene.visual_prompt, image_path, width, height)
            scene.image_path = str(image_path)

            _set_status(
                job_id,
                stage=f"Creating voice-over - scene {idx + 1} of {n_scenes}",
                progress=base + 3,
            )
            audio_path = audio_dir / f"scene_{scene.scene_number}.wav"
            audio_path, _ = await tts_service.generate_narration_audio(
                scene.narration, audio_path, req.voice, req.language, scene.duration
            )
            scene.audio_path = str(audio_path)

            clip_path = video_dir / f"clip_{scene.scene_number}.mp4"
            actual_dur = await video_renderer.render_scene_clip(
                image_path, audio_path, clip_path, req.aspect_ratio,
                zoom_in=(idx % 2 == 0),
            )
            scene.duration = round(actual_dur, 2)
            scene.status = "ready"
            clip_paths.append(clip_path)

        srt_path = None
        if req.captions_enabled:
            _set_status(job_id, stage="Creating captions", progress=82)
            srt_path = sub_dir / "captions.srt"
            caption_service.write_srt(
                script.scenes, [s.duration for s in script.scenes], srt_path
            )

        _set_status(job_id, stage="Rendering video", progress=88)
        final_path = video_dir / "final.mp4"
        await video_renderer.render_final_video(
            clip_paths, srt_path, video_dir, final_path,
            add_music=req.background_music,
        )

        thumb_path = video_dir / "thumbnail.jpg"
        try:
            await video_renderer.make_thumbnail(final_path, thumb_path)
        except Exception:
            thumb_path = None

        _set_status(job_id, stage="Finalizing video", progress=97)

        record = VideoRecord(
            video_id=video_id,
            title=script.title,
            description=script.description,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            style=req.style,
            voice=req.voice,
            language=req.language,
            scenes=script.scenes,
            video_path=str(final_path),
            thumbnail_path=str(thumb_path) if thumb_path else None,
            status="completed",
        )
        VIDEOS[video_id] = record
        WORKSPACES[video_id] = {
            "clips": [str(p) for p in clip_paths],
            "srt_path": str(srt_path) if srt_path else None,
            "work_dir": str(video_dir),
            "request": req.model_dump(),
            "used_groq": used_groq,
        }

        _set_status(
            job_id, status="completed", stage="Video ready", progress=100,
            video_id=video_id,
            message="Generated with Groq" if used_groq else "Generated in demo mode",
        )

    except Exception as exc:
        logger.exception("Video pipeline failed")
        _set_status(
            job_id, status="failed", stage="Failed", progress=0,
            error=_friendly_error(exc),
        )


async def regenerate_single_scene(
    video_id: str, scene_number: int, overrides: dict
) -> VideoRecord:
    record = VIDEOS.get(video_id)
    workspace = WORKSPACES.get(video_id)
    if not record or not workspace:
        raise ValueError("Video not found")

    scene: Optional[Scene] = next(
        (s for s in record.scenes if s.scene_number == scene_number), None
    )
    if not scene:
        raise ValueError("Scene not found")

    if overrides.get("visual_prompt"):
        scene.visual_prompt = overrides["visual_prompt"]
    if overrides.get("narration"):
        scene.narration = overrides["narration"]

    req = VideoCreateRequest(**{**workspace["request"]})
    width, height = video_renderer.ASPECT_DIMENSIONS.get(
        record.aspect_ratio, video_renderer.ASPECT_DIMENSIONS["9:16"]
    )
    video_id_dir_img = job_dir(video_id, "images")
    video_id_dir_audio = job_dir(video_id, "audio")
    video_id_dir_video = job_dir(video_id, "videos")

    image_path = video_id_dir_img / f"scene_{scene.scene_number}.png"
    await image_service.generate_scene_image(scene.visual_prompt, image_path, width, height)
    scene.image_path = str(image_path)

    audio_path = video_id_dir_audio / f"scene_{scene.scene_number}.wav"
    audio_path, _ = await tts_service.generate_narration_audio(
        scene.narration, audio_path, record.voice, record.language, scene.duration
    )
    scene.audio_path = str(audio_path)

    clip_path = video_id_dir_video / f"clip_{scene.scene_number}.mp4"
    actual_dur = await video_renderer.render_scene_clip(
        image_path, audio_path, clip_path, record.aspect_ratio
    )
    scene.duration = round(actual_dur, 2)

    srt_path = None
    if workspace.get("srt_path") or req.captions_enabled:
        sub_dir = job_dir(video_id, "subtitles")
        srt_path = sub_dir / "captions.srt"
        caption_service.write_srt(
            record.scenes, [s.duration for s in record.scenes], srt_path
        )
        workspace["srt_path"] = str(srt_path)

    clip_paths = [Path(p) for p in workspace["clips"]]
    final_path = Path(workspace["work_dir"]) / "final.mp4"
    await video_renderer.render_final_video(
        clip_paths,
        Path(workspace["srt_path"]) if workspace.get("srt_path") else None,
        Path(workspace["work_dir"]),
        final_path,
        add_music=req.background_music,
    )
    record.video_path = str(final_path)
    return record


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    if "GROQ_API_KEY" in text or isinstance(exc, GroqNotConfigured):
        return "The AI script generator isn't configured. Add a GROQ_API_KEY or enable demo mode."
    if "ffmpeg" in text.lower() or "ffprobe" in text.lower():
        return "Video rendering is temporarily unavailable. Please try again."
    if "rate limit" in text.lower():
        return "The AI provider is rate limited right now. Please try again shortly."
    return "Video generation is temporarily unavailable. Please try again."
