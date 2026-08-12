WORDS_PER_SECOND = 2.4  # ~144 wpm natural narration pace


def target_word_count(duration_seconds: int) -> tuple[int, int]:
    center = int(duration_seconds * WORDS_PER_SECOND)
    return max(10, int(center * 0.85)), int(center * 1.15)


def build_script_system_prompt() -> str:
    return (
        "You are an expert short-form video scriptwriter and scene planner for "
        "an AI video generation tool. You ALWAYS respond with a single valid "
        "JSON object and nothing else - no markdown fences, no commentary, no "
        "explanations before or after the JSON. The JSON must exactly match "
        "the schema you are given. Every string field must be plain text with "
        "no markdown formatting."
    )


def build_script_user_prompt(
    idea: str,
    duration: int,
    style: str,
    voice: str,
    language: str,
    aspect_ratio: str,
) -> str:
    lo, hi = target_word_count(duration)
    scene_count_hint = max(3, min(8, round(duration / 5)))

    return f"""Create a complete video script and scene breakdown for the idea below.

VIDEO IDEA: "{idea}"

REQUIREMENTS:
- Total spoken narration duration: {duration} seconds
- Total narration word count: between {lo} and {hi} words
- Visual style: {style}
- Voice tone: {voice}
- Narration language: {language}
- Aspect ratio: {aspect_ratio}
- Number of scenes: approximately {scene_count_hint} (divide duration evenly, each scene 3-8 seconds)
- Strong opening hook in scene 1
- Logical progression between scenes
- Clear, satisfying ending in the last scene
- Narration must sound natural when read aloud by a voice-over artist
- Each scene's "visual_prompt" must be a vivid, specific, self-contained
  description suitable for an AI image generator (mention subject, action,
  lighting, mood, and the "{style}" style)
- Each scene's "caption" is a short on-screen text overlay (max 8 words, ALL CAPS)
- "transition" must be one of: fade, cut, slide, zoom
- "media_type" must be "image"
- The sum of all scene "duration" values must equal {duration}

Respond ONLY with a JSON object matching exactly this schema:

{{
  "title": "string, short catchy title",
  "description": "string, one sentence description",
  "duration": {duration},
  "scenes": [
    {{
      "scene_number": 1,
      "duration": 5,
      "narration": "string",
      "visual_prompt": "string",
      "caption": "string",
      "transition": "fade",
      "media_type": "image"
    }}
  ]
}}
"""


def build_repair_prompt(broken_json: str, error: str) -> str:
    return f"""The following text was supposed to be valid JSON but failed to
parse or validate with this error:

ERROR: {error}

TEXT:
{broken_json}

Fix it and respond with ONLY the corrected, valid JSON object. No markdown
fences, no commentary."""
