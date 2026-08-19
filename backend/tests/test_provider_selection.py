import pytest

from wealth_copilot.config import Settings
from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider
from wealth_copilot.portfolio.provider import get_portfolio_provider
from wealth_copilot.portfolio.zerodha_provider import ZerodhaPortfolioProvider


def test_demo_provider_selection() -> None:
    provider = get_portfolio_provider(Settings(portfolio_provider="demo"))
    assert isinstance(provider, DemoPortfolioProvider)


@pytest.mark.asyncio
async def test_zerodha_provider_selection_does_not_connect() -> None:
    provider = get_portfolio_provider(Settings(portfolio_provider="zerodha"))
    assert isinstance(provider, ZerodhaPortfolioProvider)
    await provider.close()


def test_invalid_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTFOLIO_PROVIDER", "invalid")
    with pytest.raises(ValueError):
        Settings(_env_file=None)

