"""Run the cold, cached, and forced-refresh Phase 1 acceptance flow."""

import asyncio
import argparse
import json
from pathlib import Path
import time

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from wealth_copilot.agent import root_agent  # noqa: E402
from wealth_copilot.agents.daily_brief_workflow import RANKED_RESULT_KEY  # noqa: E402
from wealth_copilot.market.cache import news_candidate_cache  # noqa: E402
from wealth_copilot.market.demo_provider import DemoNewsProvider  # noqa: E402


async def _ask(runner: InMemoryRunner, prompt: str) -> dict:
    started = time.perf_counter()
    calls: list[str] = []
    texts: list[str] = []
    async for event in runner.run_async(
        user_id="acceptance-user",
        session_id="acceptance-session",
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if not event.content:
            continue
        for part in event.content.parts or []:
            if part.function_call:
                calls.append(part.function_call.name)
            if part.text:
                texts.append(part.text)

    final = texts[-1] if texts else ""
    lowered = final.lower()
    session = await runner.session_service.get_session(
        app_name="phase1_acceptance",
        user_id="acceptance-user",
        session_id="acceptance-session",
    )
    ranked = json.loads(session.state[RANKED_RESULT_KEY]) if session else {}
    feed = ranked.get("data", {})
    stories = feed.get("stories", [])
    return {
        "prompt": prompt,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "tool_calls": calls,
        "response_length": len(final),
        "story_count": len(stories),
        "relevance_fields": sum("relevance_score" in story for story in stories),
        "utility_fields": sum("final_utility_score" in story for story in stories),
        "source_tier_fields": sum("source_authority" in story for story in stories),
        "news_cache_hit": ranked.get("news_cache_hit"),
        "mentions_cache_reuse": any(
            phrase in lowered for phrase in ("cache hit", "cached candidates", "reused")
        ),
        "mentions_fresh_fetch": any(
            phrase in lowered
            for phrase in ("cache miss", "freshly fetched", "not cached", "new search")
        ),
        "news_is_live": feed.get("news_is_live"),
    }


async def main(mode: str) -> None:
    news_candidate_cache.clear()
    runner = InMemoryRunner(agent=root_agent, app_name="phase1_acceptance")
    await runner.session_service.create_session(
        app_name="phase1_acceptance",
        user_id="acceptance-user",
        session_id="acceptance-session",
    )
    if mode == "refresh":
        # Preload a valid batch so this specifically proves that the explicit
        # refresh request bypasses an otherwise usable cache entry.
        news_candidate_cache.set(await DemoNewsProvider().get_candidates(limit=20))
        prompts = ["Refresh news and tell me what matters today."]
    else:
        prompts = [
            "What matters to me today?",
            "What matters to me today?",
            "Refresh news and tell me what matters today.",
        ]
    results = []
    try:
        for turn, prompt in enumerate(prompts, start=1):
            result = await _ask(runner, prompt)
            result["turn"] = turn
            results.append(result)
            print(json.dumps(result, ensure_ascii=True), flush=True)
    finally:
        await runner.close()

    for result in results:
        assert result["story_count"] == 5, result
        assert result["relevance_fields"] == 5, result
        assert result["utility_fields"] == 5, result
        assert result["source_tier_fields"] == 5, result
        assert "daily_brief_workflow" in result["tool_calls"], result
    if mode == "all":
        assert results[0]["news_cache_hit"] is False, results[0]
        assert results[1]["news_cache_hit"] is True, results[1]
        assert "refresh_news" in results[2]["tool_calls"], results[2]
        assert results[2]["news_cache_hit"] is False, results[2]
    else:
        assert "refresh_news" in results[0]["tool_calls"], results[0]
        assert results[0]["news_cache_hit"] is False, results[0]
    print(json.dumps({"status": "PASS", "turns": len(results)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "refresh"), default="all")
    args = parser.parse_args()
    asyncio.run(main(args.mode))
