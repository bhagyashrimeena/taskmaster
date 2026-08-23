"""Stable contracts for contextual Explain, Research, and chat."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InteractionModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class InteractionMode(StrEnum):
    EXPLAIN = "explain"
    CHAT = "chat"
    TEXT = "text"
    VOICE = "voice"
    CALL = "call"
    RESEARCH = "research"


class ResearchStatus(StrEnum):
    QUEUED = "queued"
    RESEARCHING = "researching"
    COMPLETE = "complete"
    FALLBACK = "fallback"
    FAILED = "failed"


class SourceReference(InteractionModel):
    name: str
    url: str
    authority: str
    kind: str
    title: str | None = None
    publisher: str | None = None
    citation_uri: str | None = None
    canonical_url: str | None = None
    retrieved_at: datetime | None = None


class SurfaceContext(InteractionModel):
    day_id: str | None = None
    run_id: str | None = None
    target_type: str
    target_id: str | None = None
    title: str
    portfolio_as_of: datetime
    source_checkpoint: str
    facts: list[str]
    interpretation: list[str]
    unknowns: list[str]
    sources: list[SourceReference]
    portfolio_context: str


class ConversationRequest(InteractionModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=1200)
    mode: InteractionMode = InteractionMode.CHAT
    active_story_id: str | None = None
    active_event_id: str | None = None
    voice_context: Any | None = None


class ConversationResponse(InteractionModel):
    conversation_id: str
    message_id: str
    mode: InteractionMode
    route: str
    answer: str
    context: SurfaceContext
    sources: list[SourceReference]
    suggested_questions: list[str]
    used_search: bool
    used_existing_context: bool
    used_long_term_memory: bool = False
    memory_signals: list[str] = Field(default_factory=list)
    fallback_used: bool
    agent_trace: list[str]
    created_at: datetime


class ResearchRequest(InteractionModel):
    conversation_id: str | None = None
    message: str = "Research this more deeply."
    active_story_id: str | None = None
    active_event_id: str | None = None


class ResearchJob(InteractionModel):
    job_id: str
    status: ResearchStatus
    message: str
    result: ConversationResponse | None = None
    created_at: datetime
    completed_at: datetime | None = None


class SaveStoryResponse(InteractionModel):
    story_id: str
    saved: bool
    saved_for: date


class FeedbackRequest(InteractionModel):
    target_type: str
    target_id: str
    value: str
    conversation_id: str | None = None


class FeedbackResponse(InteractionModel):
    recorded: bool
    target_type: str
    target_id: str
    value: str


class DailyInteractionView(InteractionModel):
    trading_date: date
    saved_story_ids: list[str] = Field(default_factory=list)
    saved_event_ids: list[str] = Field(default_factory=list)
    feedback: dict[str, str] = Field(default_factory=dict)
