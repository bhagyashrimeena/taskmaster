"""Portfolio specialist and provider-backed local ADK tools."""

from datetime import date
import logging
from typing import Any

from google.adk.agents import Agent

from ..config import get_settings
from ..portfolio.provider import (
    PortfolioAuthenticationRequired,
    PortfolioProviderError,
    get_portfolio_provider,
)
from ..portfolio.schemas import ToolResult


logger = logging.getLogger(__name__)
settings = get_settings()
provider = get_portfolio_provider(settings)


def _ok(data: Any) -> dict[str, Any]:
    payload = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
    return ToolResult(status="ok", source=provider.source, data=payload).model_dump(mode="json")


def _error(exc: Exception) -> dict[str, Any]:
    auth = isinstance(exc, PortfolioAuthenticationRequired)
    return ToolResult(
        status="authentication_required" if auth else "error",
        source=provider.source,
        error=str(exc),
        suggestion=(
            "Complete Zerodha login in the browser and retry in this same ADK session."
            if auth
            else "Check the provider connection, or set PORTFOLIO_PROVIDER=simulated for local development."
        ),
    ).model_dump(mode="json")


async def get_portfolio_summary() -> dict[str, Any]:
    """Return the active user's normalized portfolio, totals, P&L, weights, and sectors."""

    logger.info("Portfolio tool called: get_portfolio_summary")
    try:
        return _ok(await provider.get_summary())
    except PortfolioProviderError as exc:
        logger.warning("Portfolio summary failed: %s", type(exc).__name__)
        return _error(exc)


async def login_to_zerodha() -> dict[str, Any]:
    """Start Zerodha's browser login flow when the active provider is zerodha."""

    logger.info("Portfolio tool called: login_to_zerodha")
    login = getattr(provider, "login", None)
    if login is None:
        return ToolResult(
            status="error",
            source=provider.source,
            error="Zerodha login is unavailable because PORTFOLIO_PROVIDER is not zerodha.",
            suggestion="Keep simulated mode for safe demo data, or configure a future authorized provider.",
        ).model_dump(mode="json")
    try:
        return _ok(await login())
    except PortfolioProviderError as exc:
        return _error(exc)


async def get_portfolio_holdings() -> dict[str, Any]:
    """Return normalized holdings from the configured portfolio provider."""

    logger.info("Portfolio tool called: get_portfolio_holdings")
    try:
        holdings = await provider.get_holdings()
        return _ok([item.model_dump(mode="json") for item in holdings])
    except PortfolioProviderError as exc:
        return _error(exc)


async def get_portfolio_positions() -> dict[str, Any]:
    """Return current normalized positions from the configured provider."""

    logger.info("Portfolio tool called: get_portfolio_positions")
    try:
        positions = await provider.get_positions()
        return _ok([item.model_dump(mode="json") for item in positions])
    except PortfolioProviderError as exc:
        return _error(exc)


async def get_portfolio_quotes(instruments: list[str]) -> dict[str, Any]:
    """Return quotes for exchange:symbol instruments, for example NSE:TCS."""

    logger.info("Portfolio tool called: get_portfolio_quotes")
    try:
        quotes = await provider.get_quotes(instruments)
        return _ok({key: value.model_dump(mode="json") for key, value in quotes.items()})
    except PortfolioProviderError as exc:
        return _error(exc)


async def get_portfolio_history(
    symbol: str, from_date: str, to_date: str, interval: str = "day"
) -> dict[str, Any]:
    """Return historical candles for a symbol and ISO date range."""

    logger.info("Portfolio tool called: get_portfolio_history")
    try:
        candles = await provider.get_historical_data(
            symbol=symbol,
            from_date=date.fromisoformat(from_date),
            to_date=date.fromisoformat(to_date),
            interval=interval,
        )
        return _ok([item.model_dump(mode="json") for item in candles])
    except (PortfolioProviderError, ValueError) as exc:
        return _error(exc)


def create_portfolio_agent() -> Agent:
    return Agent(
        name="portfolio_agent",
        model=settings.adk_model,
        description="Handles read-only portfolio, position, quote, and price-history questions.",
        instruction=(
            "You are Wealth Copilot's Portfolio Agent. This phase handles portfolio information only. "
            "Always use a tool for user-specific values; never invent holdings or prices. "
            "The tool result's source field identifies its provider. Clearly label simulated data "
            "and live-data failures as unavailable. Never place trades or recommend executing a trade. "
            "Prefer concise explanations in INR and calculate percentages from tool data."
        ),
        tools=[
            login_to_zerodha,
            get_portfolio_summary,
            get_portfolio_holdings,
            get_portfolio_positions,
            get_portfolio_quotes,
            get_portfolio_history,
        ],
    )


portfolio_agent = create_portfolio_agent()
