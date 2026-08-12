from typing import Literal, Optional
from pydantic import BaseModel, Field


class Scene(BaseModel):
    scene_number: int
    duration: float = Field(gt=0, le=30)
    narration: str
    visual_prompt: str
    caption: str
    transition: Literal["fade", "cut", "slide", "zoom"] = "fade"
    media_type: Literal["image", "video"] = "image"
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    status: Literal["pending", "ready", "failed"] = "pending"


class SceneRegenerateRequest(BaseModel):
    visual_prompt: Optional[str] = None
    narration: Optional[str] = None
    duration: Optional[float] = None
