"""Resolve dashboard items into source-preserving TaskMaster context."""

from typing import Any

from .schemas import SourceReference, SurfaceContext


def _source(name: str, url: str, authority: str, kind: str) -> SourceReference:
    return SourceReference(name=name, url=url, authority=authority, kind=kind)


def _source_checkpoint(portfolio, provenance=None) -> str:
    checkpoint = getattr(provenance, "source_checkpoint", None)
    if checkpoint and checkpoint != "normal":
        return checkpoint
    return portfolio.source.checkpoint or portfolio.as_of.strftime("%H:%M")


def _profile_context_fact(profile) -> str | None:
    if profile is None:
        return None
    preferences = profile.final_profile.get("agent_preferences", {})
    voice_preferences = preferences.get("voice_preferences", {}) if isinstance(preferences, dict) else {}
    alert_sensitivity = preferences.get("alert_sensitivity", "balanced") if isinstance(preferences, dict) else "balanced"
    minimum_outcome = preferences.get("minimum_attention_outcome", "INVESTIGATE") if isinstance(preferences, dict) else "INVESTIGATE"
    voice_style = voice_preferences.get("voice_style", "simple_advisor") if isinstance(voice_preferences, dict) else "simple_advisor"
    answer_length = voice_preferences.get("answer_length", "short") if isinstance(voice_preferences, dict) else "short"
    return (
        "User onboarding preferences: "
        f"alert sensitivity {alert_sensitivity}; "
        f"minimum attention outcome {minimum_outcome}; "
        f"explanation style {voice_style}; "
        f"answer length {answer_length}."
    )


async def resolve_surface_context(
    *, story_id: str | None = None, event_id: str | None = None
) -> SurfaceContext:
    # Imported lazily so TaskMaster can use this tool without a module cycle.
    from ..dashboard.service import dashboard_service
    from ..day.store import financial_day_store
    from ..onboarding import onboarding_service

    dashboard = await dashboard_service.get_dashboard()
    day = financial_day_store.get()
    profile = onboarding_service.get("demo_user")
    profile_fact = _profile_context_fact(profile)
    portfolio = dashboard.portfolio
    portfolio_context = (
        f"Portfolio value {portfolio.currency} {portfolio.portfolio_value:.2f}; "
        f"{portfolio.holdings_count} holdings; provider {portfolio.source.label}."
    )
    if story_id:
        story = next(
            (item for item in dashboard.daily_brief.stories if item.id == story_id), None
        )
        if story is None:
            raise ValueError(f"Unknown story_id: {story_id}")
        holdings = ", ".join(story.affected_holdings) or "sector exposure"
        checkpoint = _source_checkpoint(portfolio, dashboard.daily_brief.provenance)
        return SurfaceContext(
            day_id=dashboard.day_id,
            run_id=dashboard.run_id,
            target_type="story",
            target_id=story.id,
            title=story.headline,
            portfolio_as_of=portfolio.as_of,
            source_checkpoint=checkpoint,
            facts=[
                item
                for item in [
                    story.summary,
                    f"Affected portfolio holdings: {holdings}.",
                    f"At the {checkpoint} portfolio snapshot, direct exposure is {story.direct_exposure_pct:.2f}% and sector exposure is {story.sector_exposure_pct:.2f}%.",
                    f"Deterministic relevance score: {story.relevance_score:.1f}/100.",
                    profile_fact,
                ]
                if item
            ],
            interpretation=[story.why_am_i_seeing_this],
            unknowns=["The retained brief may not contain the full chronology or every official disclosure."],
            sources=[
                _source(
                    story.source_name,
                    story.source_url,
                    story.source_authority,
                    "retained_market_story",
                )
            ],
            portfolio_context=portfolio_context,
        )
    if event_id:
        events = [
            item
            for item in [dashboard.important_event, *dashboard.today_events]
            if item is not None
        ]
        event = next(
            (item for item in events if item.event.event_id == event_id), None
        )
        if event is None:
            raise ValueError(f"Unknown event_id: {event_id}")
        sources = [
            _source(event.event.source, event.event.source_url, "event_feed", "event")
        ]
        sources.extend(
            _source(item.source_name, item.source_url, "supporting", "development")
            for item in event.developments
        )
        relative = event.sector_relative_move_pct
        checkpoint = _source_checkpoint(portfolio, event.provenance)
        return SurfaceContext(
            day_id=dashboard.day_id,
            run_id=dashboard.run_id,
            target_type="event",
            target_id=event.event.event_id,
            title=event.title,
            portfolio_as_of=portfolio.as_of,
            source_checkpoint=checkpoint,
            facts=[
                item
                for item in [
                    f"{event.event.company or event.event.symbol} moved {event.event.price_change_pct:.1f}% while its sector moved {event.event.sector_change_pct:.1f}%.",
                    f"The sector-relative move was {relative:.1f} percentage points." if relative is not None else "No sector-relative move was available.",
                    f"At the {checkpoint} portfolio snapshot, your direct exposure is {event.affected_portfolio_percentage:.2f}% and sector exposure is {event.sector_exposure_percentage:.2f}%.",
                    f"Deterministic relevance score: {event.relevance_score:.2f}/100; attention decision: {event.decision.value}.",
                    profile_fact,
                ]
                if item
            ],
            interpretation=[event.reason],
            unknowns=["The retained event data does not establish a single confirmed cause for the move."],
            sources=sources,
            portfolio_context=portfolio_context,
        )
    top = dashboard.daily_brief.stories[0] if dashboard.daily_brief.stories else None
    checkpoint = _source_checkpoint(portfolio)
    largest = ", ".join(
        f"{holding.symbol} {holding.portfolio_weight:.2f}%"
        for holding in portfolio.largest_holdings
    )
    facts = [
        portfolio_context,
        f"Largest holdings by portfolio weight: {largest}.",
    ]
    if profile_fact is not None:
        facts.append(profile_fact)
    if top is not None:
        facts.append(
            f"{len(dashboard.daily_brief.stories)} personalized stories are available; "
            f"the highest-ranked is: {top.headline}"
        )
    if dashboard.important_event is not None:
        facts.append(
            f"The important event is "
            f"{dashboard.important_event.event.company or dashboard.important_event.event.symbol} "
            f"with relevance {dashboard.important_event.relevance_score:.2f}/100."
        )
    else:
        facts.append("No market event currently crosses the interruption threshold.")
    active_scenarios = [item for item in day.likely_scenarios if item.status == "active"]
    if active_scenarios:
        facts.append(
            "Likely scenarios to monitor: "
            + "; ".join(
                f"{item.symbol or 'portfolio'} {item.title} ({item.likelihood_label}, {item.confidence} confidence): {item.what_to_monitor}"
                for item in active_scenarios[:4]
            )
            + ". Scenarios are not predictions or investment advice."
        )
    watch_events = [item for item in day.calendar_watch_events if item.status == "scheduled"]
    if watch_events:
        facts.append(
            "Scheduled internal watch events: "
            + "; ".join(
                f"{item.title} at {item.scheduled_for.isoformat()}"
                for item in watch_events[:3]
            )
            + "."
        )
    return SurfaceContext(
        day_id=dashboard.day_id,
        run_id=dashboard.run_id,
        target_type="dashboard",
        title="Today's Wealth Copilot dashboard",
        portfolio_as_of=portfolio.as_of,
        source_checkpoint=checkpoint,
        facts=facts,
        interpretation=[dashboard.attention_message],
        unknowns=["A broad question may need a more specific story, event, or portfolio topic."],
        sources=[],
        portfolio_context=portfolio_context,
    )


async def get_surface_context(
    story_id: str = "", event_id: str = ""
) -> dict[str, Any]:
    """Return retained dashboard facts for one story/event without a new Search call."""

    context = await resolve_surface_context(
        story_id=story_id or None, event_id=event_id or None
    )
    return {"status": "ok", "data": context.model_dump(mode="json")}
