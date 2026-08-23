"""Deterministic market-price provider for local development and tests."""

from datetime import date, datetime, time
from decimal import Decimal
from hashlib import sha256

from ..portfolio.demo_provider import DemoPortfolioProvider
from ..simulation import simulation_service
from .provider import MarketDataProvider
from .schemas import (
    HistoricalPrice,
    IndexQuote,
    IntradayPoint,
    MarketQuote,
    MarketSnapshot,
    SectorSnapshot,
    VolumeSnapshot,
)


class DemoMarketDataProvider(MarketDataProvider):
    source = "demo_market_data"
    is_live = False

    def __init__(self, portfolio: DemoPortfolioProvider | None = None) -> None:
        self.portfolio = portfolio or DemoPortfolioProvider()

    @staticmethod
    def _normalize(instrument: str) -> str:
        cleaned = instrument.strip().upper()
        return cleaned if ":" in cleaned else f"NSE:{cleaned}"

    async def get_quote(self, instrument: str) -> MarketQuote | None:
        normalized = self._normalize(instrument)
        quote = (await self.portfolio.get_quotes([normalized])).get(normalized)
        if quote is None:
            return None
        change = None
        if quote.ohlc_close:
            change = ((quote.last_price - quote.ohlc_close) / quote.ohlc_close * 100).quantize(
                Decimal("0.01")
            )
        return MarketQuote(
            instrument=normalized,
            last_price=quote.last_price,
            previous_close=quote.ohlc_close,
            change_pct=change,
            as_of=quote.timestamp or simulation_service.snapshot().as_of,
            provider=self.source,
            is_live=self.is_live,
        )

    async def get_quotes(self, instruments: list[str]) -> dict[str, MarketQuote]:
        result: dict[str, MarketQuote] = {}
        for instrument in dict.fromkeys(instruments):
            quote = await self.get_quote(instrument)
            if quote:
                result[quote.instrument] = quote
        return result

    async def get_intraday(
        self, instrument: str, *, trading_date: date | None = None
    ) -> list[IntradayPoint]:
        quote = await self.get_quote(instrument)
        if quote is None:
            return []
        selected = trading_date or quote.as_of.date()
        zone = quote.as_of.tzinfo
        previous = quote.previous_close or quote.last_price
        points: list[IntradayPoint] = []
        checkpoints = (time(9, 15), time(10, 30), time(12, 0), time(13, 45), time(15, 30))
        for index, checkpoint in enumerate(checkpoints):
            progress = Decimal(index + 1) / Decimal(len(checkpoints))
            price = (previous + (quote.last_price - previous) * progress).quantize(Decimal("0.01"))
            points.append(
                IntradayPoint(
                    timestamp=datetime.combine(selected, checkpoint, tzinfo=zone),
                    price=price,
                    volume=200_000 * (index + 1),
                )
            )
        return points

    async def get_index_quote(self, index: str) -> IndexQuote | None:
        normalized = index.strip().upper()
        if normalized not in {"NIFTY 50", "NIFTY50", "NSE:NIFTY50"}:
            return None
        snapshot = simulation_service.snapshot()
        event = simulation_service.get_market_event()
        change = Decimal(
            str(event.index_change_pct if event and event.index_change_pct is not None else 0)
        )
        previous = Decimal("25000")
        return IndexQuote(
            instrument="NSE:NIFTY50",
            index_name="Nifty 50",
            last_price=(previous * (Decimal("1") + change / 100)).quantize(Decimal("0.01")),
            previous_close=previous,
            change_pct=change,
            as_of=snapshot.as_of,
            provider=self.source,
            is_live=self.is_live,
        )

    async def get_sector_snapshot(self, sector: str) -> SectorSnapshot | None:
        snapshot = simulation_service.snapshot()
        match = next(
            (
                (name, move)
                for name, move in snapshot.sector_moves_pct.items()
                if name.casefold() == sector.strip().casefold()
            ),
            None,
        )
        if match is None:
            return None
        return SectorSnapshot(
            sector=match[0],
            change_pct=Decimal(str(match[1])),
            as_of=snapshot.as_of,
            provider=self.source,
            is_live=self.is_live,
        )

    async def get_market_snapshot(
        self, instruments: list[str] | None = None
    ) -> MarketSnapshot:
        portfolio = await self.portfolio.get_summary()
        selected = instruments or [holding.symbol for holding in portfolio.holdings]
        quotes = await self.get_quotes(selected)
        index = await self.get_index_quote("NIFTY 50")
        sectors: dict[str, SectorSnapshot] = {}
        for sector in simulation_service.snapshot().sector_moves_pct:
            item = await self.get_sector_snapshot(sector)
            if item:
                sectors[item.sector] = item
        as_of = simulation_service.snapshot().as_of
        clock = as_of.time()
        status = "pre_open" if clock < time(9, 15) else "open" if clock <= time(15, 30) else "closed"
        identity = sha256(
            f"{self.source}|{as_of.isoformat()}|{','.join(sorted(quotes))}".encode("utf-8")
        ).hexdigest()[:16]
        return MarketSnapshot(
            snapshot_id=f"market-{identity}",
            as_of=as_of,
            market_status=status,
            provider=self.source,
            is_live=self.is_live,
            quotes=quotes,
            indexes={index.instrument: index} if index else {},
            sectors=sectors,
        )

    async def get_volume(self, instrument: str) -> VolumeSnapshot | None:
        quote = await self.get_quote(instrument)
        if quote is None:
            return None
        event = simulation_service.get_market_event()
        symbol = quote.instrument.split(":", 1)[-1]
        change = Decimal("0")
        if event and event.symbol == symbol and event.volume_change_pct is not None:
            change = Decimal(str(event.volume_change_pct))
        baseline = 1_000_000
        return VolumeSnapshot(
            instrument=quote.instrument,
            volume=int(Decimal(baseline) * (Decimal("1") + change / 100)),
            baseline_volume=baseline,
            change_pct=change,
            as_of=quote.as_of,
            provider=self.source,
            is_live=self.is_live,
        )

    async def get_historical_prices(
        self,
        instrument: str,
        *,
        from_date: date,
        to_date: date,
        interval: str = "day",
    ) -> list[HistoricalPrice]:
        candles = await self.portfolio.get_historical_data(
            instrument, from_date, to_date, interval
        )
        return [
            HistoricalPrice(
                timestamp=item.timestamp,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=item.volume,
            )
            for item in candles
        ]
