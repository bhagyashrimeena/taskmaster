"""TaskMaster-backed conversational service with fast context fallback."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
from typing import Awaitable, Callable
from urllib.parse import urlsplit
from uuid import uuid4

from google.adk.runners import InMemoryRunner
from google.genai import types

from ..agents.taskmaster import root_agent
from ..config import get_settings
from .context import resolve_surface_context
from .memory import (
    conversation_store,
    format_recalled_memories,
    persistent_memory_store,
)
from .schemas import (
    ConversationRequest,
    ConversationResponse,
    InteractionMode,
    SourceReference,
    SurfaceContext,
)


settings = get_settings()
logger = logging.getLogger(__name__)
_URL = re.compile(r"https?://[^\s)\]>]+")
_UNSAFE_SENTENCE = re.compile(
    r"[^.!?]*(?:\byou should (?:buy|sell|hold)\b|\bbuy the dip\b|\bincrease your sip\b|\bthis (?:stock|security) will recover\b)[^.!?]*[.!?]?",
    re.IGNORECASE,
)
_ACTION_DISCLAIMER = re.compile(
    r"[^.!?\n]*(?:does not constitute|is not)[^.!?\n]*(?:investment advice|recommendation)[^.!?\n]*(?:buy|sell|hold)[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)


def _plain_text(answer: str) -> str:
    answer = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 — \2", answer)
    answer = re.sub(r"(?m)^\s*#{1,6}\s*", "", answer)
    answer = re.sub(r"(?m)^\s*>\s?", "", answer)
    answer = re.sub(r"(?m)^\s*[-*]\s+", "• ", answer)
    answer = re.sub(r"(?m)^\s*---+\s*$", "", answer)
    return re.sub(r"[*_`]", "", answer)


def _safe_answer(answer: str) -> str:
    cleaned = _ACTION_DISCLAIMER.sub("", _plain_text(answer))
    cleaned = _UNSAFE_SENTENCE.sub(
        " Wealth Copilot provides relevance and context, not investment instructions.",
        cleaned,
    ).strip()
    return cleaned or "Wealth Copilot provides relevance and context, not investment instructions."


def _grounding_sources(metadata) -> list[SourceReference]:
    """Convert ADK grounding chunks into deduplicated user-facing sources."""

    if metadata is None:
        return []

    def field(value, name: str):
        if isinstance(value, dict):
            return value.get(name) or value.get(_camel(name))
        return getattr(value, name, None)

    def _camel(name: str) -> str:
        head, *tail = name.split("_")
        return head + "".join(item.title() for item in tail)

    chunks = field(metadata, "grounding_chunks") or []
    sources: list[SourceReference] = []
    seen: set[str] = set()
    for chunk in chunks:
        web = field(chunk, "web")
        uri = field(web, "uri")
        title = field(web, "title") or "Grounded source"
        if not uri:
            continue
        hostname = (urlsplit(uri).hostname or "").lower()
        is_redirect = "vertexaisearch.cloud.google.com" in hostname
        canonical_url = None if is_redirect else uri
        source_url = canonical_url or uri
        key = canonical_url or uri
        if key in seen:
            continue
        seen.add(key)
        publisher = hostname.removeprefix("www.") or title
        authority = (
            "official source"
            if any(token in hostname for token in (".gov", "rbi.org", "sebi.gov", "nseindia"))
            else "financial reporting"
        )
        sources.append(
            SourceReference(
                name=title,
                title=title,
                publisher=publisher,
                url=source_url,
                authority=authority,
                kind="grounded_web",
                citation_uri=uri,
                canonical_url=canonical_url,
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    return sources


def _route(request: ConversationRequest, context: SurfaceContext) -> str:
    if request.mode == InteractionMode.RESEARCH:
        return "research_agent"
    message = request.message.lower()
    if any(
        phrase in message
        for phrase in ("morning pulse", "evening wrap", "audio brief", "listen")
    ):
        return "media_agent"
    if any(word in message for word in ("portfolio", "holding", "exposure", "own")) and context.target_type == "dashboard":
        return "portfolio_agent"
    if context.target_type == "event":
        return "event_context"
    if context.target_type == "story":
        return "market_context"
    return "taskmaster"


def _fallback_answer(context: SurfaceContext, mode: InteractionMode) -> str:
    facts = " ".join(context.facts[:3])
    interpretation = " ".join(context.interpretation[:1])
    if mode == InteractionMode.RESEARCH:
        return (
            f"Facts: {facts}\n\nContext / interpretation: {interpretation}\n\n"
            f"What remains uncertain: {' '.join(context.unknowns)}\n\n"
            "The deeper research service is temporarily unavailable, so this answer uses the latest retained context."
        )
    return (
        f"{interpretation} {facts} This is why it deserves your attention; it is context for your "
        "decision-making, not an instruction about what action to take."
    ).strip()


def _json_context(value) -> str:
    if value is None:
        return "none"
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return json.dumps(value, default=str)


TaskMasterCall = Callable[[str, float], Awaitable[tuple]]


class InteractionService:
    def __init__(self, invoker: TaskMasterCall | None = None) -> None:
        self._invoker = invoker or self._invoke_taskmaster

    @staticmethod
    async def _invoke_taskmaster(prompt: str, timeout_seconds: float) -> tuple[str, list[str]]:
        session_id = uuid4().hex
        app_name = "agents"
        runner = InMemoryRunner(agent=root_agent, app_name=app_name)
        trace: list[str] = ["TaskMaster started"]
        answer = ""
        grounding_metadata = None
        try:
            await runner.session_service.create_session(
                app_name=app_name, user_id="dashboard-user", session_id=session_id
            )

            async def run() -> None:
                nonlocal answer
                async for event in runner.run_async(
                    user_id="dashboard-user",
                    session_id=session_id,
                    new_message=types.Content(
                        role="user", parts=[types.Part(text=prompt)]
                    ),
                ):
                    if event.author:
                        label = f"{event.author} responded"
                        if label not in trace:
                            trace.append(label)
                    if event.author == "taskmaster" and event.is_final_response() and event.content:
                        texts = [part.text for part in event.content.parts or [] if part.text]
                        if texts:
                            answer = "\n".join(texts)
                        grounding_metadata = getattr(event, "grounding_metadata", None)

            await asyncio.wait_for(run(), timeout=timeout_seconds)
            if not answer:
                raise RuntimeError("TaskMaster returned no final response")
            trace.append("TaskMaster completed")
            return answer, trace, grounding_metadata
        finally:
            await runner.close()

    async def respond(self, request: ConversationRequest) -> ConversationResponse:
        conversation_id = request.conversation_id or uuid4().hex
        previous = conversation_store.get(conversation_id)
        story_id = request.active_story_id or previous.active_story_id
        event_id = request.active_event_id or previous.active_event_id
        conversation_store.update_context(
            conversation_id, story_id=story_id, event_id=event_id
        )
        context = await resolve_surface_context(story_id=story_id, event_id=event_id)
        route = _route(request, context)
        voice_context = request.voice_context
        if voice_context is None and request.mode in {InteractionMode.VOICE, InteractionMode.CALL}:
            from ..voice.context import build_voice_context

            voice_context = await build_voice_context(conversation_id, request.mode.value)
        history = previous.history[-6:]
        history_text = "\n".join(f"{role}: {text}" for role, text in history) or "None"
        recalled_memories = persistent_memory_store.recall(
            conversation_id=conversation_id,
            query=request.message,
            context=context,
        )
        memory_profile = persistent_memory_store.summary(conversation_id, limit=4)
        memory_signals = [
            item.text
            for item in recalled_memories
            if item.kind == "fact"
        ][:3]
        if request.mode == InteractionMode.RESEARCH:
            mode_rule = "You MUST delegate to research_agent exactly once. Return source-first research with exact URLs."
        elif request.mode in {InteractionMode.VOICE, InteractionMode.CALL}:
            mode_rule = (
                "Use VOICE_CONTEXT and supplied retained context first. If a value is present in VOICE_CONTEXT, answer from it. "
                "Use LONG_TERM_MEMORY only for durable user preferences, goals, or prior conversational context; never treat it as proof of market facts. "
                "Resolve follow-ups like 'why does it matter?', 'what about the second one?', or 'is that serious?' from pinned_context, previous_voice_turns, active_cases, and relevant_stories. "
                "If the needed value is not in context, call the appropriate backend tool/agent or say what is missing. "
                "Do not invent holdings, prices, sources, events, URLs, or market movements. "
                "Answer for speech in at most 100 words, lead with the direct answer, and use short sentences. "
                "Offer one useful next option when appropriate. "
                "Do not say 'dashboard data', 'system state', 'retained context', 'VOICE_CONTEXT', or expose internal routing."
            )
        elif request.mode == InteractionMode.EXPLAIN:
            mode_rule = (
                "Use the supplied retained context first and LONG_TERM_MEMORY only for prior user-specific preferences or follow-up continuity. "
                "Do not call research_agent or refresh/search tools. "
                "Give a concise explanation of at most 140 words without headings or a source list; the UI already "
                "shows facts, interpretation, uncertainty, and sources separately."
            )
        else:
            mode_rule = (
                "Use supplied retained context first. Use LONG_TERM_MEMORY for past user context, preferences, goals, and prior conversational continuity. "
                "Do not treat LONG_TERM_MEMORY as authoritative evidence for prices, news, or external facts. "
                "Do not call research_agent or refresh/search tools."
            )
        prompt = (
            "DASHBOARD INTERACTION\n"
            f"MODE: {request.mode.value}\n"
            f"ACTIVE_STORY_ID: {story_id or 'none'}\n"
            f"ACTIVE_EVENT_ID: {event_id or 'none'}\n"
            f"EXPECTED_ROUTE: {route}\n"
            f"RETAINED_CONTEXT: {context.model_dump_json()}\n"
            f"MEMORY_PROFILE:\n{memory_profile}\n"
            f"LONG_TERM_MEMORY:\n{format_recalled_memories(recalled_memories)}\n"
            f"VOICE_CONTEXT: {_json_context(voice_context)}\n"
            f"RECENT_CONVERSATION:\n{history_text}\n"
            f"USER_QUESTION: {request.message}\n"
            f"{mode_rule} Answer the user's exact question. Clearly separate facts from interpretation. "
            "Explain relevance without giving investment instructions or price predictions."
        )
        timeout = (
            settings.research_timeout_seconds
            if request.mode == InteractionMode.RESEARCH
            else settings.portfolio_interaction_timeout_seconds
            if route in {"portfolio_agent", "media_agent"}
            else settings.interaction_timeout_seconds
        )
        fallback = False
        grounding_metadata = None
        try:
            invocation = await self._invoker(prompt, timeout)
            answer, trace = invocation[0], invocation[1]
            grounding_metadata = invocation[2] if len(invocation) > 2 else None
        except Exception as exc:
            logger.exception("TaskMaster interaction failed")
            fallback = True
            answer = _fallback_answer(context, request.mode)
            trace = [
                "TaskMaster started",
                f"TaskMaster unavailable ({type(exc).__name__})",
                "Retained context fallback completed",
            ]
        answer = _safe_answer(answer)
        conversation_store.append(conversation_id, "user", request.message)
        conversation_store.append(conversation_id, "assistant", answer)
        persistent_memory_store.remember_exchange(
            conversation_id=conversation_id,
            user_message=request.message,
            assistant_message=answer,
            mode=request.mode.value,
            context=context,
        )
        from ..day.schemas import QuestionAsked
        from ..day.store import financial_day_store

        financial_day_store.update(
            lambda state: state.questions_asked.append(
                QuestionAsked(
                    question=request.message,
                    story_id=story_id,
                    event_id=event_id,
                )
            )
        )
        sources = list(context.sources)
        known_urls = {item.canonical_url or item.url for item in sources}
        grounded_sources = _grounding_sources(grounding_metadata)
        if grounded_sources:
            for source in grounded_sources:
                source_key = source.canonical_url or source.url
                if source_key not in known_urls:
                    sources.append(source)
                    known_urls.add(source_key)
        else:
            for url in _URL.findall(answer):
                normalized = url.rstrip(".,;")
                if normalized not in known_urls:
                    sources.append(
                        SourceReference(
                            name="Research source",
                            url=normalized,
                            authority="reported",
                            kind="research",
                            citation_uri=normalized,
                        )
                    )
                    known_urls.add(normalized)
        questions = (
            ["What is confirmed by an official source?", "What remains uncertain?", "How does this compare with the sector?"]
            if request.mode == InteractionMode.RESEARCH
            else ["What caused this?", "What do we know for certain?", "Research this more deeply"]
        )
        return ConversationResponse(
            conversation_id=conversation_id,
            message_id=uuid4().hex,
            mode=request.mode,
            route=route,
            answer=answer,
            context=context,
            sources=sources,
            suggested_questions=questions,
            used_search=(
                request.mode == InteractionMode.RESEARCH
                and not fallback
                and settings.news_provider == "google_search"
            ),
            used_existing_context=True,
            used_long_term_memory=bool(recalled_memories),
            memory_signals=memory_signals,
            fallback_used=fallback,
            agent_trace=trace,
            created_at=datetime.now(timezone.utc),
        )


interaction_service = InteractionService()
