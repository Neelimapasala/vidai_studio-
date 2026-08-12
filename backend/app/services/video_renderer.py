import asyncio
import logging
import subprocess
import wave
from pathlib import Path
from typing import List, Optional

from app.utils.ffmpeg import ffmpeg_executable, ffprobe_executable

logger = logging.getLogger("vidai.render")

ASPECT_DIMENSIONS = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (720, 720),
}

FPS = 25


class RenderError(Exception):
    pass


async def _run(cmd: List[str]) -> None:
    logger.info("ffmpeg: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RenderError(stderr.decode(errors="ignore")[-4000:])


async def get_audio_duration(path: Path) -> float:
    ffprobe = ffprobe_executable()
    if ffprobe:
        proc = await asyncio.create_subprocess_exec(
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        try:
            return max(0.5, float(out.decode().strip()))
        except Exception:
            pass

    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return max(0.5, frames / float(rate))
    except Exception:
        return 1.0


async def render_scene_clip(
    image_path: Path,
    audio_path: Path,
    out_path: Path,
    aspect_ratio: str,
    zoom_in: bool = True,
) -> float:
    """Render one Ken Burns scene clip (image + narration audio) and return
    its actual duration in seconds."""
    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, ASPECT_DIMENSIONS["9:16"])
    duration = await get_audio_duration(audio_path)
    frames = max(1, int(duration * FPS))

    zoom_expr = (
        "min(zoom+0.0012,1.4)" if zoom_in else "if(lte(zoom,1.0),1.4,max(1.0,zoom-0.0012))"
    )
    fade_dur = min(0.4, duration / 4)
    fade_out_start = max(0, duration - fade_dur)

    vf = (
        f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
        f"zoompan=z='{zoom_expr}':d={frames}:s={width}x{height}:fps={FPS},"
        f"fade=t=in:st=0:d={fade_dur},fade=t=out:st={fade_out_start}:d={fade_dur}"
    )
    af = f"afade=t=in:st=0:d=0.15,afade=t=out:st={max(0, duration-0.15)}:d=0.15"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_executable(), "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        "-af", af,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-r", str(FPS),
        str(out_path),
    ]
    await _run(cmd)
    return duration


async def concat_clips(clip_paths: List[Path], out_path: Path) -> None:
    list_file = out_path.parent / f"{out_path.stem}_concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clip_paths), encoding="utf-8"
    )
    cmd = [
        ffmpeg_executable(), "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(out_path),
    ]
    await _run(cmd)


async def _ensure_ambient_pad(cache_path: Path) -> Path:
    """Render a short looping ambient pad (soft triad + slow tremolo) once,
    used as a royalty-free background-music fallback with no external assets."""
    if cache_path.exists():
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_executable(), "-y",
        "-f", "lavfi", "-i", "sine=frequency=196:sample_rate=44100:duration=8",
        "-f", "lavfi", "-i", "sine=frequency=246.94:sample_rate=44100:duration=8",
        "-f", "lavfi", "-i", "sine=frequency=293.66:sample_rate=44100:duration=8",
        "-filter_complex",
        "[0:a][1:a][2:a]amix=inputs=3:duration=longest,"
        "tremolo=f=0.15:d=0.3,volume=0.5,afade=t=in:st=0:d=1.5,afade=t=out:st=6.5:d=1.5[aout]",
        "-map", "[aout]", "-t", "8", str(cache_path),
    ]
    await _run(cmd)
    return cache_path


def _subtitles_filter(srt_path: Path) -> Optional[str]:
    if not srt_path or not srt_path.exists():
        return None
    escaped = (
        srt_path.resolve().as_posix()
        .replace(":", r"\:")
        .replace("'", r"\'")
    )
    return (
        "subtitles=filename='%s':force_style="
        "'FontName=DejaVu Sans,FontSize=13,PrimaryColour=&HFFFFFF&,"
        "OutlineColour=&H000000&,BorderStyle=3,Outline=1,Shadow=0,"
        "Alignment=2,MarginV=60'" % escaped
    )


async def burn_subtitles_and_music(
    video_in: Path,
    srt_path: Optional[Path],
    out_path: Path,
    add_music: bool = False,
) -> None:
    subtitles = _subtitles_filter(srt_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_executable(), "-y", "-i", str(video_in)]

    if add_music:
        music_path = await _ensure_ambient_pad(out_path.parent.parent / "_ambient_pad.wav")
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]

    if subtitles:
        cmd += ["-vf", subtitles]

    if add_music:
        cmd += [
            "-filter_complex",
            "[0:a]volume=1.0[a0];[1:a]volume=0.12[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "0:v", "-map", "[aout]",
        ]

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out_path),
    ]

    try:
        await _run(cmd)
    except RenderError as exc:
        if subtitles:
            logger.warning("Subtitles burn failed; retrying without captions: %s", exc)
            cmd = [ffmpeg_executable(), "-y", "-i", str(video_in)]
            if add_music:
                music_path = await _ensure_ambient_pad(out_path.parent.parent / "_ambient_pad.wav")
                cmd += ["-stream_loop", "-1", "-i", str(music_path)]
                cmd += [
                    "-filter_complex",
                    "[0:a]volume=1.0[a0];[1:a]volume=0.12[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]",
                    "-map", "0:v", "-map", "[aout]",
                ]
            cmd += [
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(out_path),
            ]
            await _run(cmd)
        else:
            raise


async def render_final_video(
    scene_clip_paths: List[Path],
    srt_path: Optional[Path],
    work_dir: Path,
    final_path: Path,
    add_music: bool = False,
) -> Path:
    concatenated = work_dir / "concatenated.mp4"
    await concat_clips(scene_clip_paths, concatenated)
    await burn_subtitles_and_music(concatenated, srt_path, final_path, add_music=add_music)
    return final_path


async def make_thumbnail(video_path: Path, out_path: Path) -> Path:
    cmd = [
        ffmpeg_executable(), "-y", "-i", str(video_path),
        "-ss", "00:00:00.5", "-frames:v", "1", str(out_path),
    ]
    await _run(cmd)
    return out_path


async def render_demo_video(
    image_path: Path,
    out_path: Path,
    duration: float = 10.0,
) -> Path:
    audio_path = out_path.parent / "demo_silent.wav"
    _make_silent_audio(audio_path, duration)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_executable(), "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration),
        "-shortest",
        str(out_path),
    ]
    await _run(cmd)
    return out_path
