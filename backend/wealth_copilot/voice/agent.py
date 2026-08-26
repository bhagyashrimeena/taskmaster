"""LiveKit voice worker that delegates every answer to the canonical Copilot service."""

from collections.abc import AsyncIterable
import asyncio
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
from .orchestrator import StatusSink, VoiceCallOrchestrator
from .prompting import acknowledgement_for, classify_voice_intent


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


def _call_greeting(context) -> str:
    if context.active_cases:
        active_case = context.active_cases[0]
        subject = active_case.symbol or active_case.title
        return (
            "Hi, I’m Wealth Copilot. I have your portfolio and today’s market context open. "
            f"The main thing on my radar is {subject}, because it moved sharply against your sector exposure. "
            "What would you like to check first?"
        )
    return (
        "Hi, I’m Wealth Copilot. I have your portfolio and today’s market context open. "
        "Nothing urgent is flagged right now. We can look at market status, exposure, or what changed today."
    )


class TaskMasterVoiceAgent(Agent):
    """Speech interface over InteractionService; it owns no financial reasoning."""

    def __init__(
        self,
        *,
        conversation_id: str | None,
        current_case_id: str | None = None,
        service: InteractionService = interaction_service,
        greet: bool = True,
        status_sink: StatusSink | None = None,
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
        self._startup_task: asyncio.Task[None] | None = None
        self._orchestrator = VoiceCallOrchestrator(
            conversation_id=conversation_id,
            current_case_id=current_case_id,
            active_event_id=_event_id_for_case(current_case_id),
            service=service,
            status_sink=status_sink,
        )

    async def on_enter(self) -> None:
        if not self._greet:
            return
        # Do not block LiveKit's room-ready handshake on network/context I/O.
        # The SDK has a deliberately short FFI readiness deadline.
        self._startup_task = asyncio.create_task(self._greet_when_ready())

    async def _greet_when_ready(self) -> None:
        try:
            context = await self._orchestrator.start()
            self.conversation_id = self._orchestrator.conversation_id
            greeting = _call_greeting(context)
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
        acknowledgement = acknowledgement_for(classify_voice_intent(self._latest_transcript))
        if acknowledgement:
            self.session.say(acknowledgement, allow_interruptions=True, add_to_chat_ctx=False)

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
        async for chunk in self._orchestrator.stream_turn(transcript):
            yield chunk
        self.conversation_id = self._orchestrator.conversation_id


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
    async def publish_status(event: str, message: str) -> None:
        payload = json.dumps({"type": "call_status", "event": event, "message": message}, separators=(",", ":"))
        await ctx.room.local_participant.publish_data(
            payload.encode("utf-8"), reliable=True, topic="wealth-copilot.call-state"
        )

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
            endpointing={"mode": "dynamic", "min_delay": 0.25, "max_delay": 1.25},
            interruption={
                "enabled": True,
                "mode": "vad",
                "min_duration": 0.2,
                "min_words": 1,
                "resume_false_interruption": False,
                "false_interruption_timeout": 0.8,
                "backchannel_boundary": None,
            },
            preemptive_generation={"enabled": False},
        ),
        aec_warmup_duration=0.5,
    )
    agent = TaskMasterVoiceAgent(
        conversation_id=context.get("conversation_id"),
        current_case_id=context.get("current_case_id"),
        status_sink=publish_status,
    )

    @session.on("agent_state_changed")
    def on_agent_state_changed(event) -> None:
        labels = {
            "thinking": ("thinking", "Thinking…"),
            "speaking": ("speaking", "Speaking…"),
            "listening": ("waiting_for_user", "Listening…"),
        }
        status = labels.get(event.new_state)
        if status:
            asyncio.create_task(publish_status(*status))

    @session.on("user_state_changed")
    def on_user_state_changed(event) -> None:
        if event.new_state == "speaking":
            if session.agent_state == "speaking":
                agent._orchestrator.mark_interrupted()
                asyncio.create_task(publish_status("interrupted", "Interrupted — I’m listening…"))
            else:
                asyncio.create_task(publish_status("listening", "Listening…"))

    @session.on("metrics_collected")
    def on_metrics_collected(event) -> None:
        metric = event.metrics
        logger.info("livekit_voice_metric %s", metric.model_dump_json(exclude_none=True))

    await session.start(
        room=ctx.room,
        agent=agent,
        record=False,
    )


if __name__ == "__main__":
    cli.run_app(server)
