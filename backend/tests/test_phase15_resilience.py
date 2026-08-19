import json

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.runners import InMemoryRunner
from google.genai import types

from wealth_copilot.agents.daily_brief_workflow import (
    CACHE_HIT_KEY,
    MARKET_RESULT_KEY,
    NEWS_METADATA_KEY,
    CachedMarketFetchAgent,
)
from wealth_copilot.market.cache import news_candidate_cache, refresh_news
from wealth_copilot.market.demo_provider import DemoNewsProvider


class _FailingMarketAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        del ctx
        if False:
            yield
        raise RuntimeError("simulated Search failure")


async def test_forced_refresh_uses_retained_stale_batch_when_search_fails() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15)
    news_candidate_cache.set(batch)
    refresh_result = refresh_news()
    assert refresh_result["stale_fallback_available"] is True
    assert news_candidate_cache.get(ttl_seconds=900) is None

    agent = CachedMarketFetchAgent(
        name="stale_fallback_test",
        sub_agents=[_FailingMarketAgent(name="failing_market")],
    )
    runner = InMemoryRunner(agent=agent, app_name="stale_fallback_test")
    await runner.session_service.create_session(
        app_name="stale_fallback_test", user_id="test", session_id="test"
    )
    try:
        async for _ in runner.run_async(
            user_id="test",
            session_id="test",
            new_message=types.Content(role="user", parts=[types.Part(text="refresh")]),
        ):
            pass
        session = await runner.session_service.get_session(
            app_name="stale_fallback_test", user_id="test", session_id="test"
        )
        cache_available_after = news_candidate_cache.get(ttl_seconds=900) is not None
    finally:
        await runner.close()
        news_candidate_cache.clear()

    metadata = json.loads(session.state[NEWS_METADATA_KEY])
    assert session.state[CACHE_HIT_KEY] is True
    assert json.loads(session.state[MARKET_RESULT_KEY])["source"] == "simulated_scenario_news"
    assert metadata["news_status"] == "stale"
    assert metadata["refresh_attempted"] is True
    assert metadata["refresh_error"] == "RuntimeError"
    assert cache_available_after is True
