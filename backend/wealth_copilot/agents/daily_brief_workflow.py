"""Hybrid ADK workflow for the standard personalized daily brief."""

from collections.abc import AsyncGenerator
import json
import logging
import re
from time import perf_counter
from typing import Any

from google.adk.agents import Agent, BaseAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions

from ..config import get_settings
from ..market.cache import news_candidate_cache
from ..market.schemas import NewsCandidateBatch
from ..portfolio.schemas import PortfolioSummary
from ..relevance import DiversityRanker, RelevanceEngine
from .market_agent import MARKET_RESULT_KEY, market_agent
from .portfolio_agent import get_portfolio_summary


logger = logging.getLogger(__name__)
settings = get_settings()

PORTFOLIO_RESULT_KEY = "daily_brief_portfolio_result"
RANKED_RESULT_KEY = "daily_brief_ranked_result"
CACHE_HIT_KEY = "daily_brief_news_cache_hit"
NEWS_METADATA_KEY = "daily_brief_news_metadata"
START_TIME_KEY = "daily_brief_started_at"
PORTFOLIO_MS_KEY = "daily_brief_portfolio_ms"
MARKET_MS_KEY = "daily_brief_market_search_ms"
RELEVANCE_MS_KEY = "daily_brief_relevance_ms"
EXPLANATION_MS_KEY = "daily_brief_explanation_ms"
TOTAL_MS_KEY = "daily_brief_total_ms"


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("workflow state value is not JSON text")
    text = value.strip()
    # Gemini Search can emit ISO timestamps as bare tokens even when instructed
    # to return JSON. Repair only that narrow, unambiguous syntax before strict
    # Pydantic validation; all other malformed data is still rejected.
    text = re.sub(
        r'(:\s*)(\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?)(?=\s*[,}\]])',
        lambda match: f'{match.group(1)}"{match.group(2)}"',
        text,
    )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("workflow state does not contain a JSON object")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("workflow JSON must be an object")
    return parsed


def _start_workflow_timing(callback_context: Any) -> None:
    """Start one monotonic timer before the sequential workflow executes."""

    callback_context.state[START_TIME_KEY] = perf_counter()


class PortfolioSnapshotAgent(BaseAgent):
    """Portfolio-agent boundary that fetches structured data without an LLM turn."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        del ctx
        started = perf_counter()
        result = await get_portfolio_summary()
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    PORTFOLIO_RESULT_KEY: json.dumps(result, ensure_ascii=False),
                    PORTFOLIO_MS_KEY: round((perf_counter() - started) * 1000, 2),
                }
            ),
        )


class CachedMarketFetchAgent(BaseAgent):
    """Use a recent batch or invoke the Search-only Market Agent."""

    def _stale_fallback_event(self, exc: Exception, *, started: float) -> Event | None:
        stale = news_candidate_cache.snapshot()
        if stale is None:
            return None
        news_candidate_cache.finish_failed_refresh()
        logger.warning(
            "Market refresh failed (%s); serving %d stale candidate(s)",
            type(exc).__name__,
            len(stale.batch.candidates),
        )
        return Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    MARKET_RESULT_KEY: stale.batch.model_dump_json(),
                    CACHE_HIT_KEY: True,
                    MARKET_MS_KEY: round((perf_counter() - started) * 1000, 2),
                    NEWS_METADATA_KEY: json.dumps(
                        {
                            "news_status": "stale",
                            "fetched_at": stale.fetched_at.isoformat(),
                            "cache_age_seconds": round(stale.age_seconds, 2),
                            "refresh_attempted": True,
                            "refresh_error": type(exc).__name__,
                        }
                    ),
                }
            ),
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        started = perf_counter()
        cached = news_candidate_cache.get(ttl_seconds=settings.news_cache_ttl_seconds)
        if cached is not None:
            snapshot = news_candidate_cache.snapshot()
            logger.info("Daily brief news cache hit: %d candidate(s)", len(cached.candidates))
            yield Event(
                author=self.name,
                actions=EventActions(
                    state_delta={
                        MARKET_RESULT_KEY: cached.model_dump_json(),
                        CACHE_HIT_KEY: True,
                        MARKET_MS_KEY: 0.0,
                        NEWS_METADATA_KEY: json.dumps(
                            {
                                "news_status": "cached",
                                "fetched_at": snapshot.fetched_at.isoformat() if snapshot else None,
                                "cache_age_seconds": round(snapshot.age_seconds, 2) if snapshot else 0.0,
                                "refresh_attempted": False,
                            }
                        ),
                    }
                ),
            )
            return

        logger.info("Daily brief news cache miss; invoking Market Agent")
        last_text = ""
        child = self.sub_agents[0]
        try:
            async for event in child.run_async(ctx):
                if event.content and event.author == child.name:
                    texts = [part.text for part in event.content.parts or [] if part.text]
                    if texts:
                        last_text = "".join(texts)
                yield event
        except Exception as exc:
            fallback = self._stale_fallback_event(exc, started=started)
            if fallback is None:
                raise
            yield fallback
            return

        try:
            raw_result = ctx.session.state.get(MARKET_RESULT_KEY) or last_text
            batch = NewsCandidateBatch.model_validate(_json_object(raw_result))
        except Exception as exc:
            fallback = self._stale_fallback_event(exc, started=started)
            if fallback is None:
                raise
            yield fallback
            return
        news_candidate_cache.set(batch)
        snapshot = news_candidate_cache.snapshot()
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    MARKET_RESULT_KEY: batch.model_dump_json(),
                    CACHE_HIT_KEY: False,
                    MARKET_MS_KEY: round((perf_counter() - started) * 1000, 2),
                    NEWS_METADATA_KEY: json.dumps(
                        {
                            "news_status": "live" if batch.is_live else "cached",
                            "fetched_at": snapshot.fetched_at.isoformat() if snapshot else None,
                            "cache_age_seconds": 0.0,
                            "refresh_attempted": True,
                        }
                    ),
                }
            ),
        )


class DeterministicDailyRankAgent(BaseAgent):
    """Normalize, match, score, and diversify with no model call."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        started = perf_counter()
        try:
            portfolio_result = _json_object(ctx.session.state.get(PORTFOLIO_RESULT_KEY))
            if portfolio_result.get("status") != "ok":
                raise ValueError(portfolio_result.get("error") or "portfolio unavailable")
            portfolio = PortfolioSummary.model_validate(portfolio_result["data"])

            batch = NewsCandidateBatch.model_validate(
                _json_object(ctx.session.state.get(MARKET_RESULT_KEY))
            )
            relevance_feed = RelevanceEngine().rank(
                batch.candidates,
                portfolio,
                news_source=batch.source,
                news_is_live=batch.is_live,
                limit=20,
            )
            final_feed = DiversityRanker().select(relevance_feed, limit=5)
            metadata = _json_object(ctx.session.state.get(NEWS_METADATA_KEY))
            relevance_ms = round((perf_counter() - started) * 1000, 2)
            result = {
                "status": "ok",
                "news_cache_hit": bool(ctx.session.state.get(CACHE_HIT_KEY, False)),
                **metadata,
                "timing": {
                    "portfolio_ms": float(ctx.session.state.get(PORTFOLIO_MS_KEY, 0.0)),
                    "market_search_ms": float(ctx.session.state.get(MARKET_MS_KEY, 0.0)),
                    "relevance_ms": relevance_ms,
                    "explanation_ms": None,
                    "total_ms": None,
                    "cache_hit": bool(ctx.session.state.get(CACHE_HIT_KEY, False)),
                },
                "data": final_feed.model_dump(mode="json"),
            }
            logger.info(
                "Deterministic daily rank selected %d of %d normalized candidate(s)",
                len(final_feed.stories),
                final_feed.deduplicated_count,
            )
        except Exception as exc:
            logger.warning("Daily brief deterministic stage failed: %s", type(exc).__name__)
            result = {
                "status": "error",
                "error": f"Unable to build daily brief: {exc}",
            }
            relevance_ms = round((perf_counter() - started) * 1000, 2)

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    RANKED_RESULT_KEY: json.dumps(result, ensure_ascii=False),
                    RELEVANCE_MS_KEY: relevance_ms,
                }
            ),
        )


class TimedExplanationAgent(BaseAgent):
    """Run the single explanation call and finalize workflow telemetry."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        started = perf_counter()
        child = self.sub_agents[0]
        async for event in child.run_async(ctx):
            yield event

        explanation_ms = round((perf_counter() - started) * 1000, 2)
        workflow_started = float(ctx.session.state.get(START_TIME_KEY, started))
        total_ms = round((perf_counter() - workflow_started) * 1000, 2)
        result = _json_object(ctx.session.state.get(RANKED_RESULT_KEY))
        timing = result.setdefault("timing", {})
        timing["explanation_ms"] = explanation_ms
        timing["total_ms"] = total_ms
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    RANKED_RESULT_KEY: json.dumps(result, ensure_ascii=False),
                    EXPLANATION_MS_KEY: explanation_ms,
                    TOTAL_MS_KEY: total_ms,
                }
            ),
        )


portfolio_snapshot_agent = PortfolioSnapshotAgent(
    name="daily_portfolio_fetch",
    description="Fetches the active normalized portfolio without model reasoning.",
)

cached_market_fetch_agent = CachedMarketFetchAgent(
    name="daily_market_fetch",
    description="Returns cached candidates or invokes the Search-only Market Agent.",
    sub_agents=[market_agent],
)

parallel_fetch_agent = ParallelAgent(
    name="daily_parallel_fetch",
    description="Fetches portfolio and market candidates concurrently.",
    sub_agents=[portfolio_snapshot_agent, cached_market_fetch_agent],
)

deterministic_rank_agent = DeterministicDailyRankAgent(
    name="daily_deterministic_rank",
    description="Runs normalization, matching, relevance, source quality, and diversity code.",
)

explanation_agent = Agent(
    name="daily_brief_explainer",
    model=settings.adk_model,
    description="Explains the already-selected top five without changing deterministic results.",
    include_contents="none",
    instruction=(
        "You are Wealth Copilot's final daily-brief explainer. The deterministic workflow result is below.\n"
        f"{{{RANKED_RESULT_KEY}}}\n"
        "If status is error, state the error concisely. Otherwise render exactly the stories supplied, in their "
        "existing order. Do not add, remove, rerank, or rescore anything. Start by independently labeling the "
        "portfolio source, news_status, fetched_at, cache_age_seconds, refresh_attempted, and whether "
        "news_cache_hit shows cached candidates were reused; "
        "do not confuse a demo portfolio with live news. For every "
        "story show headline, concise summary, clickable source, publication time, affected holdings, direct "
        "exposure, sector exposure, relevance score, final utility score, source-authority tier, and 'Why am I "
        "seeing this?'. Explain only from the supplied fields. Do not recommend trades or claim to send alerts."
    ),
)

timed_explanation_agent = TimedExplanationAgent(
    name="daily_timed_explanation",
    description="Times the one Gemini explanation call and completes telemetry.",
    sub_agents=[explanation_agent],
)

daily_brief_workflow = SequentialAgent(
    name="daily_brief_workflow",
    description=(
        "Deterministic daily-brief workflow: parallel fetch, code ranking/diversity, one explanation call."
    ),
    sub_agents=[
        parallel_fetch_agent,
        deterministic_rank_agent,
        timed_explanation_agent,
    ],
    before_agent_callback=_start_workflow_timing,
)


__all__ = [
    "CACHE_HIT_KEY",
    "MARKET_RESULT_KEY",
    "NEWS_METADATA_KEY",
    "PORTFOLIO_RESULT_KEY",
    "RANKED_RESULT_KEY",
    "daily_brief_workflow",
]
