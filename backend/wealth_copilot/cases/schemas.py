"""Durable financial-case contracts for material event continuity."""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..events.schemas import MarketEvent
from ..market.schemas import NewsCandidate


class CaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FinancialCaseStatus(StrEnum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    MONITORING = "MONITORING"
    ALERTED = "ALERTED"
    USER_ENGAGED = "USER_ENGAGED"
    ADVISOR_PENDING = "ADVISOR_PENDING"
    CARRY_FORWARD = "CARRY_FORWARD"
    CLOSED = "CLOSED"


class FinancialCasePriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PortfolioExposure(CaseModel):
    direct_pct: float = Field(ge=0, le=100)
    sector_pct: float = Field(ge=0, le=100)
    affected_holdings: list[str] = Field(default_factory=list)


class FinancialCase(CaseModel):
    case_id: str
    instrument: str | None = None
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: FinancialCaseStatus = FinancialCaseStatus.DETECTED
    priority: FinancialCasePriority = FinancialCasePriority.MEDIUM
    trigger: MarketEvent
    portfolio_exposure: PortfolioExposure
    research: list[NewsCandidate] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    user_questions: list[str] = Field(default_factory=list)
    saves: list[str] = Field(default_factory=list)
    advisor_interactions: list[str] = Field(default_factory=list)
    market_close_result: str | None = None
    tomorrow_status: str | None = None
    closed_at: datetime | None = None
