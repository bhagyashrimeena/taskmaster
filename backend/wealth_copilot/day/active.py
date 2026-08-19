"""Canonical active financial-day identity and derived attention state."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArtifactProvenance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day_id: str
    run_id: str
    source_checkpoint: str
    source_snapshot_id: str
    generated_at: datetime


class AttentionSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    high_priority_count: int = Field(ge=0)
    portfolio_relevant_story_count: int = Field(ge=0)
    active_event_count: int = Field(ge=0)
    story_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)


class ActiveFinancialDay(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day_id: str
    run_id: str
    mode: Literal["idle", "demo", "presentation", "real"]
    presentation_time: str | None
    current_checkpoint: str | None
    started_at: datetime | None
    status: str
    attention_summary: AttentionSummary = Field(default_factory=lambda: AttentionSummary(
        high_priority_count=0,
        portfolio_relevant_story_count=0,
        active_event_count=0,
    ))
