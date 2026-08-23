"""LiveKit voice worker that delegates every answer to the canonical Copilot service."""

from collections.abc import AsyncIterable
import json
import logging
from uuid import uuid4

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    ModelSettings,
    TurnHandlingOptions,
    cli,
    inference,
    llm,
)

from ..config import get_settings
from ..day.store import financial_day_store
from ..interaction.schemas import ConversationRequest, ConversationResponse, InteractionMode
from ..interaction.service import InteractionService, interaction_service
from .context import build_voice_context


logger = logging.getLogger(__name__)


class TaskMasterTransportLLM(llm.LLM):
    """SDK sentinel: generation must be handled by TaskMasterVoiceAgent.llm_node."""

    @property
    def model(self) -> str:
        return "wealth-copilot-taskmaster"

    @property
    def provider(self) -> str:
        return "wealth-copilot"

    def chat(self, **kwargs):
        del kwargs
        raise RuntimeError("Voice generation attempted to bypass TaskMaster")


def _metadata(value: str | None) -> dict[str, str | None]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _event_id_for_case(case_id: str | None) -> str | None:
    if not case_id:
        return None
    day = financial_day_store.get()
    match = next((item for item in day.financial_cases if item.case_id == case_id), None)
    return match.trigger.event_id if match else None


class TaskMasterVoiceAgent(Agent):
    """Speech interface over InteractionService; it owns no financial reasoning."""

    def __init__(
        self,
        *,
        conversation_id: str | None,
        current_case_id: str | None = None,
        service: InteractionService = interaction_service,
        greet: bool = True,
    ) -> None:
        super().__init__(
            instructions=(
                "You are the voice transport for Wealth Copilot. Every substantive answer "
                "comes from the existing TaskMaster-backed Copilot service."
            ),
        )
        self.conversation_id = conversation_id
        self.current_case_id = current_case_id
        self._service = service
        self._greet = greet
        self._latest_transcript = ""

    async def on_enter(self) -> None:
        if not self._greet:
            return
        conversation_id = self.conversation_id or uuid4().hex
        self.conversation_id = conversation_id
        try:
            context = await build_voice_context(conversation_id, InteractionMode.CALL.value)
            active_case = context.active_cases[0].title if context.active_cases else None
            case_line = f" One active case is open: {active_case}." if active_case else " No active case is open."
            greeting = (
                f"I have today's portfolio, {context.portfolio.holdings_count} holdings, "
                f"{context.attention_summary.portfolio_relevant_story_count} relevant stories, "
                f"and {context.attention_summary.active_case_count} active cases loaded."
                f"{case_line} What would you like to look at first?"
            )
        except Exception:
            logger.exception("Voice context greeting failed")
            greeting = "You are connected to Wealth Copilot. What would you like to understand?"
        self.session.say(
            greeting,
            allow_interruptions=True,
        )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        del turn_ctx
        self._latest_transcript = new_message.text_content.strip()
        if not self._latest_transcript:
            raise llm.StopResponse()

    async def respond_to_transcript(self, transcript: str) -> ConversationResponse:
        """Route one finalized voice turn through the same TaskMaster conversation."""

        conversation_id = self.conversation_id or uuid4().hex
        self.conversation_id = conversation_id
        voice_context = await build_voice_context(conversation_id, InteractionMode.CALL.value)
        response = await self._service.respond(
            ConversationRequest(
                conversation_id=self.conversation_id,
                message=transcript,
                mode=InteractionMode.CALL,
                active_event_id=_event_id_for_case(self.current_case_id),
                voice_context=voice_context,
            )
        )
        self.conversation_id = response.conversation_id
        return response

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[str]:
        del tools, model_settings
        transcript = self._latest_transcript
        if not transcript:
            latest_user = next(
                (
                    item
                    for item in reversed(chat_ctx.items)
                    if isinstance(item, llm.ChatMessage) and item.role == "user"
                ),
                None,
            )
            transcript = latest_user.text_content.strip() if latest_user else ""
        if not transcript:
            return
        self._latest_transcript = ""
        response = await self.respond_to_transcript(transcript)
        yield response.answer


settings = get_settings()
server = AgentServer()


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def wealth_copilot_voice_session(ctx: JobContext) -> None:
    """Join an explicitly dispatched room and run the STT → TaskMaster → TTS pipeline."""

    context = _metadata(getattr(ctx.job, "metadata", None))
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "day_id": context.get("day_id"),
        "run_id": context.get("run_id"),
    }
    session = AgentSession(
        stt=inference.STT(
            model=settings.livekit_stt_model,
            language=settings.livekit_stt_language,
        ),
        tts=inference.TTS(
            model=settings.livekit_tts_model,
            voice=settings.livekit_tts_voice,
        ),
        llm=TaskMasterTransportLLM(),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
        ),
    )
    await session.start(
        room=ctx.room,
        agent=TaskMasterVoiceAgent(
            conversation_id=context.get("conversation_id"),
            current_case_id=context.get("current_case_id"),
        ),
        record=False,
    )


if __name__ == "__main__":
    cli.run_app(server)
