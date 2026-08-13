"""Model discovery schemas (OpenAI /v1/models compatible)."""

from typing import List, Optional

from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "nvidia"
    created: Optional[int] = None
    loaded: bool
    profile: Optional[str] = None
    precision: Optional[str] = None
    device: Optional[str] = None
    revision: Optional[str] = None
    languages: Optional[List[str]] = None
    voices: Optional[List[str]] = None


class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelInfo]
