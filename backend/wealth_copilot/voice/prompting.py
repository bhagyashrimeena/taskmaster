"""Voice-only presentation rules over canonical TaskMaster context."""

from enum import StrEnum
import re

from .schemas import VoiceContext


class VoiceIntent(StrEnum):
    SIMPLE_STATUS = "simple_status"
    PORTFOLIO_EXPOSURE = "portfolio_exposure"
    ACTIVE_CASE_EXPLAIN = "active_case_explain"
    MARKET_NEWS = "market_news"
    DEEP_RESEARCH = "deep_research"
    UNSAFE_INVESTMENT_ADVICE = "unsafe_investment_advice"
    CONVERSATION_CONTROL = "conversation_control"
    GENERAL = "general"


def classify_voice_intent(message: str) -> VoiceIntent:
    """Classify conversational routing only; financial meaning stays in context."""

    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    if normalized in {"wait", "stop", "hold on", "one sec", "one second", "no"}:
        return VoiceIntent.CONVERSATION_CONTROL
    if any(phrase in normalized for phrase in ("where should i invest", "what should i buy", "what should i sell", "give me a trade", "trade call")):
        return VoiceIntent.UNSAFE_INVESTMENT_ADVICE
    if any(phrase in normalized for phrase in ("research deeper", "deep research", "investigate deeper", "verify sources", "research this")):
        return VoiceIntent.DEEP_RESEARCH
    if any(phrase in normalized for phrase in ("market status", "market today", "how is the market", "how's the market", "market doing")):
        return VoiceIntent.SIMPLE_STATUS
    if any(word in normalized for word in ("bizarre", "weirdest", "unusual news", "strangest")):
        return VoiceIntent.MARKET_NEWS
    if any(word in normalized for word in ("alert", "drop", "fell", "fallen", "case", "why does that matter", "is that serious")):
        return VoiceIntent.ACTIVE_CASE_EXPLAIN
    if any(word in normalized for word in ("exposure", "concentration", "holding", "biggest risk")):
        return VoiceIntent.PORTFOLIO_EXPOSURE
    return VoiceIntent.GENERAL


def acknowledgement_for(intent: VoiceIntent) -> str | None:
    """Acknowledge only turns expected to need slower source work."""

    if intent == VoiceIntent.DEEP_RESEARCH:
        return "Give me a moment while I check the sources."
    return None


def status_for(intent: VoiceIntent, context: VoiceContext) -> tuple[str, str]:
    if intent == VoiceIntent.SIMPLE_STATUS:
        return "checking_market_status", "Checking today’s market status…"
    if intent == VoiceIntent.ACTIVE_CASE_EXPLAIN and context.active_cases:
        label = context.active_cases[0].symbol or "active"
        return "reviewing_active_case", f"Reviewing the {label} alert…"
    if intent in {VoiceIntent.MARKET_NEWS, VoiceIntent.DEEP_RESEARCH}:
        return "researching_sources", "Reviewing today’s relevant stories…"
    if intent == VoiceIntent.PORTFOLIO_EXPOSURE:
        return "checking_portfolio", "Checking your portfolio exposure…"
    return "thinking", "Thinking…"


def build_live_call_prompt(message: str, context: VoiceContext, intent: VoiceIntent) -> str:
    """Build the conversational LLM layer without duplicating financial logic."""

    intent_guidance = {
        VoiceIntent.SIMPLE_STATUS: (
            "Answer market status using the portfolio move, benchmark move when available, and the single main driver. "
            "Do not mention total portfolio value, provider names, or holdings count unless asked."
        ),
        VoiceIntent.PORTFOLIO_EXPOSURE: (
            "Explain only the most important concentration or exposure and why it matters today."
        ),
        VoiceIntent.ACTIVE_CASE_EXPLAIN: (
            "Use the active or pinned case. Explain the movement divergence, relevant exposure, and why it crossed attention rules."
        ),
        VoiceIntent.MARKET_NEWS: (
            "Choose the most unusual story from relevant_stories. If the unusual story is less portfolio-relevant than another story, say so briefly."
        ),
        VoiceIntent.DEEP_RESEARCH: (
            "Delegate to research only if fresh source verification is genuinely required. Start with one short useful finding."
        ),
        VoiceIntent.UNSAFE_INVESTMENT_ADVICE: (
            "Briefly refuse the trade recommendation. Redirect to the two most useful risk or research signals in context."
        ),
        VoiceIntent.CONVERSATION_CONTROL: (
            "Respect the conversational interruption. Reply naturally in one very short sentence and wait for the user."
        ),
        VoiceIntent.GENERAL: "Answer the exact question from the supplied context.",
    }[intent]
    return (
        "LIVE WEALTH COPILOT CALL\n"
        "You are Wealth Copilot, a calm AI wealth advisor on a live voice call. The canonical TaskMaster context is already open. "
        "Speak like a human advisor, not a dashboard, report, or chatbot. Preserve all supplied financial facts and deterministic decisions. "
        "Usually answer in 1 to 3 short sentences and no more than 65 words. Lead with the direct answer. Mention only the most relevant numbers. "
        "Use natural spoken language. Do not use headings, bullets, markdown, raw metadata, section labels, or phrases like 'based on dashboard data'. "
        "Ask at most one helpful follow-up. Never recommend buy, sell, or hold actions, predict prices, or invent missing facts. "
        "Never infer that a news story caused a price move unless the context explicitly verifies that link. State uncertainty briefly when cause is unknown. "
        f"VOICE_INTENT: {intent.value}\n"
        f"INTENT_GUIDANCE: {intent_guidance}\n"
        f"VOICE_CONTEXT: {context.model_dump_json()}\n"
        f"USER: {message}\n"
        "Respond now with only the words that should be spoken on the call."
    )


_SENTENCE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)


def complete_sentences(buffer: str, *, final: bool = False) -> tuple[list[str], str]:
    """Release complete spoken sentences while retaining an unfinished tail."""

    working = buffer.replace("\r", " ").replace("\n", " ")
    if not working.strip():
        return [], ""
    matches = list(_SENTENCE.finditer(working))
    completed: list[str] = []
    consumed = 0
    for match in matches:
        sentence = re.sub(r"\s+", " ", match.group(0)).strip()
        if not sentence:
            continue
        terminal = sentence[-1:] in ".!?"
        if not terminal and not final:
            break
        completed.append(sentence)
        consumed = match.end()
    return completed, working[consumed:].lstrip()
