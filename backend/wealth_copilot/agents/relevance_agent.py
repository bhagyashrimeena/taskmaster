"""Relevance Agent backed by the deterministic scoring engine."""

from datetime import datetime, timezone
import logging
from typing import Any

from google.adk.agents import Agent

from ..config import get_settings
from ..relevance.engine import RelevanceEngine
from .portfolio_agent import provider as portfolio_provider


logger = logging.getLogger(__name__)
settings = get_settings()
engine = RelevanceEngine()


async def rank_personalized_news(
    candidates: list[dict[str, Any]],
    news_is_live: bool,
    news_source: str = "market_intelligence_agent",
    limit: int = 5,
) -> dict[str, Any]:
    """Normalize, portfolio-match, deterministically score, and rank candidate news."""

    logger.info("Relevance tool called with %d candidate(s)", len(candidates))
    try:
        portfolio = await portfolio_provider.get_summary()
        feed = engine.rank(
            candidates,
            portfolio,
            news_source=news_source,
            news_is_live=news_is_live,
            limit=limit,
            now=datetime.now(timezone.utc),
        )
        return {"status": "ok", "data": feed.model_dump(mode="json")}
    except Exception as exc:
        logger.warning("Relevance ranking failed: %s", type(exc).__name__)
        return {
            "status": "error",
            "error": f"Unable to rank candidate news: {exc}",
            "suggestion": "Check candidate schema/source fields and portfolio-provider availability.",
        }


def create_relevance_agent() -> Agent:
    return Agent(
        name="relevance_agent",
        model=settings.adk_model,
        description=(
            "Normalizes and ranks market candidates against the active portfolio using "
            "an explainable deterministic scoring tool, then explains the top five."
        ),
        instruction=(
            "You are Wealth Copilot's Relevance Agent. You receive candidate-news JSON. Always call "
            "rank_personalized_news with the complete candidate list, the input source, the input is_live "
            "value as news_is_live, and limit=5; never score stories "
            "yourself. Preserve every headline, source name, source URL, publication time, exposure, signal "
            "component, and deterministic relevance score exactly. For each returned story, add a concise "
            "plain-language interpretation of why the relationship matters, grounded only in the returned "
            "signals. Do not recommend trades. notification_required is an inert Phase 1 calculation only; "
            "never send or claim to send a notification. Return exactly the five ranked stories when five exist."
        ),
        tools=[rank_personalized_news],
    )


relevance_agent = create_relevance_agent()
