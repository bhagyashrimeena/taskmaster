"""Canonical demo portfolio backed by repeatable scenario market values."""

from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal

from ..simulation import simulation_service
from .provider import PortfolioProvider
from .schemas import (
    AssetAllocation,
    HistoricalCandle,
    Holding,
    PerformancePoint,
    PortfolioSummary,
    Position,
    Profile,
    Quote,
    SectorExposure,
)


_DEMO_ROWS = (
    {
        "symbol": "HDFCBANK",
        "name": "HDFC Bank",
        "sector": "Financial Services",
        "asset_class": "Indian equity",
        "quantity": "100",
        "average_price": "1420",
        "target_current_price": "1532",
        "target_day_pnl": "-8745",
    },
    {
        "symbol": "RELIANCE",
        "name": "Reliance Industries",
        "sector": "Energy",
        "asset_class": "Indian equity",
        "quantity": "70",
        "average_price": "1330",
        "target_current_price": "1450",
        "target_day_pnl": "3240",
    },
    {
        "symbol": "INFY",
        "name": "Infosys",
        "sector": "Information Technology",
        "asset_class": "Indian equity",
        "quantity": "45",
        "average_price": "1650",
        "target_current_price": "1580",
        "target_day_pnl": "-300",
    },
    {
        "symbol": "TCS",
        "name": "TCS",
        "sector": "Information Technology",
        "asset_class": "Indian equity",
        "quantity": "15",
        "average_price": "3600",
        "target_current_price": "3800",
        "target_day_pnl": "220",
    },
    {
        "symbol": "BHARTIARTL",
        "name": "Bharti Airtel",
        "sector": "Telecom",
        "asset_class": "Indian equity",
        "quantity": "30",
        "average_price": "1550",
        "target_current_price": "1800",
        "target_day_pnl": "800",
    },
    {
        "symbol": "ITC",
        "name": "ITC",
        "sector": "Consumer Staples",
        "asset_class": "Indian equity",
        "quantity": "100",
        "average_price": "450",
        "target_current_price": "420",
        "target_day_pnl": "-180",
    },
    {
        "symbol": "SUNPHARMA",
        "name": "Sun Pharma",
        "sector": "Healthcare",
        "asset_class": "Indian equity",
        "quantity": "20",
        "average_price": "1500",
        "target_current_price": "1750",
        "target_day_pnl": "100",
    },
    {
        "symbol": "ICICIBANK",
        "name": "ICICI Bank",
        "sector": "Financial Services",
        "asset_class": "Indian equity",
        "quantity": "20",
        "average_price": "1110",
        "target_current_price": "1250",
        "target_day_pnl": "-200",
    },
    {
        "symbol": "PPFAS",
        "name": "Parag Parikh Flexi Cap Fund",
        "sector": "Diversified equity",
        "asset_class": "Mutual funds",
        "quantity": "1",
        "average_price": "76000",
        "target_current_price": "85000",
        "target_day_pnl": "0",
    },
    {
        "symbol": "UTINIFTY",
        "name": "UTI Nifty 50 Index Fund",
        "sector": "Diversified equity",
        "asset_class": "Mutual funds",
        "quantity": "1",
        "average_price": "63000",
        "target_current_price": "70000",
        "target_day_pnl": "0",
    },
    {
        "symbol": "MOMIDCAP",
        "name": "Motilal Oswal Midcap Fund",
        "sector": "Diversified equity",
        "asset_class": "Mutual funds",
        "quantity": "1",
        "average_price": "45000",
        "target_current_price": "50000",
        "target_day_pnl": "0",
    },
    {
        "symbol": "HDFCSTDEBT",
        "name": "HDFC Short Term Debt Fund",
        "sector": "Debt",
        "asset_class": "Debt",
        "quantity": "1",
        "average_price": "38500",
        "target_current_price": "40000",
        "target_day_pnl": "0",
    },
    {
        "symbol": "GOLDETF",
        "name": "Gold ETF",
        "sector": "Gold",
        "asset_class": "Gold",
        "quantity": "1",
        "average_price": "29500",
        "target_current_price": "33200",
        "target_day_pnl": "0",
    },
    {
        "symbol": "CASH",
        "name": "Cash balance",
        "sector": "Cash",
        "asset_class": "Cash",
        "quantity": "1",
        "average_price": "24999.80",
        "target_current_price": "24999.80",
        "target_day_pnl": "0",
    },
)

# Fund composition is fixture input. Portfolio-level sector exposure is always
# calculated from each holding's current market value and these fund weights.
_FUND_SECTOR_LOOKTHROUGH: dict[str, dict[str, Decimal]] = {
    "PPFAS": {
        "Financial Services": Decimal("24"),
        "Information Technology": Decimal("17"),
        "Consumer Discretionary": Decimal("18"),
        "Communication Services": Decimal("12"),
        "Industrials": Decimal("10"),
        "Healthcare": Decimal("8"),
        "Other": Decimal("11"),
    },
    "UTINIFTY": {
        "Financial Services": Decimal("34"),
        "Information Technology": Decimal("14"),
        "Energy": Decimal("13"),
        "Consumer Staples": Decimal("9"),
        "Industrials": Decimal("9"),
        "Healthcare": Decimal("5"),
        "Other": Decimal("16"),
    },
    "MOMIDCAP": {
        "Financial Services": Decimal("18"),
        "Information Technology": Decimal("12"),
        "Industrials": Decimal("23"),
        "Consumer Discretionary": Decimal("18"),
        "Healthcare": Decimal("10"),
        "Other": Decimal("19"),
    },
}

_PERFORMANCE = (
    ("1D", "-0.60", "-0.30"),
    ("1W", "1.70", "0.80"),
    ("1M", "3.80", "2.50"),
    ("3M", "6.50", "4.80"),
    ("1Y", "9.40", "8.20"),
)


def _previous_close(row: dict[str, str]) -> Decimal:
    quantity = Decimal(row["quantity"])
    target_value = quantity * Decimal(row["target_current_price"])
    target_day_pnl = Decimal(row["target_day_pnl"])
    return ((target_value - target_day_pnl) / quantity).quantize(Decimal("0.0001"))


class DemoPortfolioProvider(PortfolioProvider):
    source = "simulated"
    is_live = False

    @property
    def scenario_id(self) -> str:
        return simulation_service.state().scenario_id

    @property
    def as_of(self) -> datetime:
        return simulation_service.snapshot().as_of

    def _holdings(self) -> list[Holding]:
        snapshot = simulation_service.snapshot()
        raw = []
        for row in _DEMO_ROWS:
            qty = Decimal(row["quantity"])
            previous_close = _previous_close(row)
            return_pct = Decimal(str(snapshot.holding_returns_pct.get(row["symbol"], 0.0)))
            current_price = (previous_close * (Decimal("1") + return_pct / 100)).quantize(
                Decimal("0.01")
            )
            average_price = Decimal(row["average_price"])
            raw.append(
                {
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "asset_class": row["asset_class"],
                    "sector": row["sector"],
                    "sector_lookthrough": _FUND_SECTOR_LOOKTHROUGH.get(row["symbol"], {}),
                    "quantity": qty,
                    "average_price": average_price,
                    "current_price": current_price,
                    "previous_close": previous_close,
                    "market_value": qty * current_price,
                    "invested_value": qty * average_price,
                }
            )
        current_total = sum((row["market_value"] for row in raw), Decimal("0"))
        return [
            Holding(
                **row,
                unrealized_pnl=row["market_value"] - row["invested_value"],
                day_pnl=row["quantity"] * (row["current_price"] - row["previous_close"]),
                portfolio_weight=(
                    row["market_value"] / current_total * 100
                ).quantize(Decimal("0.01")),
            )
            for row in raw
        ]

    async def get_summary(self) -> PortfolioSummary:
        holdings = self._holdings()
        portfolio_value = sum((holding.market_value for holding in holdings), Decimal("0"))
        invested_value = sum((holding.invested_value for holding in holdings), Decimal("0"))
        sector_values: dict[str, Decimal] = defaultdict(Decimal)
        allocation_values: dict[str, Decimal] = defaultdict(Decimal)
        for holding in holdings:
            allocation_values[holding.asset_class or "Unclassified"] += holding.market_value
            if holding.sector_lookthrough:
                for sector, weight in holding.sector_lookthrough.items():
                    sector_values[sector] += holding.market_value * weight / 100
            else:
                sector_values[holding.sector or "Unclassified"] += holding.market_value
        sectors = sorted(
            (
                SectorExposure(
                    sector=sector,
                    market_value=value.quantize(Decimal("0.01")),
                    portfolio_weight=(value / portfolio_value * 100).quantize(Decimal("0.01")),
                )
                for sector, value in sector_values.items()
            ),
            key=lambda item: item.market_value,
            reverse=True,
        )
        allocation = sorted(
            (
                AssetAllocation(
                    label=label,
                    market_value=value,
                    portfolio_weight=(value / portfolio_value * 100).quantize(Decimal("0.01")),
                )
                for label, value in allocation_values.items()
            ),
            key=lambda item: item.market_value,
            reverse=True,
        )
        performance = [
            PerformancePoint(
                period=period,
                portfolio_return_pct=Decimal(portfolio_return),
                benchmark_return_pct=Decimal(benchmark_return),
                benchmark_label="Nifty 50",
            )
            for period, portfolio_return, benchmark_return in _PERFORMANCE
        ]
        return PortfolioSummary(
            source="simulated",
            provider="simulated",
            scenario_id=self.scenario_id,
            is_live=self.is_live,
            as_of=self.as_of,
            portfolio_value=portfolio_value,
            invested_value=invested_value,
            unrealized_pnl=portfolio_value - invested_value,
            day_pnl=sum((holding.day_pnl or Decimal("0") for holding in holdings), Decimal("0")),
            overall_return_pct=(
                (portfolio_value - invested_value) / invested_value * 100
            ).quantize(Decimal("0.01")) if invested_value else Decimal("0"),
            equity_exposure_pct=sum(
                item.portfolio_weight
                for item in allocation
                if item.label in {"Indian equity", "Mutual funds"}
            ),
            defensive_exposure_pct=sum(
                item.portfolio_weight
                for item in allocation
                if item.label in {"Debt", "Gold", "Cash"}
            ),
            risk_profile="Moderately aggressive",
            holdings=sorted(holdings, key=lambda item: item.market_value, reverse=True),
            sector_exposure=sectors,
            asset_allocation=allocation,
            performance=performance,
            data_source_label="Demo portfolio",
        )

    async def get_profile(self) -> Profile:
        return Profile(
            source="simulated",
            provider="simulated",
            scenario_id=self.scenario_id,
            user_id="SIM001",
            user_name="Demo Investor",
            email="demo@example.invalid",
            broker="Demo portfolio",
        )

    async def get_holdings(self) -> list[Holding]:
        return [holding.model_copy(deep=True) for holding in self._holdings()]

    async def get_positions(self) -> list[Position]:
        return []

    @staticmethod
    def _normalize_instrument(instrument: str) -> str:
        return instrument.upper() if ":" in instrument else f"NSE:{instrument.upper()}"

    async def get_quotes(self, instruments: list[str]) -> dict[str, Quote]:
        by_symbol = {holding.symbol: holding for holding in self._holdings()}
        result: dict[str, Quote] = {}
        for requested in instruments:
            instrument = self._normalize_instrument(requested)
            symbol = instrument.split(":", 1)[1]
            holding = by_symbol.get(symbol)
            if holding:
                result[instrument] = Quote(
                    instrument=instrument,
                    last_price=holding.current_price,
                    ohlc_open=holding.previous_close,
                    ohlc_high=max(holding.current_price, holding.previous_close) * Decimal("1.006"),
                    ohlc_low=min(holding.current_price, holding.previous_close) * Decimal("0.994"),
                    ohlc_close=holding.previous_close,
                    timestamp=self.as_of,
                )
        return result

    async def get_ltp(self, instruments: list[str]) -> dict[str, Decimal]:
        return {
            instrument: quote.last_price
            for instrument, quote in (await self.get_quotes(instruments)).items()
        }

    async def get_ohlc(self, instruments: list[str]) -> dict[str, Quote]:
        return await self.get_quotes(instruments)

    async def get_historical_data(
        self, symbol: str, from_date: date, to_date: date, interval: str = "day"
    ) -> list[HistoricalCandle]:
        quote = (await self.get_quotes([symbol])).get(self._normalize_instrument(symbol))
        if quote is None or from_date > to_date:
            return []
        candles: list[HistoricalCandle] = []
        cursor = from_date
        index = 0
        while cursor <= to_date:
            if cursor.weekday() < 5:
                factor = Decimal("1") + (Decimal(index - 2) * Decimal("0.002"))
                close = (quote.last_price * factor).quantize(Decimal("0.01"))
                candles.append(
                    HistoricalCandle(
                        timestamp=datetime.combine(cursor, time(15, 30), tzinfo=self.as_of.tzinfo),
                        open=(close * Decimal("0.996")).quantize(Decimal("0.01")),
                        high=(close * Decimal("1.008")).quantize(Decimal("0.01")),
                        low=(close * Decimal("0.992")).quantize(Decimal("0.01")),
                        close=close,
                        volume=1_000_000 + index * 10_000,
                    )
                )
                index += 1
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return candles


# Compatibility for existing imports and environment names. New application
# code should use DemoPortfolioProvider; simulation remains a developer fixture.
SimulatedPortfolioProvider = DemoPortfolioProvider


__all__ = ["DemoPortfolioProvider", "SimulatedPortfolioProvider"]
