"""Contracts for cached morning and evening audio briefs."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from ..day.active import ArtifactProvenance


class MediaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AudioBriefType(StrEnum):
    MORNING = "morning"
    EVENING = "evening"
    STORY = "story"


class AudioStatus(StrEnum):
    TEXT_READY = "text_ready"
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FALLBACK = "fallback"


class AudioSection(MediaModel):
    title: str
    text: str


class AudioBrief(MediaModel):
    brief_id: str
    day_id: str | None = None
    run_id: str | None = None
    type: AudioBriefType
    title: str
    generated_at: datetime
    source_snapshot_at: datetime
    sections: list[AudioSection]
    script: str
    duration_target_seconds: int = Field(ge=20, le=180)
    estimated_duration_seconds: int = Field(ge=1)
    actual_duration_seconds: float | None = Field(default=None, ge=0)
    voice: str
    model: str
    status: AudioStatus
    audio_url: str | None = None
    fallback_text: str
    data_freshness: str
    used_stories: list[str] = Field(default_factory=list)
    used_events: list[str] = Field(default_factory=list)
    cached: bool = False
    message: str
    provenance: ArtifactProvenance | None = None


class AudioGenerationResponse(MediaModel):
    brief: AudioBrief
    accepted: bool
