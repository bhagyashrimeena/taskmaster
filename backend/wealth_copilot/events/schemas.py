"""Provider-neutral schemas for deterministic market-event decisions."""

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..market.schemas import NewsCandidate
from ..day.active import ArtifactProvenance


class EventModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MarketEventType(StrEnum):
    PRICE_MOVE = "PRICE_MOVE"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    EARNINGS = "EARNINGS"
    CORPORATE_ANNOUNCEMENT = "CORPORATE_ANNOUNCEMENT"
    REGULATORY = "REGULATORY"
    MACRO = "MACRO"
    NEWS = "NEWS"


class EventSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventDecision(StrEnum):
    IGNORE = "IGNORE"
    MONITOR = "MONITOR"
    INVESTIGATE = "INVESTIGATE"
    ALERT = "ALERT"


class InvestigationStatus(StrEnum):
    SKIPPED = "skipped"
    COMPLETE = "complete"
    FAILED = "failed"


class MarketEvent(EventModel):
    event_id: str = Field(min_length=3, max_length=120)
    instrument: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: MarketEventType
    symbol: str | None = None
    company: str | None = None
    sector: str | None = None
    price_change_pct: float | None = None
    sector_change_pct: float | None = None
    index_change_pct: float | None = None
    volume_change_pct: float | None = None
    headline: str = Field(min_length=5, max_length=300)
    source: str = Field(min_length=2, max_length=120)
    source_url: str
    severity: EventSeverity = EventSeverity.MEDIUM
    has_material_news: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None

    @field_validator("instrument")
    @classmethod
    def normalize_instrument(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        cleaned = value.strip().upper()
        return cleaned if ":" in cleaned else f"NSE:{cleaned}"

    @model_validator(mode="after")
    def align_instrument_and_symbol(self):
        if self.instrument and not self.symbol:
            self.symbol = self.instrument.split(":", 1)[-1]
        elif self.symbol and not self.instrument:
            self.instrument = f"NSE:{self.symbol}"
        return self

    @field_validator("source_url")
    @classmethod
    def source_must_be_http(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("source_url must be an HTTP(S) URL")
        return value.strip()


class TriggerSignal(EventModel):
    rule: str
    triggered: bool
    observed: float | str | bool | None = None
    threshold: float | str | None = None
    reason: str


class EventTraceStep(EventModel):
    stage: str
    outcome: str
    details: dict[str, Any] = Field(default_factory=dict)


class EventAssessment(EventModel):
    day_id: str | None = None
    run_id: str | None = None
    event: MarketEvent
    portfolio_source: str
    direct_holding: bool
    affected_holdings: list[str]
    affected_portfolio_percentage: float = Field(ge=0, le=100)
    sector_exposure_percentage: float = Field(ge=0, le=100)
    sector_relative_move_pct: float | None = None
    trigger_detected: bool
    trigger_signals: list[TriggerSignal]
    investigation_status: InvestigationStatus
    investigation_error: str | None = None
    developments: list[NewsCandidate] = Field(default_factory=list)
    relevance_score: float = Field(ge=0, le=100)
    decision: EventDecision
    notification_required: bool
    title: str
    reason: str
    actions: list[str] = Field(default_factory=list)
    trace: list[EventTraceStep]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance: ArtifactProvenance | None = None


class StoredEvent(EventModel):
    assessment: EventAssessment
    notification_status: str = "not_sent"
    user_action: str | None = None


class DailyEventState(EventModel):
    trading_date: date
    events: list[StoredEvent] = Field(default_factory=list)
