"""Focused REST and event-stream contracts for the product frontend."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..cases.schemas import FinancialCase, FinancialCasePriority, FinancialCaseStatus
from ..dashboard.schemas import DailyBriefView, PortfolioView
from ..day.schemas import DayRunMode, DayStatus, DayTimelineStep, FinancialDayState
from ..events.schemas import EventAssessment, EventDecision
from ..interaction.schemas import DailyInteractionView
from ..market_data.schemas import IndexQuote, IntradayPoint, SectorSnapshot


class ProductModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AttentionItemKind(StrEnum):
    EVENT = "event"
    STORY = "story"


class AttentionItem(ProductModel):
    item_id: str
    kind: AttentionItemKind
    priority: str
    title: str
    summary: str
    relevance_score: float
    direct_exposure_pct: float = 0
    sector_exposure_pct: float = 0
    status: str
    occurred_at: datetime
    actions: list[str] = Field(default_factory=list)


class TodayResponse(ProductModel):
    day_id: str
    run_id: str
    trading_date: date
    generated_at: datetime
    greeting: str
    attention_count: int = Field(ge=0)
    attention_message: str
    attention_items: list[AttentionItem] = Field(default_factory=list)
    portfolio: PortfolioView
    daily_brief: DailyBriefView
    recent_timeline: list[DayTimelineStep] = Field(default_factory=list)
    next_checkpoint: DayTimelineStep | None = None
    morning_brief_id: str | None = None
    evening_brief_id: str | None = None
    daily_state: DailyInteractionView
    disclaimer: str


class PortfolioResponse(ProductModel):
    day_id: str
    run_id: str
    generated_at: datetime
    portfolio: PortfolioView


class AlertCategory(StrEnum):
    ATTENTION = "attention"
    INVESTIGATING = "investigating"
    MONITORING = "monitoring"
    IGNORED = "ignored"


class AlertInboxItem(ProductModel):
    case_id: str | None = None
    event_id: str
    instrument: str | None = None
    company: str | None = None
    headline: str
    occurred_at: datetime
    updated_at: datetime
    category: AlertCategory
    status: str
    priority: FinancialCasePriority
    decision: EventDecision
    notification_required: bool
    price_change_pct: float | None = None
    sector_change_pct: float | None = None
    index_change_pct: float | None = None
    direct_exposure_pct: float = 0
    sector_exposure_pct: float = 0
    portfolio_impact_pct: float | None = None
    relevance_score: float = 0
    reason: str


class AlertInboxResponse(ProductModel):
    day_id: str
    run_id: str
    generated_at: datetime
    counts: dict[AlertCategory, int]
    items: list[AlertInboxItem] = Field(default_factory=list)


class AlertDetailResponse(ProductModel):
    day_id: str
    run_id: str
    generated_at: datetime
    case: FinancialCase
    assessment: EventAssessment | None = None
    item: AlertInboxItem
    intraday: list[IntradayPoint] = Field(default_factory=list)
    benchmark: IndexQuote | None = None
    sector: SectorSnapshot | None = None


class TimelineResponse(ProductModel):
    day_id: str
    run_id: str
    trading_date: date
    generated_at: datetime
    status: DayStatus
    run_mode: DayRunMode
    completed_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    active_step_id: str | None = None
    next_checkpoint: DayTimelineStep | None = None
    timeline: list[DayTimelineStep]
    financial_day: FinancialDayState


class CopilotBootstrapResponse(ProductModel):
    day_id: str
    run_id: str
    generated_at: datetime
    conversation_id: str | None = None
    context_summary: str
    suggested_questions: list[str]
    holdings_count: int = Field(ge=0)
    relevant_story_count: int = Field(ge=0)
    active_case_count: int = Field(ge=0)
    saved_story_count: int = Field(ge=0)
    saved_event_count: int = Field(ge=0)
    voice_call_enabled: bool = False
    voice_call_reason: str | None = None


class ProductEventType(StrEnum):
    SNAPSHOT = "SNAPSHOT"
    EVENT_ALERT_CREATED = "EVENT_ALERT_CREATED"
    FINANCIAL_CASE_UPDATED = "FINANCIAL_CASE_UPDATED"
    CHECKPOINT_COMPLETED = "CHECKPOINT_COMPLETED"
    AUDIO_READY = "AUDIO_READY"


class ProductEvent(ProductModel):
    event_type: ProductEventType
    emitted_at: datetime
    day_id: str
    run_id: str
    entity_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


class StreamSnapshot(ProductModel):
    day_id: str
    run_id: str
    status: DayStatus
    completed_steps: list[str]
    case_versions: dict[str, datetime]
    alert_event_ids: list[str]
    ready_audio_ids: list[str]
