"""Scenario-driven portfolio provider for safe, repeatable demonstrations."""

from datetime import date, datetime, time
from decimal import Decimal

from ..simulation import simulation_service
from .provider import PortfolioProvider
from .schemas import HistoricalCandle, Holding, Position, Profile, Quote


_ROWS = (
    ("HDFCBANK", "Financial Services", "75", "1680", "2021.60"),
    ("RELIANCE", "Energy", "100", "1260", "1431.40"),
    ("INFY", "Information Technology", "80", "1325", "1473.50"),
    ("TCS", "Information Technology", "25", "3550", "4041.60"),
    ("ICICIBANK", "Financial Services", "60", "1140", "1403.33"),
    ("BHARTIARTL", "Telecommunication", "40", "1420", "1684.00"),
    ("WIPRO", "Information Technology", "100", "440", "505.20"),
    ("ITC", "Consumer Staples", "200", "410", "450.00"),
    ("SUNPHARMA", "Healthcare", "20", "1600", "1812.00"),
)


class SimulatedPortfolioProvider(PortfolioProvider):
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
        reference_values = {
            symbol: Decimal(quantity) * Decimal(reference)
            for symbol, _, quantity, _, reference in _ROWS
        }
        reference_total = sum(reference_values.values(), Decimal("0"))
        raw = []
        for symbol, sector, quantity, average, reference in _ROWS:
            qty = Decimal(quantity)
            previous_close = Decimal(reference)
            return_pct = Decimal(str(snapshot.holding_returns_pct.get(symbol, 0.0)))
            current_price = (previous_close * (Decimal("1") + return_pct / 100)).quantize(
                Decimal("0.01")
            )
            average_price = Decimal(average)
            raw.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "quantity": qty,
                    "average_price": average_price,
                    "current_price": current_price,
                    "previous_close": previous_close,
                    "market_value": qty * current_price,
                    "invested_value": qty * average_price,
                }
            )
        return [
            Holding(
                **row,
                unrealized_pnl=row["market_value"] - row["invested_value"],
                day_pnl=row["quantity"] * (row["current_price"] - row["previous_close"]),
                portfolio_weight=(
                    reference_values[row["symbol"]] / reference_total * 100
                ).quantize(Decimal("0.01")),
            )
            for row in raw
        ]

    async def get_profile(self) -> Profile:
        return Profile(
            source="simulated",
            provider="simulated",
            scenario_id=self.scenario_id,
            user_id="SIM001",
            user_name="Simulated Investor",
            email="simulation@example.invalid",
            broker="Simulated Portfolio",
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
