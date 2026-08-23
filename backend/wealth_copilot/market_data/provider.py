"""Market-data provider interface and centralized selection."""

from abc import ABC, abstractmethod
from datetime import date

from ..config import Settings, get_settings
from .schemas import (
    HistoricalPrice,
    IndexQuote,
    IntradayPoint,
    MarketQuote,
    MarketSnapshot,
    SectorSnapshot,
    VolumeSnapshot,
)


class MarketDataProviderError(RuntimeError):
    """Safe application-facing market-data failure."""


class MarketDataProvider(ABC):
    """Price data only. News and research do not implement this contract."""

    source: str
    is_live: bool

    @abstractmethod
    async def get_quote(self, instrument: str) -> MarketQuote | None: ...

    @abstractmethod
    async def get_quotes(self, instruments: list[str]) -> dict[str, MarketQuote]: ...

    @abstractmethod
    async def get_intraday(
        self, instrument: str, *, trading_date: date | None = None
    ) -> list[IntradayPoint]: ...

    @abstractmethod
    async def get_index_quote(self, index: str) -> IndexQuote | None: ...

    @abstractmethod
    async def get_sector_snapshot(self, sector: str) -> SectorSnapshot | None: ...

    @abstractmethod
    async def get_market_snapshot(
        self, instruments: list[str] | None = None
    ) -> MarketSnapshot: ...

    @abstractmethod
    async def get_volume(self, instrument: str) -> VolumeSnapshot | None: ...

    @abstractmethod
    async def get_historical_prices(
        self,
        instrument: str,
        *,
        from_date: date,
        to_date: date,
        interval: str = "day",
    ) -> list[HistoricalPrice]: ...


def get_market_data_provider(settings: Settings | None = None) -> MarketDataProvider:
    selected = settings or get_settings()
    if selected.market_data_provider == "demo":
        from .demo_provider import DemoMarketDataProvider

        return DemoMarketDataProvider()
    raise ValueError(
        f"Unsupported MARKET_DATA_PROVIDER={selected.market_data_provider!r}; use demo."
    )
