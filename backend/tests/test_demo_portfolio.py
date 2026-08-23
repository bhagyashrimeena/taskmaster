from decimal import Decimal

import pytest

from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider


@pytest.fixture
def provider() -> DemoPortfolioProvider:
    return DemoPortfolioProvider()


async def test_holdings_are_complete_and_unique(provider: DemoPortfolioProvider) -> None:
    holdings = await provider.get_holdings()
    assert holdings
    assert len({holding.symbol for holding in holdings}) == len(holdings)
    for holding in holdings:
        assert holding.quantity > 0
        assert holding.average_price > 0
        assert holding.current_price > 0
        assert holding.market_value == holding.quantity * holding.current_price
        assert holding.invested_value == holding.quantity * holding.average_price
        assert holding.sector


async def test_portfolio_value_and_weights_are_consistent(provider: DemoPortfolioProvider) -> None:
    summary = await provider.get_summary()
    assert summary.source == "simulated"
    assert summary.provider == "simulated"
    assert summary.scenario_id == "hdfc-company-shock"
    assert summary.is_live is False
    assert summary.portfolio_value > 0
    assert sum(item.market_value for item in summary.holdings) == summary.portfolio_value
    assert Decimal("99.95") <= sum(item.portfolio_weight for item in summary.holdings) <= Decimal("100.05")
    assert summary.sector_exposure[0].portfolio_weight == max(
        item.portfolio_weight for item in summary.sector_exposure
    )


async def test_demo_quotes_are_deterministic(provider: DemoPortfolioProvider) -> None:
    quotes = await provider.get_quotes(["NSE:TCS", "INFY", "NSE:NOTREAL"])
    repeated = await provider.get_quotes(["NSE:TCS", "INFY"])
    assert quotes["NSE:TCS"].last_price == repeated["NSE:TCS"].last_price > 0
    assert quotes["NSE:INFY"].last_price == repeated["NSE:INFY"].last_price > 0
    assert "NSE:NOTREAL" not in quotes


async def test_checkpoint_weights_use_current_market_values(
    provider: DemoPortfolioProvider,
) -> None:
    from wealth_copilot.simulation import simulation_service

    simulation_service.advance_to("12:17")
    summary = await provider.get_summary()
    hdfc = next(item for item in summary.holdings if item.symbol == "HDFCBANK")
    financials = next(
        item for item in summary.sector_exposure
        if item.sector == "Financial Services"
    )

    assert hdfc.portfolio_weight == (
        hdfc.market_value / summary.portfolio_value * 100
    ).quantize(Decimal("0.01"))
    assert financials.portfolio_weight == (
        sum(
            (
                item.market_value
                if item.sector == "Financial Services"
                else Decimal("0")
            )
            + item.market_value
            * item.sector_lookthrough.get("Financial Services", Decimal("0"))
            / 100
            for item in summary.holdings
        )
        / summary.portfolio_value
        * 100
    ).quantize(Decimal("0.01"))
    assert Decimal("99.95") <= sum(
        item.portfolio_weight for item in summary.holdings
    ) <= Decimal("100.05")
