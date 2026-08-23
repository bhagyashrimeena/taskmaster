import asyncio
from datetime import datetime, timezone
import re

from fastapi.testclient import TestClient
from google.adk.tools.agent_tool import AgentTool

from wealth_copilot.agents.research_agent import research_agent
from wealth_copilot.config import application_today
from wealth_copilot.day.schemas import DayRunMode
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.agents.taskmaster import root_agent
from wealth_copilot.api import app
from wealth_copilot.interaction.context import resolve_surface_context
from wealth_copilot.interaction.memory import (
    conversation_store,
    daily_interaction_store,
    persistent_memory_store,
)
from wealth_copilot.interaction.research_jobs import ResearchJobManager
from wealth_copilot.interaction.schemas import (
    ConversationRequest,
    InteractionMode,
    ResearchRequest,
    SurfaceContext,
)
from wealth_copilot.interaction.service import InteractionService
from wealth_copilot.interaction.service import _grounding_sources
from wealth_copilot.simulation import simulation_service


def _release_demo_event() -> None:
    financial_day_store.update(
        lambda state: setattr(state, "run_mode", DayRunMode.DEMO)
    )
    simulation_service.advance_to("12:17")


async def _fake_taskmaster(prompt: str, timeout: float):
    assert timeout > 0
    assert "RETAINED_CONTEXT" in prompt
    return "Facts: retained evidence. Context / interpretation: relevant to your portfolio.", [
        "TaskMaster started",
        "taskmaster responded",
        "TaskMaster completed",
    ]


async def test_explain_uses_stable_item_context_and_follow_up_history() -> None:
    conversation_store.clear()
    service = InteractionService(invoker=_fake_taskmaster)
    first = await service.respond(
        ConversationRequest(
            message="Why am I seeing this?",
            mode=InteractionMode.EXPLAIN,
            active_story_id="hdfc-rbi",
        )
    )
    second = await service.respond(
        ConversationRequest(
            conversation_id=first.conversation_id,
            message="What is the key uncertainty?",
        )
    )

    assert first.context.target_id == "hdfc-rbi"
    assert first.used_existing_context is True
    assert first.used_search is False
    assert first.fallback_used is False
    assert second.context.target_id == "hdfc-rbi"
    assert len(conversation_store.get(first.conversation_id).history) == 4


async def test_long_term_memory_is_recalled_in_follow_up_prompt() -> None:
    prompts: list[str] = []

    async def capture(prompt: str, timeout: float):
        del timeout
        prompts.append(prompt)
        return "I remember your earlier context.", ["TaskMaster completed"]

    service = InteractionService(invoker=capture)
    first = await service.respond(
        ConversationRequest(
            message="My name is Tanaya and I prefer concise answers.",
            mode=InteractionMode.CHAT,
        )
    )
    second = await service.respond(
        ConversationRequest(
            conversation_id=first.conversation_id,
            message="What do you remember about me?",
            mode=InteractionMode.CHAT,
        )
    )

    assert second.conversation_id == first.conversation_id
    assert "MEMORY_PROFILE:" in prompts[-1]
    assert "LONG_TERM_MEMORY:" in prompts[-1]
    assert "User's name is Tanaya." in prompts[-1]
    assert "User preference: concise answers." in prompts[-1]


def test_persistent_memory_store_extracts_and_recalls_user_facts() -> None:
    persistent_memory_store.remember_exchange(
        conversation_id="c1",
        user_message="I live in Mumbai and my goal is to understand portfolio risk better.",
        assistant_message="I'll keep that in mind.",
        mode="chat",
        context=SurfaceContext(
            target_type="dashboard",
            title="Today",
            portfolio_as_of=datetime.now(timezone.utc),
            source_checkpoint="07:00",
            facts=["Portfolio context"],
            interpretation=["Context"],
            unknowns=["Unknown"],
            sources=[],
            portfolio_context="Portfolio value INR 1.00",
        ),
    )

    recalled = persistent_memory_store.recall(
        conversation_id="c1",
        query="Where am I based and what are my goals?",
        context=SurfaceContext(
            target_type="dashboard",
            title="Today",
            portfolio_as_of=datetime.now(timezone.utc),
            source_checkpoint="07:00",
            facts=["Portfolio context"],
            interpretation=["Context"],
            unknowns=["Unknown"],
            sources=[],
            portfolio_context="Portfolio value INR 1.00",
        ),
    )

    assert any("User goal:" in item.text for item in recalled)
    assert any("User is based in Mumbai." in item.text for item in recalled)


async def test_text_voice_and_call_modes_share_the_taskmaster_path() -> None:
    prompts: list[str] = []

    async def capture(prompt: str, timeout: float):
        del timeout
        prompts.append(prompt)
        return "The same retained portfolio context was used.", ["TaskMaster completed"]

    service = InteractionService(invoker=capture)
    for mode in (InteractionMode.TEXT, InteractionMode.VOICE, InteractionMode.CALL):
        response = await service.respond(ConversationRequest(message="What changed?", mode=mode))
        assert response.route == "taskmaster"
        assert response.mode == mode
        assert response.used_existing_context is True

    assert [f"MODE: {mode.value}" in prompt for mode, prompt in zip(
        (InteractionMode.TEXT, InteractionMode.VOICE, InteractionMode.CALL), prompts, strict=True
    )] == [True, True, True]
    assert "VOICE_CONTEXT: none" in prompts[0]
    assert '"top_holdings"' in prompts[1]
    assert '"relevant_stories"' in prompts[2]


async def test_event_context_separates_facts_interpretation_and_sources() -> None:
    _release_demo_event()
    context = await resolve_surface_context(event_id="hdfc-bank-sudden-fall")

    assert context.target_type == "event"
    assert any("5.4%" in fact for fact in context.facts)
    assert context.interpretation
    assert context.unknowns
    assert len(context.sources) >= 3


async def test_story_context_uses_one_timestamped_portfolio_snapshot() -> None:
    simulation_service.advance_to("07:00")
    morning = await resolve_surface_context(story_id="hdfc-rbi")

    assert morning.source_checkpoint == "07:00"
    assert morning.portfolio_as_of.strftime("%H:%M") == "07:00"
    assert any(
        "At the 07:00 portfolio snapshot, direct exposure is" in fact
        and "sector exposure is" in fact
        for fact in morning.facts
    )
    assert any("Deterministic relevance score" in fact for fact in morning.facts)

    simulation_service.advance_to("12:17")
    noon = await resolve_surface_context(story_id="hdfc-rbi")

    assert noon.source_checkpoint == "12:17"
    assert noon.portfolio_as_of.strftime("%H:%M") == "12:17"
    assert any(
        "At the 12:17 portfolio snapshot, direct exposure is" in fact
        and "sector exposure is" in fact
        for fact in noon.facts
    )
    assert any("Deterministic relevance score" in fact for fact in noon.facts)


async def test_event_context_exposure_matches_1217_provenance() -> None:
    _release_demo_event()
    context = await resolve_surface_context(event_id="hdfc-bank-sudden-fall")

    assert context.source_checkpoint == "12:17"
    assert context.portfolio_as_of.strftime("%H:%M") == "12:17"
    assert any(
        "At the 12:17 portfolio snapshot, your direct exposure is" in fact
        and "sector exposure is" in fact
        for fact in context.facts
    )
    assert any(
        "Deterministic relevance score:" in fact and "attention decision: ALERT" in fact
        for fact in context.facts
    )


async def test_taskmaster_has_research_specialist() -> None:
    specialists = {
        tool.agent.name for tool in root_agent.tools if isinstance(tool, AgentTool)
    }
    assert research_agent.name in specialists


async def test_research_job_runs_through_research_mode() -> None:
    _release_demo_event()
    calls = []

    async def research_invoker(prompt: str, timeout: float):
        calls.append((prompt, timeout))
        return "Facts: confirmed. Sources: https://example.com/filing", ["TaskMaster completed"]

    manager = ResearchJobManager(InteractionService(invoker=research_invoker))
    job = manager.start(ResearchRequest(active_event_id="hdfc-bank-sudden-fall"))
    current = None
    for _ in range(20):
        await asyncio.sleep(0.01)
        current = manager.get(job.job_id)
        if current and current.result:
            break
    assert current is not None and current.result is not None
    assert current.status.value == "complete"
    assert current.result.route == "research_agent"
    assert any(source.url == "https://example.com/filing" for source in current.result.sources)
    assert "delegate to research_agent" in calls[0][0]


async def test_model_failure_returns_existing_context_without_search() -> None:
    _release_demo_event()
    async def unavailable(prompt: str, timeout: float):
        del prompt, timeout
        raise RuntimeError("quota")

    result = await InteractionService(invoker=unavailable).respond(
        ConversationRequest(
            message="Explain this event",
            mode=InteractionMode.EXPLAIN,
            active_event_id="hdfc-bank-sudden-fall",
        )
    )
    assert result.fallback_used is True
    assert result.used_search is False
    assert "retained context" in result.agent_trace[-1].lower()


async def test_portfolio_fallback_retains_largest_holdings() -> None:
    async def unavailable(prompt: str, timeout: float):
        del prompt, timeout
        raise TimeoutError

    result = await InteractionService(invoker=unavailable).respond(
        ConversationRequest(message="Which holding is my largest exposure?")
    )
    assert result.route == "portfolio_agent"
    assert any("HDFCBANK" in fact for fact in result.context.facts)


async def test_unsafe_model_instruction_is_removed() -> None:
    async def unsafe(prompt: str, timeout: float):
        del prompt, timeout
        return "You should sell this now. Here are the facts.", []

    result = await InteractionService(invoker=unsafe).respond(
        ConversationRequest(message="What now?", active_story_id="hdfc-rbi")
    )
    assert re.search(r"\byou should (?:buy|sell|hold)\b", result.answer, re.I) is None
    assert "investment instructions" in result.answer


async def test_markdown_and_action_disclaimer_are_normalized() -> None:
    async def markdown(prompt: str, timeout: float):
        del prompt, timeout
        return "### **Facts**\n> * Confirmed.\nThis does not constitute investment advice or a recommendation to buy or sell.", []

    result = await InteractionService(invoker=markdown).respond(
        ConversationRequest(message="Explain", active_story_id="hdfc-rbi")
    )
    assert "**" not in result.answer
    assert "###" not in result.answer
    assert ">" not in result.answer
    assert re.search(r"\b(buy|sell|hold)\b", result.answer, re.I) is None


async def test_markdown_links_become_readable_plain_text() -> None:
    async def markdown_link(prompt: str, timeout: float):
        del prompt, timeout
        return "[Official filing](https://example.com/filing)", []

    result = await InteractionService(invoker=markdown_link).respond(
        ConversationRequest(message="Explain", active_story_id="hdfc-rbi")
    )
    assert result.answer == "Official filing — https://example.com/filing"


def test_structured_grounding_sources_are_deduplicated_and_preserve_citation() -> None:
    sources = _grounding_sources(
        {
            "grounding_chunks": [
                {"web": {"title": "RBI", "uri": "https://rbi.org.in/notice"}},
                {"web": {"title": "RBI duplicate", "uri": "https://rbi.org.in/notice"}},
                {"web": {"title": "Grounding redirect", "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/test"}},
            ]
        }
    )

    assert len(sources) == 2
    assert sources[0].canonical_url == "https://rbi.org.in/notice"
    assert sources[1].canonical_url is None
    assert sources[1].citation_uri.startswith("https://vertexaisearch.cloud.google.com/")


def test_story_save_feedback_and_daily_state_http_contract() -> None:
    daily_interaction_store.clear()
    client = TestClient(app)

    saved = client.post("/api/v1/stories/hdfc-rbi/save")
    feedback = client.post(
        "/api/v1/feedback",
        json={"target_type": "story", "target_id": "hdfc-rbi", "value": "useful"},
    )
    dashboard = client.get("/api/v1/dashboard").json()

    assert saved.status_code == 200
    assert saved.json()["saved_for"] == application_today().isoformat()
    assert feedback.status_code == 200
    assert "hdfc-rbi" in dashboard["daily_state"]["saved_story_ids"]
    assert dashboard["daily_state"]["feedback"]["story:hdfc-rbi"] == "useful"


def test_unknown_story_is_rejected() -> None:
    response = TestClient(app).post("/api/v1/stories/not-real/save")
    assert response.status_code == 404
