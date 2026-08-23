"""The LiveKit worker must remain a transport over the canonical Copilot service."""

from types import SimpleNamespace

import pytest
from livekit.agents import AgentSession

from wealth_copilot.interaction.schemas import InteractionMode
from wealth_copilot.voice.agent import (
    TaskMasterTransportLLM,
    TaskMasterVoiceAgent,
    _metadata,
)


class StubInteractionService:
    def __init__(self) -> None:
        self.requests = []

    async def respond(self, request):
        self.requests.append(request)
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
    assert second.conversation_id == "voice-conversation"
    assert [item.mode for item in service.requests] == [
        InteractionMode.CALL,
        InteractionMode.CALL,
    ]
    assert service.requests[1].conversation_id == "voice-conversation"


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
