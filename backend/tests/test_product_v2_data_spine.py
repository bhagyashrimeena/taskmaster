from datetime import timedelta
from decimal import Decimal

import pytest

from wealth_copilot.config import Settings
from wealth_copilot.events import (
    EventDecisionEngine,
    EventWatcher,
    InMemoryMarketEventStream,
    get_event_fixture,
)
from wealth_copilot.events.memory import DailyEventStore
from wealth_copilot.market_data import DemoMarketDataProvider, get_market_data_provider
from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider
from wealth_copilot.simulation import simulation_service


@pytest.mark.asyncio
async def test_portfolio_v2_aggregates_are_calculated_from_current_values() -> None:
    provider = DemoPortfolioProvider()
    simulation_service.reset_scenario()
    summary = await provider.get_summary()

    assert summary.data_source_label == "Demo portfolio"
    assert summary.calculation_version == "portfolio-v2"
    assert sum(item.market_value for item in summary.holdings) == summary.portfolio_value
    assert abs(sum(item.market_value for item in summary.asset_allocation) - summary.portfolio_value) <= Decimal("0.01")
    assert abs(sum(item.market_value for item in summary.sector_exposure) - summary.portfolio_value) <= Decimal("0.10")
    assert all(
        item.portfolio_weight
        == (item.market_value / summary.portfolio_value * 100).quantize(Decimal("0.01"))
        for item in summary.holdings
    )
    assert any(item.sector_lookthrough for item in summary.holdings)


@pytest.mark.asyncio
async def test_market_data_is_separate_from_search_and_implements_full_contract() -> None:
    simulation_service.advance_to("12:17")
    provider = get_market_data_provider(Settings(market_data_provider="simulated"))
    assert isinstance(provider, DemoMarketDataProvider)

    quote = await provider.get_quote("HDFCBANK")
    assert quote and quote.provider == "demo_market_data" and quote.is_live is False
    assert (await provider.get_quotes(["HDFCBANK", "INFY"]))["NSE:HDFCBANK"] == quote
    assert len(await provider.get_intraday("HDFCBANK")) == 5
    assert (await provider.get_index_quote("NIFTY 50")).instrument == "NSE:NIFTY50"
    assert (await provider.get_sector_snapshot("Financial Services")).change_pct == Decimal("-0.8")
    snapshot = await provider.get_market_snapshot(["HDFCBANK", "INFY"])
    assert snapshot.provider == "demo_market_data"
    assert set(snapshot.quotes) == {"NSE:HDFCBANK", "NSE:INFY"}
    assert (await provider.get_volume("HDFCBANK")).change_pct == Decimal("185")
    history = await provider.get_historical_prices(
        "HDFCBANK",
        from_date=snapshot.as_of.date() - timedelta(days=7),
        to_date=snapshot.as_of.date(),
    )
    assert history and all(item.high >= item.low for item in history)


@pytest.mark.asyncio
async def test_generic_event_stream_and_engine_have_no_fixture_id_policy() -> None:
    original = get_event_fixture("hdfc-bank-sudden-fall")
    renamed = original.model_copy(
        update={
            "event_id": "generic-bank-anomaly",
            "instrument": "NSE:HDFCBANK",
            "metadata": {"provider_sequence": 42},
        }
    )
    stream = InMemoryMarketEventStream([renamed])
    engine = EventDecisionEngine(store=DailyEventStore())
    watcher = EventWatcher(
        stream=stream,
        portfolio=DemoPortfolioProvider(),
        decision_engine=engine,
    )

    assessments, cursor = await watcher.poll()
    assert cursor == "1"
    assert len(assessments) == 1
    assert assessments[0].event.event_id == "generic-bank-anomaly"
    assert assessments[0].event.symbol == "HDFCBANK"
    assert assessments[0].event.metadata["provider_sequence"] == 42
    assert assessments[0].notification_required is True
    assert (await stream.poll(cursor=cursor)).events == []
