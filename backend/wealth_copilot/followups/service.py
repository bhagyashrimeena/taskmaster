"""News-derived scenario planning and internal calendar-style watch events."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re

from ..config import application_now, application_today, get_settings
from ..dashboard.schemas import StoryView
from ..day.schemas import CalendarWatchEvent, FinancialDayState, LikelyScenario, NewsSnapshot
from ..day.store import FinancialDayStore, financial_day_store


_BLOCKED_LANGUAGE = re.compile(
    r"\b(will|guaranteed|sure|definitely|buy|sell|invest now|target price)\b",
    re.IGNORECASE,
)


def _decision_for_story(story: StoryView) -> str:
    if story.relevance_score >= 95 and story.direct_exposure_pct >= 15:
        return "INVESTIGATE"
    if story.relevance_score >= 75:
        return "MONITOR"
    return "IGNORE"


def _symbol_for_story(story: StoryView) -> str | None:
    if story.affected_holdings:
        return story.affected_holdings[0]
    for token in ("RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK"):
        if token.lower() in story.headline.lower() or token.lower() in story.summary.lower():
            return token
    return None


def _safe(value: str) -> str:
    return _BLOCKED_LANGUAGE.sub("may", value)


class FollowupService:
    disclaimer = "Scenarios are not predictions or investment advice."

    def __init__(self, store: FinancialDayStore | None = None) -> None:
        self.store = store or financial_day_store

    def news_snapshot_from_story(self, story: StoryView, day_id: str) -> NewsSnapshot:
        symbol = _symbol_for_story(story)
        return NewsSnapshot(
            story_id=story.id,
            day_id=day_id,
            title=story.headline,
            source_name=story.source_name,
            source_url=story.canonical_url or story.source_url,
            source_status=story.canonical_url_status,
            published_at=story.published_at,
            symbols=story.affected_holdings or ([symbol] if symbol else []),
            sectors=[],
            summary=story.summary,
            known_facts=[
                story.summary,
                f"Direct portfolio exposure is {story.direct_exposure_pct:.2f}%.",
                f"Sector exposure is {story.sector_exposure_pct:.2f}%.",
                f"Relevance score is {story.relevance_score:.2f}/100.",
            ],
            uncertainties=[
                "The market outcome is not confirmed.",
                "Further source updates may change the monitoring priority.",
            ],
            portfolio_relevance_reason=story.why_am_i_seeing_this,
            direct_exposure_percent=story.direct_exposure_pct,
            sector_exposure_percent=story.sector_exposure_pct,
            relevance_score=story.relevance_score,
            decision=_decision_for_story(story),
        )

    def scenarios_for_story(self, story: StoryView, *, day_id: str, case_id: str | None = None) -> list[LikelyScenario]:
        symbol = _symbol_for_story(story)
        if story.relevance_score < 75 or not symbol:
            return []
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=26)
        subject = "Reliance" if symbol == "RELIANCE" else symbol
        base = story.summary
        relevance = (
            f"{subject} is relevant because direct exposure is {story.direct_exposure_pct:.2f}% "
            f"and sector exposure is {story.sector_exposure_pct:.2f}%."
        )
        if symbol == "RELIANCE":
            templates = [
                (
                    "growth",
                    "bullish",
                    "plausible",
                    "medium",
                    "Growth case",
                    "One plausible scenario is that investors view the development as a long-term growth option.",
                    "Follow price reaction, management commentary, execution milestones, and sector peer response.",
                ),
                (
                    "wait-and-watch",
                    "neutral",
                    "plausible",
                    "medium",
                    "Wait-and-watch case",
                    "One plausible scenario is that reaction stays muted until execution clarity improves.",
                    "Monitor official updates, timeline clarity, capital allocation details, and volume trends.",
                ),
                (
                    "capex-risk",
                    "risk",
                    "possible",
                    "medium",
                    "Capex/debt concern case",
                    "One possible risk scenario is that investors focus on capex, debt, or regulatory uncertainty.",
                    "Watch debt commentary, capex guidance, approvals, and any sector-wide repricing.",
                ),
            ]
        else:
            templates = [
                (
                    "positive-follow-through",
                    "bullish",
                    "possible",
                    "low",
                    "Positive follow-through case",
                    "One possible scenario is that later updates make the development more material for this holding.",
                    "Monitor official disclosures, sector reaction, and whether the relevance score changes.",
                ),
                (
                    "contained",
                    "neutral",
                    "plausible",
                    "medium",
                    "Contained reaction case",
                    "One plausible scenario is that the event remains important to know but does not require interruption.",
                    "Monitor whether price movement stays close to sector movement.",
                ),
                (
                    "risk-escalation",
                    "risk",
                    "possible",
                    "medium",
                    "Risk escalation case",
                    "One possible risk scenario is that new facts raise uncertainty or increase portfolio relevance.",
                    "Watch source verification, company response, and sector-relative movement.",
                ),
            ]
        return [
            LikelyScenario(
                scenario_id=f"scenario-{story.id}-{key}",
                story_id=story.id,
                case_id=case_id,
                symbol=symbol,
                title=title,
                base_summary=base,
                scenario_type=scenario_type,
                likelihood_label=likelihood,
                confidence=confidence,
                why_it_could_happen=_safe(why),
                what_to_monitor=_safe(monitor),
                portfolio_relevance=_safe(relevance),
                created_at=now,
                expires_at=expires,
            )
            for key, scenario_type, likelihood, confidence, title, why, monitor in templates
        ]

    def ensure_from_stories(self, stories: list[StoryView], trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()

        def mutate(state: FinancialDayState) -> None:
            existing_snapshots = {item.story_id for item in state.news_snapshots}
            existing_scenarios = {item.scenario_id for item in state.likely_scenarios}
            cases_by_symbol = {
                (case.trigger.symbol or case.trigger.instrument or "").upper(): case.case_id
                for case in state.financial_cases
            }
            for story in stories:
                if story.id not in existing_snapshots:
                    state.news_snapshots.append(self.news_snapshot_from_story(story, state.day_id))
                symbol = _symbol_for_story(story)
                case_id = cases_by_symbol.get((symbol or "").upper())
                for scenario in self.scenarios_for_story(story, day_id=state.day_id, case_id=case_id):
                    if scenario.scenario_id not in existing_scenarios:
                        state.likely_scenarios.append(scenario)
                        existing_scenarios.add(scenario.scenario_id)

        return self.store.update(mutate, selected)

    def create_watch_event(
        self,
        *,
        title: str,
        description: str,
        symbol: str | None = None,
        story_id: str | None = None,
        case_id: str | None = None,
        scenario_id: str | None = None,
        scheduled_for: datetime | None = None,
        trigger_type: str = "news_followup",
        created_by: str = "user",
        trading_date: date | None = None,
    ) -> CalendarWatchEvent:
        selected = trading_date or application_today()
        default_schedule = application_now() + timedelta(minutes=5)
        scheduled = scheduled_for or default_schedule
        event = CalendarWatchEvent(
            event_id=f"watch-{(scenario_id or story_id or case_id or symbol or 'event').lower().replace(':', '-')}-{scheduled.strftime('%Y%m%d%H%M')}",
            day_id=self.store.get(selected).day_id,
            case_id=case_id,
            story_id=story_id,
            scenario_id=scenario_id,
            symbol=symbol,
            title=_safe(title),
            description=_safe(description),
            scheduled_for=scheduled,
            trigger_type=trigger_type,
            created_by=created_by,
            reminder_copy=_safe(f"Review {symbol or title} market reaction and any follow-up announcements."),
        )

        def mutate(state: FinancialDayState) -> None:
            state.calendar_watch_events = [
                item for item in state.calendar_watch_events if item.event_id != event.event_id
            ]
            state.calendar_watch_events.append(event)

        self.store.update(mutate, selected)
        return event

    def ensure_reliance_watch_event(self, trading_date: date | None = None) -> CalendarWatchEvent | None:
        selected = trading_date or application_today()
        state = self.store.get(selected)
        scenario = next((item for item in state.likely_scenarios if item.symbol == "RELIANCE"), None)
        if not scenario:
            return None
        return self.create_watch_event(
            title="Review Reliance market reaction",
            description=(
                "Wealth Copilot flagged Reliance because relevant news flow may matter to portfolio exposure. "
                "Review price movement, sector reaction, and follow-up announcements."
            ),
            symbol="RELIANCE",
            story_id=scenario.story_id,
            scenario_id=scenario.scenario_id,
            trigger_type="news_followup",
            created_by="agent",
            trading_date=selected,
        )


followup_service = FollowupService()
