"""Stable frontend contract for the Phase 3 dashboard."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..events.schemas import EventAssessment
from ..interaction.schemas import DailyInteractionView
from ..day.active import ArtifactProvenance, AttentionSummary


class DashboardModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FreshnessStatus(StrEnum):
    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"


class RefreshPhase(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class DataSource(DashboardModel):
    label: str
    is_live: bool
    provider: str
    scenario_id: str | None = None
    checkpoint: str | None = None


class HoldingView(DashboardModel):
    symbol: str
    name: str | None = None
    asset_class: str | None = None
    quantity: float | None = None
    average_price: float | None = None
    current_price: float | None = None
    market_value: float
    unrealized_pnl: float | None = None
    day_pnl: float | None = None
    portfolio_weight: float
    day_change_pct: float | None = None


class SectorView(DashboardModel):
    sector: str
    portfolio_weight: float


class AllocationView(DashboardModel):
    label: str
    portfolio_weight: float
    market_value: float


class PerformanceView(DashboardModel):
    period: str
    portfolio_return_pct: float
    benchmark_return_pct: float | None = None
    benchmark_label: str | None = None


class PortfolioView(DashboardModel):
    source: DataSource
    as_of: datetime
    currency: str
    portfolio_value: float
    invested_value: float
    unrealized_pnl: float
    day_pnl: float | None = None
    day_change_pct: float | None = None
    overall_return_pct: float | None = None
    equity_exposure_pct: float | None = None
    defensive_exposure_pct: float | None = None
    risk_profile: str | None = None
    holdings_count: int
    largest_holdings: list[HoldingView]
    sector_exposure: list[SectorView]
    asset_allocation: list[AllocationView] = Field(default_factory=list)
    performance: list[PerformanceView] = Field(default_factory=list)


class FreshnessView(DashboardModel):
    status: FreshnessStatus
    label: str
    fetched_at: datetime
    cache_age_seconds: float = Field(ge=0)
    refresh_attempted: bool


class StoryView(DashboardModel):
    id: str
    headline: str
    summary: str
    source_name: str
    source_url: str
    canonical_url: str | None = None
    canonical_url_status: str = "unavailable"
    published_at: datetime
    affected_holdings: list[str]
    direct_exposure_pct: float
    sector_exposure_pct: float
    relevance_score: float
    final_utility_score: float
    source_authority: str
    why_am_i_seeing_this: str
    actions: list[str] = Field(default_factory=lambda: ["explain", "learn_more", "save"])


class DailyBriefView(DashboardModel):
    day_id: str
    run_id: str
    freshness: FreshnessView
    candidate_count: int
    analyzed_count: int
    stories: list[StoryView]
    provenance: ArtifactProvenance | None = None


class ActivityItem(DashboardModel):
    stage: str
    label: str
    status: str
    detail: str


class RefreshView(DashboardModel):
    refresh_id: str | None = None
    phase: RefreshPhase = RefreshPhase.IDLE
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str = "Market intelligence is up to date."


class DashboardResponse(DashboardModel):
    day_id: str
    run_id: str
    generated_at: datetime
    greeting: str
    attention_count: int = Field(ge=0)
    attention_summary: AttentionSummary
    attention_message: str
    portfolio: PortfolioView
    daily_brief: DailyBriefView
    important_event: EventAssessment | None = None
    today_events: list[EventAssessment]
    agent_activity: list[ActivityItem]
    refresh: RefreshView
    daily_state: DailyInteractionView
    disclaimer: str


class EventActionRequest(DashboardModel):
    action: str


class EventActionResponse(DashboardModel):
    status: str
    event_id: str
    action: str
    saved: bool
