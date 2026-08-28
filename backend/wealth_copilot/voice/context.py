"""Compact backend-owned context for voice and LiveKit turns."""

from datetime import datetime
import re

from ..config import application_now, application_today
from ..dashboard.service import dashboard_service
from ..day.schemas import StepStatus
from ..day.store import financial_day_store
from ..events.schemas import EventAssessment
from ..interaction.memory import conversation_store
from ..onboarding import onboarding_service
from .schemas import (
    VoiceAttentionContext,
    VoiceCaseContext,
    VoiceContext,
    VoiceHoldingContext,
    VoiceLikelyScenarioContext,
    VoicePinnedContext,
    VoicePortfolioContext,
    VoicePreferenceContext,
    VoicePreviousTurnContext,
    VoiceSectorContext,
    VoiceStoryContext,
    VoiceTimelineContext,
    VoiceWatchEventContext,
)


_SYMBOL = re.compile(r"\b[A-Z][A-Z0-9]{2,12}\b")
_NON_SYMBOL_TOKENS = {
    "ABOUT",
    "ANSWER",
    "BECAUSE",
    "CALL",
    "DOES",
    "MATTER",
    "SECOND",
    "TASKMASTER",
    "THAT",
    "THE",
    "WHAT",
    "WHY",
}


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _today_change_pct(market_value: float, day_pnl: float | None) -> float | None:
    if day_pnl is None:
        return None
    previous_value = market_value - day_pnl
    if previous_value == 0:
        return None
    return round(day_pnl / previous_value * 100, 2)


def _case_for_event(assessments: dict[str, EventAssessment], event_id: str | None):
    return assessments.get(event_id or "")


def _previous_turns(conversation_id: str) -> list[VoicePreviousTurnContext]:
    history = conversation_store.get(conversation_id).history
    turns: list[VoicePreviousTurnContext] = []
    pending_user: str | None = None
    for role, text in history[-10:]:
        if role == "user":
            pending_user = text
        elif role == "assistant" and pending_user:
            turns.append(
                VoicePreviousTurnContext(
                    user=pending_user,
                    assistant_summary=text[:220],
                    topic=_topic_from_text(f"{pending_user} {text}"),
                )
            )
            pending_user = None
    if pending_user:
        turns.append(VoicePreviousTurnContext(user=pending_user, topic=_topic_from_text(pending_user)))
    return turns[-5:]


def _topic_from_text(text: str) -> str | None:
    for match in _SYMBOL.findall(text.upper()):
        if match not in _NON_SYMBOL_TOKENS and match not in {"INR", "RBI", "LIC", "AI"}:
            return match
    return None


def _pinned_context(conversation_id: str, active_cases: list[VoiceCaseContext]) -> VoicePinnedContext:
    record = conversation_store.get(conversation_id)
    history_text = " ".join(text for _, text in record.history[-6:])
    active_case = active_cases[0] if active_cases else None
    topic = _topic_from_text(history_text) or (active_case.symbol if active_case else None)
    last_user = next((text for role, text in reversed(record.history) if role == "user"), None)
    return VoicePinnedContext(
        active_topic=active_case.title if active_case else topic,
        last_discussed_symbol=topic,
        last_discussed_case_id=active_case.case_id if active_case else None,
        last_user_intent=last_user[:80] if last_user else None,
    )


async def build_voice_context(conversation_id: str, mode: str = "call") -> VoiceContext:
    """Build a small context packet from canonical backend product state."""

    dashboard = await dashboard_service.get_dashboard()
    day = financial_day_store.get(application_today())
    portfolio = dashboard.portfolio
    day_performance = next((item for item in portfolio.performance if item.period == "1D"), None)
    top_holdings = portfolio.largest_holdings[:5]
    largest = top_holdings[0] if top_holdings else None
    top_three_concentration = round(sum(item.portfolio_weight for item in top_holdings[:3]), 2)
    risk_flags: list[str] = []
    if largest and largest.portfolio_weight >= 15:
        risk_flags.append(f"Largest holding is above 15%: {largest.symbol}")
    largest_sector = portfolio.sector_exposure[0] if portfolio.sector_exposure else None
    if largest_sector and largest_sector.portfolio_weight >= 25:
        risk_flags.append(f"{largest_sector.sector} is the largest sector exposure")

    assessments = {
        item.event.event_id: item
        for item in [*day.events_detected, *day.events_alerted, *day.events_ignored]
    }
    active_cases: list[VoiceCaseContext] = []
    for case in day.financial_cases:
        if case.status.value == "CLOSED":
            continue
        assessment = _case_for_event(assessments, case.trigger.event_id)
        active_cases.append(
            VoiceCaseContext(
                case_id=case.case_id,
                symbol=case.trigger.symbol or case.trigger.instrument,
                title=case.trigger.headline,
                status=case.status.value,
                priority=case.priority.value,
                detected_at=case.opened_at,
                price_change_percent=case.trigger.price_change_pct,
                sector_change_percent=case.trigger.sector_change_pct,
                benchmark_change_percent=case.trigger.index_change_pct,
                direct_exposure_percent=case.portfolio_exposure.direct_pct,
                sector_exposure_percent=case.portfolio_exposure.sector_pct,
                relevance_score=assessment.relevance_score if assessment else None,
                short_reason=assessment.reason if assessment else case.trigger.headline,
                known_facts=[
                    fact
                    for fact in (
                        f"{case.trigger.symbol or case.trigger.instrument} moved {case.trigger.price_change_pct}%.",
                        f"{case.trigger.sector} sector moved {case.trigger.sector_change_pct}%.",
                        f"Direct exposure is {case.portfolio_exposure.direct_pct}%.",
                        f"Sector exposure is {case.portfolio_exposure.sector_pct}%.",
                    )
                    if "None" not in fact
                ],
                uncertainties=[
                    "Exact cause may require source verification.",
                    "Movement can reflect more than one factor.",
                ],
                suggested_next_actions=assessment.actions if assessment else ["Explain", "Research", "Save"],
            )
        )

    timeline = [
        VoiceTimelineContext(
            time=step.scheduled_time,
            type="financial_day_step",
            title=step.label,
            status=step.status.value,
            summary=step.detail,
        )
        for step in day.timeline
        if step.status in {StepStatus.COMPLETE, StepStatus.RUNNING}
    ][-5:]
    preferences = VoicePreferenceContext()
    onboarding = onboarding_service.get("demo_user")
    if onboarding is not None:
        agent_preferences = onboarding.final_profile.get("agent_preferences", {})
        voice_preferences = agent_preferences.get("voice_preferences", {}) if isinstance(agent_preferences, dict) else {}
        preferences = VoicePreferenceContext(
            alert_sensitivity=agent_preferences.get("alert_sensitivity", "balanced") if isinstance(agent_preferences, dict) else "balanced",
            minimum_attention_outcome=agent_preferences.get("minimum_attention_outcome", "INVESTIGATE") if isinstance(agent_preferences, dict) else "INVESTIGATE",
            voice_style=voice_preferences.get("voice_style", "simple_advisor") if isinstance(voice_preferences, dict) else "simple_advisor",
            answer_length=voice_preferences.get("answer_length", "short") if isinstance(voice_preferences, dict) else "short",
            focus_areas=agent_preferences.get("focus_areas", []) if isinstance(agent_preferences, dict) else [],
        )

    return VoiceContext(
        conversation_id=conversation_id,
        mode=mode,
        user_local_time=application_now(),
        day_id=dashboard.day_id,
        run_id=dashboard.run_id,
        current_checkpoint=day.presentation_active_checkpoint or day.active_step_id,
        financial_day_status=day.status.value,
        portfolio=VoicePortfolioContext(
            total_value=portfolio.portfolio_value,
            today_change_amount=portfolio.day_pnl,
            today_change_percent=portfolio.day_change_pct,
            overall_gain_amount=portfolio.unrealized_pnl,
            overall_gain_percent=portfolio.overall_return_pct,
            benchmark_change_percent=day_performance.benchmark_return_pct if day_performance else None,
            benchmark_label=day_performance.benchmark_label if day_performance else None,
            holdings_count=portfolio.holdings_count,
            top_holdings=[
                VoiceHoldingContext(
                    symbol=holding.symbol,
                    name=holding.name,
                    value=holding.market_value,
                    weight_percent=holding.portfolio_weight,
                    today_change_percent=_today_change_pct(holding.market_value, holding.day_pnl),
                    sector=holding.asset_class,
                )
                for holding in top_holdings
            ],
            sector_exposure=[
                VoiceSectorContext(
                    sector=item.sector,
                    weight_percent=item.portfolio_weight,
                )
                for item in portfolio.sector_exposure[:5]
            ],
            largest_holding=largest.symbol if largest else None,
            top_three_concentration=top_three_concentration,
            risk_flags=risk_flags,
        ),
        attention_summary=VoiceAttentionContext(
            high_priority_count=dashboard.attention_summary.high_priority_count,
            portfolio_relevant_story_count=len(dashboard.daily_brief.stories),
            active_case_count=len(active_cases),
            monitoring_count=sum(1 for item in [*day.events_detected, *day.events_alerted] if item.decision.value == "MONITOR"),
            ignored_count=len(day.events_ignored),
        ),
        active_cases=active_cases[:5],
        relevant_stories=[
            VoiceStoryContext(
                story_id=story.id,
                title=story.headline,
                source_name=story.source_name,
                symbols=story.affected_holdings,
                sectors=[],
                summary=story.summary,
                relevance_score=story.relevance_score,
                direct_exposure_percent=story.direct_exposure_pct,
                sector_exposure_percent=story.sector_exposure_pct,
                source_status=story.canonical_url_status,
            )
            for story in dashboard.daily_brief.stories[:5]
        ],
        likely_scenarios=[
            VoiceLikelyScenarioContext(
                scenario_id=item.scenario_id,
                symbol=item.symbol,
                title=item.title,
                scenario_type=item.scenario_type,
                likelihood_label=item.likelihood_label,
                confidence=item.confidence,
                why_it_could_happen=item.why_it_could_happen,
                what_to_monitor=item.what_to_monitor,
                portfolio_relevance=item.portfolio_relevance,
            )
            for item in day.likely_scenarios
            if item.status == "active"
        ][:6],
        watch_events=[
            VoiceWatchEventContext(
                event_id=item.event_id,
                symbol=item.symbol,
                title=item.title,
                scheduled_for=item.scheduled_for,
                reminder_copy=item.reminder_copy,
                status=item.status,
            )
            for item in day.calendar_watch_events
            if item.status == "scheduled"
        ][:4],
        timeline=timeline,
        previous_voice_turns=_previous_turns(conversation_id),
        pinned_context=_pinned_context(conversation_id, active_cases),
        preferences=preferences,
    )
