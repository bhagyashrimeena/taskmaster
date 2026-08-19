import json

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from pydantic import PrivateAttr

from wealth_copilot.agent import root_agent
from wealth_copilot.agents.daily_brief_workflow import (
    RANKED_RESULT_KEY,
    _json_object,
    daily_brief_workflow,
    explanation_agent,
    parallel_fetch_agent,
)
from wealth_copilot.agents.portfolio_agent import (
    get_portfolio_summary,
    portfolio_agent,
)
from wealth_copilot.agents.research_agent import research_agent
from wealth_copilot.agents.media_agent import media_agent
from wealth_copilot.market.cache import news_candidate_cache, refresh_news
from wealth_copilot.market.demo_provider import DemoNewsProvider


def test_root_agent_is_discoverable() -> None:
    assert isinstance(root_agent, Agent)
    assert root_agent.name == "taskmaster"
    agent_tools = [tool for tool in root_agent.tools if isinstance(tool, AgentTool)]
    assert {tool.agent.name for tool in agent_tools} == {
        portfolio_agent.name,
        daily_brief_workflow.name,
        research_agent.name,
        media_agent.name,
    }
    workflow_tool = next(tool for tool in agent_tools if tool.agent is daily_brief_workflow)
    assert workflow_tool.skip_summarization is True


def test_daily_brief_has_explicit_parallel_then_sequential_workflow() -> None:
    assert isinstance(daily_brief_workflow, SequentialAgent)
    assert isinstance(parallel_fetch_agent, ParallelAgent)
    assert daily_brief_workflow.sub_agents[0] is parallel_fetch_agent
    assert [agent.name for agent in parallel_fetch_agent.sub_agents] == [
        "daily_portfolio_fetch",
        "daily_market_fetch",
    ]


def test_market_json_parser_repairs_only_bare_iso_timestamps() -> None:
    parsed = _json_object(
        '{"source":"search","is_live":true,"generated_at": '
        '2026-08-17T11:30:00+05:30,"candidates":[]}'
    )
    assert parsed["generated_at"] == "2026-08-17T11:30:00+05:30"


async def test_local_demo_tool_returns_structured_data() -> None:
    result = await get_portfolio_summary()
    assert result["status"] == "ok"
    assert result["source"] == "simulated"
    assert result["data"]["portfolio_value"] == "841999.80"
    assert result["data"]["holdings"][0]["symbol"] == "HDFCBANK"


class _ToolCallingModel(BaseLlm):
    """Deterministic model double that forces one real ADK function call."""

    _calls: int = PrivateAttr(default=0)

    async def generate_content_async(self, llm_request, stream: bool = False):
        del llm_request, stream
        self._calls += 1
        if self._calls == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_function_call(
                            name="get_portfolio_summary", args={}
                        )
                    ],
                )
            )
        else:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="Demo portfolio is available.")],
                )
            )


class _ExplanationModel(BaseLlm):
    async def generate_content_async(self, llm_request, stream: bool = False):
        del llm_request, stream
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="Five-story daily brief rendered.")],
            )
        )


async def test_daily_workflow_state_handoff_and_deterministic_rank() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15)
    news_candidate_cache.set(batch)
    original_model = explanation_agent.model
    explanation_agent.model = _ExplanationModel(model="deterministic-explanation-model")
    try:
        runner = InMemoryRunner(agent=daily_brief_workflow, app_name="daily_workflow_smoke")
        await runner.session_service.create_session(
            app_name="daily_workflow_smoke", user_id="test-user", session_id="test-session"
        )
        ranked_payload = None
        async for event in runner.run_async(
            user_id="test-user",
            session_id="test-session",
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text="What matters today?")]
            ),
        ):
            if RANKED_RESULT_KEY in event.actions.state_delta:
                ranked_payload = json.loads(event.actions.state_delta[RANKED_RESULT_KEY])
        session = await runner.session_service.get_session(
            app_name="daily_workflow_smoke",
            user_id="test-user",
            session_id="test-session",
        )
        final_ranked_payload = json.loads(session.state[RANKED_RESULT_KEY])
        await runner.close()
    finally:
        explanation_agent.model = original_model
        news_candidate_cache.clear()

    assert ranked_payload is not None
    assert ranked_payload["status"] == "ok"
    assert ranked_payload["news_cache_hit"] is True
    assert len(ranked_payload["data"]["stories"]) == 5
    assert all(story["final_utility_score"] > 0 for story in ranked_payload["data"]["stories"])
    assert final_ranked_payload["news_status"] == "cached"
    assert final_ranked_payload["fetched_at"]
    assert final_ranked_payload["cache_age_seconds"] >= 0
    assert final_ranked_payload["refresh_attempted"] is False
    timing = final_ranked_payload["timing"]
    assert set(timing) == {
        "portfolio_ms",
        "market_search_ms",
        "relevance_ms",
        "explanation_ms",
        "total_ms",
        "cache_hit",
    }
    assert timing["total_ms"] >= timing["explanation_ms"] >= 0
    assert timing["cache_hit"] is True


async def test_refresh_news_invalidates_an_existing_candidate_batch() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15)
    news_candidate_cache.set(batch)
    assert news_candidate_cache.get(ttl_seconds=900) is not None

    result = refresh_news()

    assert result["status"] == "ok"
    assert news_candidate_cache.get(ttl_seconds=900) is None


async def test_adk_runner_executes_local_portfolio_tool() -> None:
    model = _ToolCallingModel(model="deterministic-test-model")
    agent = Agent(
        name="portfolio_tool_smoke",
        model=model,
        instruction="Use the portfolio summary tool.",
        tools=[get_portfolio_summary],
    )
    runner = InMemoryRunner(agent=agent, app_name="portfolio_tool_smoke")
    await runner.session_service.create_session(
        app_name="portfolio_tool_smoke", user_id="test-user", session_id="test-session"
    )

    events = []
    async for event in runner.run_async(
        user_id="test-user",
        session_id="test-session",
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text="Show my portfolio.")]
        ),
    ):
        events.append(event)

    responses = [
        part.function_response.response
        for event in events
        if event.content
        for part in event.content.parts
        if part.function_response
    ]
    assert model._calls == 2
    assert responses[0]["status"] == "ok"
    assert responses[0]["data"]["portfolio_value"] == "841999.80"
