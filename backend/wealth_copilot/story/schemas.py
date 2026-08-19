"""Stable contracts for the visual recap of one financial day."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from ..day.active import ArtifactProvenance


class StoryModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class WealthStoryStatus(StrEnum):
    READY = "ready"


class StoryNarrationStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FALLBACK = "fallback"


class StorySceneKind(StrEnum):
    SUMMARY = "summary"
    DRIVER = "driver"
    ALERT = "alert"
    QUIET = "quiet"
    SAVED = "saved"
    ADVISOR = "advisor"
    TOMORROW = "tomorrow"


class StoryContributor(StoryModel):
    symbol: str
    portfolio_weight_pct: float
    daily_return_pct: float
    contribution_percentage_points: float
    direction: str


class StoryEvent(StoryModel):
    event_id: str
    company: str
    price_change_pct: float
    sector_change_pct: float
    exposure_pct: float
    relevance_score: float
    alert_time: datetime


class StoryAdvisorInteraction(StoryModel):
    request_id: str
    question: str
    response_id: str | None = None
    response_summary: str | None = None
    advisor_name: str | None = None


class StoryTomorrowEvent(StoryModel):
    event_id: str
    title: str
    scheduled_at: datetime
    portfolio_exposure_pct: float


class StoryScene(StoryModel):
    scene_id: str
    order: int = Field(ge=1)
    kind: StorySceneKind
    duration_seconds: int = Field(ge=3, le=10)
    eyebrow: str
    title: str
    primary_value: str | None = None
    secondary_text: str | None = None
    detail: str | None = None


class StorySceneNarration(StoryModel):
    scene_id: str
    text: str
    status: StoryNarrationStatus
    audio_url: str | None = None
    actual_duration_seconds: float | None = Field(default=None, ge=0)


class StoryNarration(StoryModel):
    story_id: str
    day_id: str
    run_id: str
    status: StoryNarrationStatus
    scenes: list[StorySceneNarration]
    total_duration_seconds: float | None = Field(default=None, ge=0)
    muted: bool = False
    message: str


class DailyWealthStory(StoryModel):
    story_id: str
    day_id: str
    run_id: str
    trading_date: date
    generated_at: datetime
    source_signature: str
    portfolio_open: float | None = None
    portfolio_close: float | None = None
    portfolio_change_pct: float | None = None
    top_positive_contributors: list[StoryContributor] = Field(default_factory=list)
    top_negative_contributors: list[StoryContributor] = Field(default_factory=list)
    important_event: StoryEvent | None = None
    saved_items: list[str] = Field(default_factory=list)
    advisor_interaction: StoryAdvisorInteraction | None = None
    tomorrow_events: list[StoryTomorrowEvent] = Field(default_factory=list)
    scenes: list[StoryScene]
    audio_brief_id: str | None = None
    duration_seconds: int = Field(ge=20, le=30)
    status: WealthStoryStatus = WealthStoryStatus.READY
    cached: bool = False
    provenance: ArtifactProvenance | None = None
