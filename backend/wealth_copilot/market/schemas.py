"""Source-preserving market-news and personalization schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewsModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EventType(StrEnum):
    EARNINGS = "earnings"
    CORPORATE_ACTION = "corporate_action"
    REGULATORY = "regulatory"
    MANAGEMENT = "management"
    PRODUCT = "product"
    MACRO = "macro"
    SECTOR = "sector"
    MARKET_MOVE = "market_move"
    OTHER = "other"


class Materiality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceAuthority(StrEnum):
    TIER_1_PRIMARY = "tier_1_primary"
    TIER_2_ESTABLISHED = "tier_2_established"
    TIER_3_SECONDARY = "tier_3_secondary"
    TIER_4_OTHER = "tier_4_other"


class NewsCandidate(NewsModel):
    id: str
    headline: str = Field(min_length=5, max_length=300)
    summary: str = Field(min_length=10, max_length=1500)
    source_name: str = Field(min_length=2, max_length=120)
    source_url: str
    grounding_uri: str | None = None
    canonical_url: str | None = None
    canonical_url_status: Literal["verified", "unavailable"] = "unavailable"
    published_at: datetime
    companies: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    event_type: EventType = EventType.OTHER
    market_move_pct: float | None = None

    @field_validator("source_url")
    @classmethod
    def source_must_be_http(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"https", "http"} or not parts.netloc:
            raise ValueError("source_url must be an HTTP(S) URL")
        if parts.path in {"", "/"} and not parts.query:
            raise ValueError("source_url must identify an article, not a publisher homepage")
        return value.strip()

    @field_validator("companies", "sectors")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class NewsCandidateBatch(NewsModel):
    source: str
    is_live: bool
    generated_at: datetime
    candidates: list[NewsCandidate]


class CanonicalUrlResolution(NewsModel):
    canonical_url: str | None = None
    status: Literal["verified", "unavailable"] = "unavailable"
    resolved_at: datetime


class MarketBriefSnapshot(NewsModel):
    snapshot_id: str
    generated_at: datetime
    retrieved_at: datetime
    provider: str
    status: str
    candidate_count: int = Field(ge=0)
    batch: NewsCandidateBatch
    canonical_urls: dict[str, "CanonicalUrlResolution"] = Field(default_factory=dict)


class RelevanceSignals(NewsModel):
    direct_holding: float = Field(ge=0, le=35)
    exposure_magnitude: float = Field(ge=0, le=20)
    sector_exposure: float = Field(ge=0, le=12)
    event_materiality: float = Field(ge=0, le=15)
    freshness: float = Field(ge=0, le=10)
    market_movement: float = Field(ge=0, le=8)

    @property
    def total(self) -> float:
        return round(
            self.direct_holding
            + self.exposure_magnitude
            + self.sector_exposure
            + self.event_materiality
            + self.freshness
            + self.market_movement,
            2,
        )


class PersonalizedNews(NewsCandidate):
    affected_holdings: list[str]
    direct_exposure_pct: float = Field(ge=0, le=100)
    sector_exposure_pct: float = Field(ge=0, le=100)
    relevance_score: float = Field(ge=0, le=100)
    materiality: Materiality
    signals: RelevanceSignals
    why_it_matters: str
    why_am_i_seeing_this: str
    source_authority: SourceAuthority = SourceAuthority.TIER_4_OTHER
    source_quality_score: float = Field(default=0, ge=0, le=8)
    novelty_score: float = Field(default=0, ge=0, le=4)
    similarity_penalty: float = Field(default=0, ge=0, le=12)
    company_saturation_penalty: float = Field(default=0, ge=0)
    final_utility_score: float = Field(default=0, ge=0, le=100)
    selection_reason: str = ""
    notification_required: bool = False


class PersonalizedNewsFeed(NewsModel):
    portfolio_source: str
    news_source: str
    news_is_live: bool
    generated_at: datetime
    candidate_count: int = Field(ge=0)
    deduplicated_count: int = Field(ge=0)
    stories: list[PersonalizedNews]


def candidate_json_schema() -> dict[str, Any]:
    """Schema hint used in Market Agent instructions."""

    return NewsCandidate.model_json_schema()
