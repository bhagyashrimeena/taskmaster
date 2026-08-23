"""Canonical active financial-day identity and derived attention state."""

from datetime import datetime
from enum import StrEnum
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


class AttentionDisposition(StrEnum):
    INTERRUPTED = "interrupted"
    DEFERRED = "deferred"
    MONITORED = "monitored"
    IGNORED = "ignored"


class AttentionBudget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    interrupt_limit: int = Field(default=3, ge=1)
    signals_processed: int = Field(default=0, ge=0)
    interrupted: int = Field(default=0, ge=0)
    deferred: int = Field(default=0, ge=0)
    monitored: int = Field(default=0, ge=0)
    ignored: int = Field(default=0, ge=0)

    def record(self, disposition: AttentionDisposition) -> None:
        self.signals_processed += 1
        if disposition == AttentionDisposition.INTERRUPTED:
            self.interrupted += 1
        elif disposition == AttentionDisposition.DEFERRED:
            self.deferred += 1
        elif disposition == AttentionDisposition.MONITORED:
            self.monitored += 1
        else:
            self.ignored += 1


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
