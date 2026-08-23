"""Market-price provider public API, separate from news and Search."""

from .demo_provider import DemoMarketDataProvider
from .provider import MarketDataProvider, MarketDataProviderError, get_market_data_provider
from .schemas import (
    HistoricalPrice,
    IndexQuote,
    IntradayPoint,
    MarketQuote,
    MarketSnapshot,
    SectorSnapshot,
    VolumeSnapshot,
)

__all__ = [
    "DemoMarketDataProvider",
    "HistoricalPrice",
    "IndexQuote",
    "IntradayPoint",
    "MarketDataProvider",
    "MarketDataProviderError",
    "MarketQuote",
    "MarketSnapshot",
    "SectorSnapshot",
    "VolumeSnapshot",
    "get_market_data_provider",
]
