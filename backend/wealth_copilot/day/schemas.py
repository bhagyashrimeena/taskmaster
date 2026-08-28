"""Stable models for one continuous financial day."""

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..events.schemas import EventAssessment
from ..advisor.schemas import AdvisorPacket, AdvisorResponse
from ..story.schemas import DailyWealthStory
from ..cases.schemas import FinancialCase, FinancialCaseStatus
from ..taskmaster.schemas import OperatorCycle
from .active import AttentionBudget, AttentionSummary, ArtifactProvenance


class DayModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DayStatus(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class DayRunMode(StrEnum):
    IDLE = "idle"
    REAL = "real"
    DEMO = "demo"
    PRESENTATION = "presentation"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PortfolioHealthStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ATTENTION = "ATTENTION"


class SnapshotHolding(DayModel):
    symbol: str
    sector: str
    market_value: float
    portfolio_weight: float
    daily_return_pct: float = 0


class PortfolioSnapshot(DayModel):
    captured_at: datetime
    session: str
    source: str
    portfolio_value: float
    holdings: list[SnapshotHolding]


class PortfolioHealth(DayModel):
    assessed_at: datetime
    largest_holding: str
    largest_holding_pct: float
    largest_sector: str
    largest_sector_pct: float
    concentration_flags: list[str] = Field(default_factory=list)
    relevant_overnight_events: int = 0
    critical_events: int = 0
    status: PortfolioHealthStatus
    explanation: str


class HoldingContribution(DayModel):
    symbol: str
    portfolio_weight_pct: float
    daily_return_pct: float
    contribution_percentage_points: float
    direction: str


class MarketCloseReview(DayModel):
    generated_at: datetime
    portfolio_return_pct: float
    top_positive_contributors: list[HoldingContribution]
    top_negative_contributors: list[HoldingContribution]
    alert_event_ids: list[str] = Field(default_factory=list)
    advisor_request_ids: list[str] = Field(default_factory=list)
    advisor_response_ids: list[str] = Field(default_factory=list)
    explanation: str
    provenance: ArtifactProvenance | None = None


class TomorrowEvent(DayModel):
    event_id: str
    title: str
    scheduled_at: datetime
    event_type: str
    affected_holdings: list[str] = Field(default_factory=list)
    affected_sector: str | None = None
    portfolio_exposure_pct: float = 0
    why_relevant: str
    relevance_rank: int


class NewsSnapshot(DayModel):
    story_id: str
    day_id: str
    title: str
    source_name: str
    source_url: str
    source_status: str
    published_at: datetime
    symbols: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    summary: str
    known_facts: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    portfolio_relevance_reason: str
    direct_exposure_percent: float = 0
    sector_exposure_percent: float = 0
    relevance_score: float = 0
    decision: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LikelyScenario(DayModel):
    scenario_id: str
    story_id: str
    case_id: str | None = None
    symbol: str | None = None
    title: str
    base_summary: str
    scenario_type: str
    likelihood_label: str
    confidence: str
    why_it_could_happen: str
    what_to_monitor: str
    portfolio_relevance: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    status: str = "active"


class CalendarWatchEvent(DayModel):
    event_id: str
    day_id: str
    case_id: str | None = None
    story_id: str | None = None
    scenario_id: str | None = None
    symbol: str | None = None
    title: str
    description: str
    scheduled_for: datetime
    trigger_type: str
    status: str = "scheduled"
    created_by: str = "agent"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    reminder_copy: str
    external_provider: str | None = None
    external_event_id: str | None = None


class QuestionAsked(DayModel):
    question: str
    asked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    story_id: str | None = None
    event_id: str | None = None


class DayTimelineStep(DayModel):
    step_id: str
    scheduled_time: str
    label: str
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    detail: str = "Waiting for its scheduled checkpoint."
    linked_ids: list[str] = Field(default_factory=list)


def default_timeline() -> list[DayTimelineStep]:
    return [
        DayTimelineStep(step_id="morning", scheduled_time="07:00", label="Morning Pulse"),
        DayTimelineStep(step_id="health", scheduled_time="08:00", label="Portfolio Health"),
        DayTimelineStep(step_id="open", scheduled_time="09:15", label="Market Open Monitor"),
        DayTimelineStep(step_id="event", scheduled_time="09:15", label="Event Investigations"),
        DayTimelineStep(step_id="watch", scheduled_time="10:00", label="Adaptive Market Watch"),
        DayTimelineStep(step_id="sector", scheduled_time="11:30", label="Sector Deep Dive"),
        DayTimelineStep(step_id="learning", scheduled_time="13:00", label="Learn From Your Portfolio"),
        DayTimelineStep(step_id="close", scheduled_time="15:30", label="Market Close Review"),
        DayTimelineStep(step_id="intelligence", scheduled_time="17:00", label="Portfolio Intelligence"),
        DayTimelineStep(step_id="actions", scheduled_time="18:30", label="Action Queue"),
        DayTimelineStep(step_id="evening", scheduled_time="20:00", label="Evening Wealth Wrap"),
        DayTimelineStep(step_id="tomorrow", scheduled_time="21:00", label="Tomorrow Prep"),
        DayTimelineStep(step_id="story", scheduled_time="21:01", label="Daily Wealth Story"),
    ]


class FinancialDayState(DayModel):
    trading_date: date
    day_id: str = ""
    run_id: str = ""
    scenario_id: str | None = None
    user_id: str = "SIM001"
    status: DayStatus = DayStatus.NOT_STARTED
    run_mode: DayRunMode = DayRunMode.REAL
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    morning_brief_id: str | None = None
    portfolio_open_snapshot: PortfolioSnapshot | None = None
    portfolio_close_snapshot: PortfolioSnapshot | None = None
    portfolio_health: PortfolioHealth | None = None
    news_considered: list[str] = Field(default_factory=list)
    top_stories: list[str] = Field(default_factory=list)
    events_detected: list[EventAssessment] = Field(default_factory=list)
    events_alerted: list[EventAssessment] = Field(default_factory=list)
    events_ignored: list[EventAssessment] = Field(default_factory=list)
    financial_cases: list[FinancialCase] = Field(default_factory=list)
    open_case_ids: list[str] = Field(default_factory=list)
    operator_cycles: list[OperatorCycle] = Field(default_factory=list)
    attention_budget: AttentionBudget = Field(default_factory=AttentionBudget)
    market_snapshot_ids: list[str] = Field(default_factory=list)
    market_watch_runs: list[datetime] = Field(default_factory=list)
    selected_sector: str | None = None
    learning_topic: str | None = None
    portfolio_intelligence_summary: str | None = None
    action_queue: list[str] = Field(default_factory=list)
    saved_stories: list[str] = Field(default_factory=list)
    saved_events: list[str] = Field(default_factory=list)
    questions_asked: list[QuestionAsked] = Field(default_factory=list)
    advisor_requests: list[AdvisorPacket] = Field(default_factory=list)
    advisor_responses: list[AdvisorResponse] = Field(default_factory=list)
    market_close_review: MarketCloseReview | None = None
    evening_brief_id: str | None = None
    story_audio_brief_id: str | None = None
    daily_story: DailyWealthStory | None = None
    tomorrow_events: list[TomorrowEvent] = Field(default_factory=list)
    news_snapshots: list[NewsSnapshot] = Field(default_factory=list)
    likely_scenarios: list[LikelyScenario] = Field(default_factory=list)
    calendar_watch_events: list[CalendarWatchEvent] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    timeline: list[DayTimelineStep] = Field(default_factory=default_timeline)
    simulated_duration_seconds: int | None = None
    heartbeat_at: datetime | None = None
    active_step_id: str | None = None
    run_attempt: int = 0
    last_error: str | None = None
    presentation_minute: float | None = None
    presentation_status: str | None = None
    presentation_active_checkpoint: str | None = None
    presentation_message: str | None = None
    attention_summary: AttentionSummary = Field(
        default_factory=lambda: AttentionSummary(
            high_priority_count=0,
            portfolio_relevant_story_count=0,
            active_event_count=0,
        )
    )
    morning_pulse_provenance: ArtifactProvenance | None = None
    daily_story_provenance: ArtifactProvenance | None = None

    @model_validator(mode="after")
    def populate_identity(self):
        if not self.day_id:
            self.day_id = f"financial-day-{self.trading_date.isoformat()}"
        if not self.run_id:
            self.run_id = f"{self.day_id}-idle"
        self.open_case_ids = [
            item.case_id
            for item in self.financial_cases
            if item.status != FinancialCaseStatus.CLOSED
        ]
        return self
