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
    assert summary.portfolio_value == Decimal("841999.80")
    assert sum(item.market_value for item in summary.holdings) == summary.portfolio_value
    assert Decimal("99.95") <= sum(item.portfolio_weight for item in summary.holdings) <= Decimal("100.05")
    assert summary.sector_exposure[0].sector == "Information Technology"
    assert summary.sector_exposure[0].portfolio_weight == Decimal("32.00")


async def test_demo_quotes_are_deterministic(provider: DemoPortfolioProvider) -> None:
    quotes = await provider.get_quotes(["NSE:TCS", "INFY", "NSE:NOTREAL"])
    assert quotes["NSE:TCS"].last_price == Decimal("4041.60")
    assert quotes["NSE:INFY"].last_price == Decimal("1473.50")
    assert "NSE:NOTREAL" not in quotes
