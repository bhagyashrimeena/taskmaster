"""Portfolio provider contract and centralized selection."""

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import logging

from ..config import Settings, get_settings
from .schemas import (
    AssetAllocation,
    HistoricalCandle,
    Holding,
    PortfolioSummary,
    Position,
    Profile,
    Quote,
    SectorExposure,
)


logger = logging.getLogger(__name__)


class PortfolioProviderError(RuntimeError):
    """Base error safe to surface to an application caller."""


class PortfolioAuthenticationRequired(PortfolioProviderError):
    """The live provider requires interactive authentication."""


class PortfolioToolUnavailable(PortfolioProviderError):
    """The configured provider does not expose a requested operation."""


class PortfolioProvider(ABC):
    """Normalized application-facing portfolio interface."""

    source: str
    is_live: bool
    scenario_id: str | None = None

    @abstractmethod
    async def get_profile(self) -> Profile: ...

    @abstractmethod
    async def get_holdings(self) -> list[Holding]: ...

    @abstractmethod
    async def get_positions(self) -> list[Position]: ...

    @abstractmethod
    async def get_quotes(self, instruments: list[str]) -> dict[str, Quote]: ...

    @abstractmethod
    async def get_ltp(self, instruments: list[str]) -> dict[str, Decimal]: ...

    @abstractmethod
    async def get_ohlc(self, instruments: list[str]) -> dict[str, Quote]: ...

    @abstractmethod
    async def get_historical_data(
        self, symbol: str, from_date: date, to_date: date, interval: str = "day"
    ) -> list[HistoricalCandle]: ...

    async def get_summary(self) -> PortfolioSummary:
        holdings = await self.get_holdings()
        portfolio_value = sum((h.market_value for h in holdings), Decimal("0"))
        invested_value = sum((h.invested_value for h in holdings), Decimal("0"))
        day_values = [h.day_pnl for h in holdings if h.day_pnl is not None]
        sector_values: dict[str, Decimal] = defaultdict(Decimal)
        allocation_values: dict[str, Decimal] = defaultdict(Decimal)
        for holding in holdings:
            holding.portfolio_weight = (
                (holding.market_value / portfolio_value * 100).quantize(Decimal("0.01"))
                if portfolio_value
                else Decimal("0")
            )
            allocation_values[holding.asset_class or "Unclassified"] += holding.market_value
            if holding.sector_lookthrough:
                for sector, weight in holding.sector_lookthrough.items():
                    sector_values[sector] += holding.market_value * weight / 100
            else:
                sector_values[holding.sector or "Unclassified"] += holding.market_value

        sectors = [
            SectorExposure(
                sector=sector,
                market_value=value,
                portfolio_weight=(value / portfolio_value * 100).quantize(Decimal("0.01"))
                if portfolio_value
                else Decimal("0"),
            )
            for sector, value in sector_values.items()
        ]
        sectors.sort(key=lambda item: item.market_value, reverse=True)
        allocation = [
            AssetAllocation(
                label=label,
                market_value=value,
                portfolio_weight=(value / portfolio_value * 100).quantize(Decimal("0.01"))
                if portfolio_value
                else Decimal("0"),
            )
            for label, value in allocation_values.items()
        ]
        allocation.sort(key=lambda item: item.market_value, reverse=True)
        return PortfolioSummary(
            source=self.source,  # type: ignore[arg-type]
            provider=self.source,  # type: ignore[arg-type]
            scenario_id=self.scenario_id,
            is_live=self.is_live,
            as_of=getattr(self, "as_of", None) or datetime.now(timezone.utc),
            portfolio_value=portfolio_value,
            invested_value=invested_value,
            unrealized_pnl=portfolio_value - invested_value,
            day_pnl=sum(day_values, Decimal("0")) if day_values else None,
            holdings=sorted(holdings, key=lambda item: item.market_value, reverse=True),
            sector_exposure=sectors,
            asset_allocation=allocation,
            data_source_label="Connected portfolio" if self.is_live else "Demo portfolio",
        )


def get_portfolio_provider(settings: Settings | None = None) -> PortfolioProvider:
    """Select one provider in one place; never silently fall back from live data."""

    selected = settings or get_settings()
    logger.info("Portfolio provider selected: %s", selected.portfolio_provider)
    if selected.portfolio_provider == "zerodha":
        from .zerodha_provider import ZerodhaPortfolioProvider

        return ZerodhaPortfolioProvider(
            url=selected.zerodha_mcp_url,
            timeout_seconds=selected.zerodha_mcp_timeout_seconds,
        )
    if selected.portfolio_provider == "simulated":
        from .demo_provider import DemoPortfolioProvider

        return DemoPortfolioProvider()
    raise ValueError(
        f"Unsupported PORTFOLIO_PROVIDER={selected.portfolio_provider!r}; use simulated or zerodha."
    )
