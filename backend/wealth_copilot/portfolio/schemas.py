"""Provider-neutral portfolio data models."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WealthModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Profile(WealthModel):
    source: Literal["simulated", "zerodha"]
    provider: Literal["simulated", "zerodha"]
    scenario_id: str | None = None
    user_id: str
    user_name: str
    email: str | None = None
    broker: str | None = None


class Holding(WealthModel):
    symbol: str
    exchange: str = "NSE"
    quantity: Decimal = Field(ge=0)
    average_price: Decimal = Field(ge=0)
    current_price: Decimal = Field(ge=0)
    previous_close: Decimal | None = Field(default=None, ge=0)
    market_value: Decimal = Field(ge=0)
    invested_value: Decimal = Field(ge=0)
    unrealized_pnl: Decimal
    day_pnl: Decimal | None = None
    portfolio_weight: Decimal = Field(ge=0, le=100)
    sector: str | None = None


class Position(WealthModel):
    symbol: str
    exchange: str = "NSE"
    product: str | None = None
    quantity: Decimal
    average_price: Decimal = Field(ge=0)
    current_price: Decimal = Field(ge=0)
    pnl: Decimal


class Quote(WealthModel):
    instrument: str
    last_price: Decimal = Field(ge=0)
    ohlc_open: Decimal | None = None
    ohlc_high: Decimal | None = None
    ohlc_low: Decimal | None = None
    ohlc_close: Decimal | None = None
    timestamp: datetime | None = None


class HistoricalCandle(WealthModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)
    open_interest: int | None = Field(default=None, ge=0)


class SectorExposure(WealthModel):
    sector: str
    market_value: Decimal = Field(ge=0)
    portfolio_weight: Decimal = Field(ge=0, le=100)


class PortfolioSummary(WealthModel):
    source: Literal["simulated", "zerodha"]
    provider: Literal["simulated", "zerodha"]
    scenario_id: str | None = None
    is_live: bool
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str = "INR"
    portfolio_value: Decimal = Field(ge=0)
    invested_value: Decimal = Field(ge=0)
    unrealized_pnl: Decimal
    day_pnl: Decimal | None = None
    holdings: list[Holding]
    sector_exposure: list[SectorExposure]


class HistoricalRequest(WealthModel):
    symbol: str
    from_date: date
    to_date: date
    interval: str = "day"


class ToolResult(WealthModel):
    status: Literal["ok", "error", "authentication_required"]
    source: Literal["simulated", "zerodha"]
    data: Any | None = None
    error: str | None = None
    suggestion: str | None = None
