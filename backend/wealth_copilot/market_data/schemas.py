"""Provider-neutral market-price and market-snapshot contracts."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MarketDataModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MarketQuote(MarketDataModel):
    instrument: str
    last_price: Decimal = Field(ge=0)
    previous_close: Decimal | None = Field(default=None, ge=0)
    change_pct: Decimal | None = None
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    is_live: bool


class IntradayPoint(MarketDataModel):
    timestamp: datetime
    price: Decimal = Field(ge=0)
    volume: int = Field(default=0, ge=0)


class HistoricalPrice(MarketDataModel):
    timestamp: datetime
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    volume: int = Field(default=0, ge=0)


class IndexQuote(MarketQuote):
    index_name: str


class SectorSnapshot(MarketDataModel):
    sector: str
    change_pct: Decimal
    as_of: datetime
    provider: str
    is_live: bool


class VolumeSnapshot(MarketDataModel):
    instrument: str
    volume: int = Field(ge=0)
    baseline_volume: int | None = Field(default=None, ge=0)
    change_pct: Decimal | None = None
    as_of: datetime
    provider: str
    is_live: bool


class MarketSnapshot(MarketDataModel):
    snapshot_id: str
    as_of: datetime
    market_status: Literal["pre_open", "open", "closed", "unknown"] = "unknown"
    provider: str
    is_live: bool
    quotes: dict[str, MarketQuote] = Field(default_factory=dict)
    indexes: dict[str, IndexQuote] = Field(default_factory=dict)
    sectors: dict[str, SectorSnapshot] = Field(default_factory=dict)
