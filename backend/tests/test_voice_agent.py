"""The LiveKit worker must remain a transport over the canonical Copilot service."""

from types import SimpleNamespace

import pytest
from livekit.agents import AgentSession

from wealth_copilot.interaction.memory import conversation_store
from wealth_copilot.interaction.schemas import InteractionMode
from wealth_copilot.simulation import simulation_service
from wealth_copilot.day.schemas import DayRunMode
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.voice.agent import (
    TaskMasterTransportLLM,
    TaskMasterVoiceAgent,
    _metadata,
)
from wealth_copilot.voice.context import build_voice_context


class StubInteractionService:
    def __init__(self) -> None:
        self.requests = []

    async def respond(self, request):
        self.requests.append(request)
        conversation_store.append(request.conversation_id, "user", request.message)
        conversation_store.append(
            request.conversation_id,
            "assistant",
            f"TaskMaster answer for: {request.message}",
        )
        return SimpleNamespace(
            conversation_id=request.conversation_id or "voice-conversation",
            answer=f"TaskMaster answer for: {request.message}",
        )


@pytest.mark.asyncio
async def test_voice_turns_share_taskmaster_conversation_and_call_mode() -> None:
    service = StubInteractionService()
    agent = TaskMasterVoiceAgent(conversation_id=None, service=service)

    first = await agent.respond_to_transcript("What changed since morning?")
    second = await agent.respond_to_transcript("Why does that matter to me?")

    assert first.answer.startswith("TaskMaster answer")
    assert second.conversation_id == first.conversation_id
    assert [item.mode for item in service.requests] == [
        InteractionMode.CALL,
        InteractionMode.CALL,
    ]
    assert service.requests[1].conversation_id == first.conversation_id
    assert service.requests[0].voice_context is not None
    assert service.requests[0].voice_context.portfolio.top_holdings


@pytest.mark.asyncio
async def test_livekit_agent_session_runs_a_complete_text_turn() -> None:
    service = StubInteractionService()
    agent = TaskMasterVoiceAgent(
        conversation_id="voice-conversation",
        service=service,
        greet=False,
    )

    async with AgentSession(llm=TaskMasterTransportLLM()) as session:
        await session.start(agent)
        result = await session.run(user_input="Summarize my biggest exposures")

    result.expect.next_event().is_message(role="assistant")
    result.expect.no_more_events()
    assert service.requests[0].message == "Summarize my biggest exposures"


def test_voice_dispatch_metadata_is_defensive() -> None:
    assert _metadata(None) == {}
    assert _metadata("not-json") == {}
    assert _metadata('{"conversation_id":"conversation-1"}') == {
        "conversation_id": "conversation-1"
    }


@pytest.mark.asyncio
async def test_voice_context_packet_includes_product_context_without_full_dump() -> None:
    financial_day_store.update(lambda state: setattr(state, "run_mode", DayRunMode.DEMO))
    simulation_service.advance_to("12:17")

    context = await build_voice_context("voice-context-test", "call")
    serialized = context.model_dump_json()

    assert context.portfolio.holdings_count == 14
    assert context.portfolio.top_holdings[0].symbol == "HDFCBANK"
    assert context.portfolio.sector_exposure
    assert context.attention_summary.portfolio_relevant_story_count >= 1
    assert context.relevant_stories
    assert len(context.portfolio.top_holdings) <= 5
    assert len(context.relevant_stories) <= 5
    assert len(context.timeline) <= 5
    assert len(serialized) < 18_000


@pytest.mark.asyncio
async def test_voice_context_uses_previous_turns_and_pinned_topic() -> None:
    service = StubInteractionService()
    agent = TaskMasterVoiceAgent(
        conversation_id="voice-topic-test",
        service=service,
        greet=False,
    )

    await agent.respond_to_transcript("Why does HDFCBANK matter?")
    await agent.respond_to_transcript("What about the second one?")

    second_context = service.requests[1].voice_context
    assert second_context is not None
    assert second_context.previous_voice_turns
    assert second_context.pinned_context.last_discussed_symbol == "HDFCBANK"
