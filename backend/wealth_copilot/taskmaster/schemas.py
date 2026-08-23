"""Auditable TaskMaster operator-cycle contracts."""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TaskmasterModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TaskmasterDecision(StrEnum):
    INTERRUPT_NOW = "INTERRUPT_NOW"
    MONITOR = "MONITOR"
    RESEARCH_FIRST = "RESEARCH_FIRST"
    DEFER_TO_EVENING = "DEFER_TO_EVENING"
    ASK_USER = "ASK_USER"
    PREPARE_ADVISOR_HANDOFF = "PREPARE_ADVISOR_HANDOFF"
    CARRY_TO_TOMORROW = "CARRY_TO_TOMORROW"
    CLOSE_CASE = "CLOSE_CASE"


class OperatorCycle(TaskmasterModel):
    cycle_id: str
    subject_id: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observations: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    delegated_to: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    decision: TaskmasterDecision
    reason: str
    follow_up_at: datetime | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
