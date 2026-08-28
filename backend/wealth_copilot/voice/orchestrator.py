"""Low-latency call orchestration over the canonical TaskMaster service."""

from collections.abc import AsyncIterator, Awaitable, Callable
import asyncio
from dataclasses import dataclass, field
import logging
import re
from time import perf_counter
from uuid import uuid4

from ..interaction.schemas import ConversationRequest, InteractionMode
from ..interaction.service import InteractionService, interaction_service
from .context import build_voice_context
from .llm import voice_presentation_llm
from .prompting import VoiceIntent, classify_voice_intent, status_for
from .schemas import VoiceContext


logger = logging.getLogger(__name__)
StatusSink = Callable[[str, str], Awaitable[None]]


@dataclass
class CallMemory:
    active_topic: str | None = None
    last_discussed_symbol: str | None = None
    last_discussed_case_id: str | None = None
    last_market_question: str | None = None
    last_listed_items: list[str] = field(default_factory=list)
    previous_user_intent: str | None = None
    last_answer_summary: str | None = None
    interrupted_turn_summary: str | None = None


class VoiceCallOrchestrator:
    """Keeps the call warm; TaskMaster remains the only answer generator."""

    def __init__(
        self,
        *,
        conversation_id: str | None,
        current_case_id: str | None,
        active_event_id: str | None,
        service: InteractionService = interaction_service,
        status_sink: StatusSink | None = None,
    ) -> None:
        self.conversation_id = conversation_id or uuid4().hex
        self.current_case_id = current_case_id
        self.active_event_id = active_event_id
        self.service = service
        self.status_sink = status_sink
        self.memory = CallMemory(last_discussed_case_id=current_case_id)
        self._context: VoiceContext | None = None
        self._context_loaded_at = 0.0
        self._turn_started_at = 0.0

    async def emit(self, event: str, message: str) -> None:
        if self.status_sink:
            try:
                await self.status_sink(event, message)
            except Exception:
                logger.debug("Voice status publish failed", exc_info=True)

    async def start(self) -> VoiceContext:
        started = perf_counter()
        # ADC/client construction performs synchronous discovery on first use.
        # Keep it off LiveKit's event loop so room events cannot miss their
        # readiness deadline while the call is connecting.
        try:
            await asyncio.to_thread(voice_presentation_llm.warm)
        except Exception:
            logger.warning("Voice presentation LLM warmup failed; first spoken turn may use fallback", exc_info=True)
        await self.emit("loading_context", "Opening today’s portfolio context…")
        self._context = await build_voice_context(self.conversation_id, InteractionMode.CALL.value)
        self._context_loaded_at = perf_counter()
        self._seed_memory(self._context)
        logger.info("voice_latency context_preload_ms=%.0f", (self._context_loaded_at - started) * 1000)
        return self._context

    def _seed_memory(self, context: VoiceContext) -> None:
        pinned = context.pinned_context
        self.memory.active_topic = pinned.active_topic
        self.memory.last_discussed_symbol = pinned.last_discussed_symbol
        self.memory.last_discussed_case_id = self.current_case_id or pinned.last_discussed_case_id

    async def context_for_turn(self, intent: VoiceIntent) -> VoiceContext:
        now = perf_counter()
        if self._context is None or intent == VoiceIntent.DEEP_RESEARCH or now - self._context_loaded_at > 30:
            self._context = await build_voice_context(self.conversation_id, InteractionMode.CALL.value)
            self._context_loaded_at = perf_counter()
        context = self._context.model_copy(deep=True)
        pinned = context.pinned_context
        pinned.active_topic = self.memory.active_topic or pinned.active_topic
        pinned.last_discussed_symbol = self.memory.last_discussed_symbol or pinned.last_discussed_symbol
        pinned.last_discussed_case_id = self.memory.last_discussed_case_id or pinned.last_discussed_case_id
        pinned.last_user_intent = self.memory.previous_user_intent or pinned.last_user_intent
        pinned.last_market_question = self.memory.last_market_question
        pinned.last_listed_items = list(self.memory.last_listed_items)
        pinned.last_answer_summary = self.memory.last_answer_summary
        pinned.interrupted_turn_summary = self.memory.interrupted_turn_summary
        return context

    async def stream_turn(self, transcript: str) -> AsyncIterator[str]:
        self._turn_started_at = perf_counter()
        intent = classify_voice_intent(transcript)
        context = await self.context_for_turn(intent)
        status, label = status_for(intent, context)
        await self.emit(status, label)
        context_ready = perf_counter()
        logger.info(
            "voice_latency intent=%s transcript_to_context_ms=%.0f cached=%s",
            intent.value,
            (context_ready - self._turn_started_at) * 1000,
            context_ready - self._context_loaded_at < 0.1,
        )
        first_chunk_at: float | None = None
        spoken: list[str] = []
        request = ConversationRequest(
            conversation_id=self.conversation_id,
            message=transcript,
            mode=InteractionMode.CALL,
            active_event_id=self.active_event_id,
            voice_context=context,
        )
        stream_method = getattr(self.service, "stream_voice", None)
        if stream_method is None:
            response = await self.service.respond(request)
            chunks = _sentence_chunks(response.answer)
            self.conversation_id = response.conversation_id
            for chunk in chunks:
                if first_chunk_at is None:
                    first_chunk_at = perf_counter()
                    await self.emit("tts_stream_started", "Speaking…")
                spoken.append(chunk)
                yield chunk
        else:
            async for chunk in stream_method(request, intent=intent):
                if first_chunk_at is None:
                    first_chunk_at = perf_counter()
                    await self.emit("tts_stream_started", "Speaking…")
                spoken.append(chunk)
                yield chunk
        answer = " ".join(spoken).strip()
        self._remember_turn(transcript, answer, intent, context)
        finished = perf_counter()
        logger.info(
            "voice_latency intent=%s first_spoken_chunk_ms=%s total_turn_ms=%.0f words=%d",
            intent.value,
            f"{(first_chunk_at - self._turn_started_at) * 1000:.0f}" if first_chunk_at else "none",
            (finished - self._turn_started_at) * 1000,
            len(answer.split()),
        )

    def _remember_turn(self, transcript: str, answer: str, intent: VoiceIntent, context: VoiceContext) -> None:
        self.memory.previous_user_intent = intent.value
        if intent == VoiceIntent.SIMPLE_STATUS:
            self.memory.last_market_question = transcript[:160]
        known_symbols = {
            item.symbol.upper()
            for item in context.portfolio.top_holdings
        } | {
            item.symbol.upper()
            for item in context.active_cases
            if item.symbol
        }
        mentioned = next((symbol for symbol in known_symbols if re.search(rf"\b{re.escape(symbol)}\b", f"{transcript} {answer}", re.IGNORECASE)), None)
        if mentioned:
            self.memory.last_discussed_symbol = mentioned
            self.memory.active_topic = mentioned
            matching_case = next((item for item in context.active_cases if item.symbol and item.symbol.upper() == mentioned), None)
            if matching_case:
                self.memory.last_discussed_case_id = matching_case.case_id
        self.memory.last_answer_summary = answer[:240] or None
        self.memory.last_listed_items = [item for item in known_symbols if item in answer.upper()][:4]
        self.memory.interrupted_turn_summary = None

    def mark_interrupted(self, transcript: str | None = None) -> None:
        self.memory.interrupted_turn_summary = (transcript or self.memory.last_answer_summary or "Assistant speech interrupted")[:240]


def _sentence_chunks(answer: str) -> list[str]:
    chunks = re.findall(r"[^.!?]+(?:[.!?]+|$)", answer)
    return [re.sub(r"\s+", " ", item).strip() + " " for item in chunks if item.strip()][:4]
