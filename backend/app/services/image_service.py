import hashlib
import logging
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.providers.base_image_provider import BaseImageProvider

logger = logging.getLogger("vidai.image")

IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "").strip()

# Style -> gradient color palettes (start, end) + accent
STYLE_PALETTES = {
    "cinematic": [((10, 12, 26), (58, 22, 74)), ((20, 8, 30), (120, 30, 60))],
    "realistic": [((15, 20, 25), (55, 65, 75)), ((25, 30, 35), (90, 95, 100))],
    "3d": [((8, 24, 40), (30, 90, 160)), ((10, 30, 50), (60, 130, 200))],
    "anime": [((30, 10, 50), (255, 90, 150)), ((10, 20, 60), (255, 160, 60))],
    "minimal": [((245, 245, 245), (225, 225, 230)), ((250, 248, 245), (230, 225, 220))],
    "corporate": [((12, 24, 48), (24, 60, 110)), ((18, 20, 40), (40, 80, 130))],
    "educational": [((10, 40, 40), (20, 100, 90)), ((15, 30, 55), (30, 110, 130))],
    "documentary": [((20, 18, 15), (70, 60, 45)), ((15, 15, 15), (65, 60, 55))],
}


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class FallbackImageProvider(BaseImageProvider):
    """No-API-key-required generator: a stylized gradient card with the
    scene's visual concept rendered as clean typography + soft shapes.
    Deterministic per-prompt so repeated scenes look consistent."""

    async def generate_image(
        self, prompt: str, out_path: Path, width: int, height: int
    ) -> Path:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        style_key = "cinematic"
        for key in STYLE_PALETTES:
            if key in prompt.lower():
                style_key = key
                break
        palette_options = STYLE_PALETTES[style_key]
        start, end = palette_options[seed % len(palette_options)]

        img = Image.new("RGB", (width, height), start)
        draw = ImageDraw.Draw(img)

        # vertical gradient
        for y in range(height):
            t = y / max(1, height - 1)
            r = int(start[0] + (end[0] - start[0]) * t)
            g = int(start[1] + (end[1] - start[1]) * t)
            b = int(start[2] + (end[2] - start[2]) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # soft decorative circles for depth
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        for i in range(3):
            cx = (seed >> (i * 8)) % width
            cy = (seed >> (i * 8 + 4)) % height
            radius = min(width, height) // (2 + i)
            odraw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=(255, 255, 255, 14),
            )
        overlay = overlay.filter(ImageFilter.GaussianBlur(60))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # subtle vignette
        vignette = Image.new("L", (width, height), 0)
        vdraw = ImageDraw.Draw(vignette)
        vdraw.ellipse([-width * 0.3, -height * 0.3, width * 1.3, height * 1.3], fill=255)
        vignette = vignette.filter(ImageFilter.GaussianBlur(120))
        dark = Image.new("RGB", (width, height), (0, 0, 0))
        img = Image.composite(img, dark, vignette)
        draw = ImageDraw.Draw(img)

        # render a short concept label extracted from the prompt, wrapped to
        # fit within a safe margin using actual measured text width
        concept = prompt.split(",")[0].strip()[:90]
        font_size = max(26, width // 18)
        font = _load_font(font_size)
        max_line_width = width * 0.82

        words = concept.split()
        wrapped: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_line_width or not current:
                current = candidate
            else:
                wrapped.append(current)
                current = word
        if current:
            wrapped.append(current)
        wrapped = wrapped[:4]

        total_h = len(wrapped) * (font_size + 14)
        y = (height - total_h) // 2
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) // 2, y),
                line,
                font=font,
                fill=(255, 255, 255),
            )
            y += font_size + 14

        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, quality=92)
        return out_path


fallback_image_provider = FallbackImageProvider()


async def generate_scene_image(prompt: str, out_path: Path, width: int, height: int) -> Path:
    """Entry point used by the orchestrator. Uses a real provider automatically
    once IMAGE_API_KEY + a provider implementation are wired in; otherwise
    uses the built-in fallback so the app always works."""
    if IMAGE_API_KEY:
        # Placeholder for a real provider integration (Stability, Replicate, etc).
        # Implement BaseImageProvider and swap it in here when you have a key.
        logger.info("IMAGE_API_KEY set but no real provider wired in - using fallback")
    return await fallback_image_provider.generate_image(prompt, out_path, width, height)
