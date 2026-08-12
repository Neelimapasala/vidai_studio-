from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.models.scene import Scene


class VideoScript(BaseModel):
    """Structured output expected from Groq."""
    title: str
    description: str
    duration: int
    scenes: List[Scene]


class VideoCreateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=800)
    duration: Literal[15, 30, 60, 90] = 30
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    style: Literal[
        "Cinematic", "Realistic", "3D", "Anime",
        "Minimal", "Corporate", "Educational", "Documentary",
    ] = "Cinematic"
    voice: Literal["Male", "Female", "Neutral"] = "Neutral"
    language: Literal["English", "Telugu", "Hindi"] = "English"
    captions_enabled: bool = True
    background_music: bool = False


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    stage: str = "queued"
    progress: int = 0
    message: Optional[str] = None
    video_id: Optional[str] = None
    error: Optional[str] = None


class VideoRecord(BaseModel):
    video_id: str
    title: str
    description: str
    duration: int
    aspect_ratio: str
    style: str
    voice: str
    language: str
    scenes: List[Scene]
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    status: Literal["draft", "rendering", "completed", "failed"] = "draft"
