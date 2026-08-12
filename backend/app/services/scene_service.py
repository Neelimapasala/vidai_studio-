from app.models.scene import Scene
from app.models.video import VideoScript


def build_sample_script(
    idea: str, duration: int, style: str, voice: str, language: str
) -> VideoScript:
    """Deterministic offline fallback used when Groq is not configured or
    fails, so the app is always runnable (demo mode)."""

    beats = [
        (
            "Every idea starts with a single spark of curiosity.",
            f"A close-up of glowing particles forming a spark of light, {style.lower()} style, dramatic lighting",
            "IT ALL STARTS WITH AN IDEA",
        ),
        (
            f"Today we're exploring {idea.strip().rstrip('.')}.",
            f"Wide establishing shot representing '{idea}', {style.lower()} style, cinematic composition",
            "LET'S DIVE IN",
        ),
        (
            "Step by step, the pieces begin to connect.",
            f"Abstract network of connected nodes and pathways lighting up, {style.lower()} style",
            "CONNECTING THE DOTS",
        ),
        (
            "What seemed complex starts to feel simple and clear.",
            f"A clean, bright scene symbolizing clarity and understanding, {style.lower()} style",
            "IT ALL MAKES SENSE NOW",
        ),
        (
            "And that's the bigger picture, brought to life.",
            f"A confident, wide hero shot summarizing the concept, {style.lower()} style, golden hour lighting",
            "THE BIGGER PICTURE",
        ),
        (
            "Thanks for watching — now you know how it works.",
            f"An inspiring closing shot with soft light and clear focus, {style.lower()} style",
            "NOW YOU KNOW",
        ),
    ]

    scene_count = max(3, min(len(beats), round(duration / 5)))
    chosen = beats[:scene_count]
    per_scene = round(duration / scene_count, 1)

    scenes = []
    remaining = duration
    for i, (narration, visual_prompt, caption) in enumerate(chosen, start=1):
        is_last = i == len(chosen)
        d = round(remaining, 1) if is_last else per_scene
        remaining -= d
        scenes.append(
            Scene(
                scene_number=i,
                duration=max(1.5, d),
                narration=narration,
                visual_prompt=visual_prompt,
                caption=caption,
                transition="fade",
                media_type="image",
            )
        )

    return VideoScript(
        title=idea.strip()[:60] or "Untitled AI Video",
        description=f"An AI-generated {style.lower()} video about: {idea.strip()}",
        duration=duration,
        scenes=scenes,
    )


def reconcile_scene_durations(script: VideoScript) -> VideoScript:
    """Make sure scene durations sum to the requested total duration."""
    total = sum(s.duration for s in script.scenes)
    if total <= 0:
        return script
    factor = script.duration / total
    for s in script.scenes:
        s.duration = round(max(1.5, s.duration * factor), 2)
    return script
