"""Resolve dashboard items into source-preserving TaskMaster context."""

from typing import Any

from .schemas import SourceReference, SurfaceContext


def _source(name: str, url: str, authority: str, kind: str) -> SourceReference:
    return SourceReference(name=name, url=url, authority=authority, kind=kind)


async def resolve_surface_context(
    *, story_id: str | None = None, event_id: str | None = None
) -> SurfaceContext:
    # Imported lazily so TaskMaster can use this tool without a module cycle.
    from ..dashboard.service import dashboard_service

    dashboard = await dashboard_service.get_dashboard()
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
        return SurfaceContext(
            day_id=dashboard.day_id,
            run_id=dashboard.run_id,
            target_type="story",
            target_id=story.id,
            title=story.headline,
            facts=[
                story.summary,
                f"Affected portfolio holdings: {holdings}.",
                f"Direct exposure is {story.direct_exposure_pct:.2f}% and sector exposure is {story.sector_exposure_pct:.2f}%.",
                f"Deterministic relevance score: {story.relevance_score:.1f}/100.",
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
        events = [dashboard.important_event, *dashboard.today_events]
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
        return SurfaceContext(
            day_id=dashboard.day_id,
            run_id=dashboard.run_id,
            target_type="event",
            target_id=event.event.event_id,
            title=event.title,
            facts=[
                f"{event.event.company or event.event.symbol} moved {event.event.price_change_pct:.1f}% while its sector moved {event.event.sector_change_pct:.1f}%.",
                f"The sector-relative move was {relative:.1f} percentage points." if relative is not None else "No sector-relative move was available.",
                f"Your direct exposure is {event.affected_portfolio_percentage:.2f}% and sector exposure is {event.sector_exposure_percentage:.2f}%.",
                f"Deterministic relevance score: {event.relevance_score:.2f}/100; attention decision: {event.decision.value}.",
            ],
            interpretation=[event.reason],
            unknowns=["The retained event data does not establish a single confirmed cause for the move."],
            sources=sources,
            portfolio_context=portfolio_context,
        )
    top = dashboard.daily_brief.stories[0]
    largest = ", ".join(
        f"{holding.symbol} {holding.portfolio_weight:.2f}%"
        for holding in portfolio.largest_holdings
    )
    return SurfaceContext(
        day_id=dashboard.day_id,
        run_id=dashboard.run_id,
        target_type="dashboard",
        title="Today's Wealth Copilot dashboard",
        facts=[
            portfolio_context,
            f"Largest holdings by portfolio weight: {largest}.",
            f"Five personalized stories are available; the highest-ranked is: {top.headline}",
            f"The important event is {dashboard.important_event.event.company} with relevance {dashboard.important_event.relevance_score:.2f}/100.",
        ],
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
