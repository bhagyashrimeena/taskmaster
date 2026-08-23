"""Composition service for focused frontend contracts.

This layer does not calculate portfolio truth or make decisions. It only shapes
canonical dashboard, case, market-data, and financial-day state for each page.
"""

from datetime import datetime, timezone

from ..cases.schemas import FinancialCase, FinancialCasePriority, FinancialCaseStatus
from ..config import application_today
from ..dashboard.service import dashboard_service
from ..day.schemas import FinancialDayState, StepStatus
from ..day.store import financial_day_store
from ..events.schemas import EventAssessment, EventDecision
from ..interaction.memory import conversation_store
from ..market_data import MarketDataProvider, get_market_data_provider
from ..voice.service import voice_session_service
from .schemas import (
    AlertCategory,
    AlertDetailResponse,
    AlertInboxItem,
    AlertInboxResponse,
    AttentionItem,
    AttentionItemKind,
    CopilotBootstrapResponse,
    PortfolioResponse,
    StreamSnapshot,
    TimelineResponse,
    TodayResponse,
)


def _category(decision: EventDecision, status: FinancialCaseStatus | None) -> AlertCategory:
    if decision == EventDecision.ALERT or status == FinancialCaseStatus.ALERTED:
        return AlertCategory.ATTENTION
    if decision == EventDecision.INVESTIGATE or status == FinancialCaseStatus.INVESTIGATING:
        return AlertCategory.INVESTIGATING
    if decision == EventDecision.IGNORE or status == FinancialCaseStatus.CLOSED:
        return AlertCategory.IGNORED
    return AlertCategory.MONITORING


def _priority(assessment: EventAssessment) -> FinancialCasePriority:
    if assessment.decision == EventDecision.ALERT:
        return FinancialCasePriority.CRITICAL if assessment.relevance_score >= 95 else FinancialCasePriority.HIGH
    if assessment.decision == EventDecision.INVESTIGATE:
        return FinancialCasePriority.HIGH
    if assessment.decision == EventDecision.MONITOR:
        return FinancialCasePriority.MEDIUM
    return FinancialCasePriority.LOW


class ProductApiService:
    def __init__(self, market_data: MarketDataProvider | None = None) -> None:
        self.market_data = market_data or get_market_data_provider()

    @staticmethod
    def _day() -> FinancialDayState:
        return financial_day_store.get(application_today())

    async def today(self) -> TodayResponse:
        dashboard = await dashboard_service.get_dashboard()
        day = self._day()
        attention: list[AttentionItem] = []
        event = dashboard.important_event
        if event is not None and event.notification_required:
            attention.append(AttentionItem(
                item_id=event.event.event_id,
                kind=AttentionItemKind.EVENT,
                priority="high",
                title=event.title,
                summary=event.reason,
                relevance_score=event.relevance_score,
                direct_exposure_pct=event.affected_portfolio_percentage,
                sector_exposure_pct=event.sector_exposure_percentage,
                status=event.decision.value,
                occurred_at=event.event.timestamp,
                actions=event.actions,
            ))
        attention.extend(
            AttentionItem(
                item_id=story.id,
                kind=AttentionItemKind.STORY,
                priority="high" if story.relevance_score >= 85 else "normal",
                title=story.headline,
                summary=story.why_am_i_seeing_this,
                relevance_score=story.relevance_score,
                direct_exposure_pct=story.direct_exposure_pct,
                sector_exposure_pct=story.sector_exposure_pct,
                status="BRIEF",
                occurred_at=story.published_at,
                actions=story.actions,
            )
            for story in dashboard.daily_brief.stories
            if story.relevance_score >= 85
        )
        completed = [step for step in day.timeline if step.status == StepStatus.COMPLETE]
        next_checkpoint = next(
            (step for step in day.timeline if step.status in {StepStatus.PENDING, StepStatus.RUNNING}),
            None,
        )
        return TodayResponse(
            day_id=dashboard.day_id,
            run_id=dashboard.run_id,
            trading_date=day.trading_date,
            generated_at=dashboard.generated_at,
            greeting=dashboard.greeting,
            attention_count=len(attention),
            attention_message=(
                "Nothing material needs your attention right now"
                if not attention
                else f"{len(attention)} {'update is' if len(attention) == 1 else 'updates are'} worth reviewing"
            ),
            attention_items=attention,
            portfolio=dashboard.portfolio,
            daily_brief=dashboard.daily_brief,
            recent_timeline=completed[-3:],
            next_checkpoint=next_checkpoint,
            morning_brief_id=day.morning_brief_id,
            evening_brief_id=day.evening_brief_id,
            daily_state=dashboard.daily_state,
            disclaimer=dashboard.disclaimer,
        )

    async def portfolio(self) -> PortfolioResponse:
        dashboard = await dashboard_service.get_dashboard()
        return PortfolioResponse(
            day_id=dashboard.day_id,
            run_id=dashboard.run_id,
            generated_at=dashboard.generated_at,
            portfolio=dashboard.portfolio,
        )

    @staticmethod
    def _assessments(day: FinancialDayState) -> dict[str, EventAssessment]:
        result: dict[str, EventAssessment] = {}
        for assessment in [*day.events_detected, *day.events_alerted, *day.events_ignored]:
            result[assessment.event.event_id] = assessment
        return result

    @staticmethod
    def _item(assessment: EventAssessment, case: FinancialCase | None) -> AlertInboxItem:
        event = assessment.event
        direct = assessment.affected_portfolio_percentage
        impact = (
            round(direct * event.price_change_pct / 100, 2)
            if event.price_change_pct is not None
            else None
        )
        return AlertInboxItem(
            case_id=case.case_id if case else None,
            event_id=event.event_id,
            instrument=event.instrument,
            company=event.company,
            headline=event.headline,
            occurred_at=event.timestamp,
            updated_at=case.updated_at if case else assessment.evaluated_at,
            category=_category(assessment.decision, case.status if case else None),
            status=(case.status.value if case else assessment.decision.value),
            priority=case.priority if case else _priority(assessment),
            decision=assessment.decision,
            notification_required=assessment.notification_required,
            price_change_pct=event.price_change_pct,
            sector_change_pct=event.sector_change_pct,
            index_change_pct=event.index_change_pct,
            direct_exposure_pct=direct,
            sector_exposure_pct=assessment.sector_exposure_percentage,
            portfolio_impact_pct=impact,
            relevance_score=assessment.relevance_score,
            reason=assessment.reason,
        )

    async def alerts(self, category: AlertCategory | None = None) -> AlertInboxResponse:
        day = self._day()
        assessments = self._assessments(day)
        cases = {case.trigger.event_id: case for case in day.financial_cases}
        items = [
            self._item(assessment, cases.get(event_id))
            for event_id, assessment in assessments.items()
        ]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        counts = {item_category: 0 for item_category in AlertCategory}
        for item in items:
            counts[item.category] += 1
        if category is not None:
            items = [item for item in items if item.category == category]
        return AlertInboxResponse(
            day_id=day.day_id,
            run_id=day.run_id,
            generated_at=datetime.now(timezone.utc),
            counts=counts,
            items=items,
        )

    async def alert_detail(self, case_id: str) -> AlertDetailResponse:
        day = self._day()
        case = next((item for item in day.financial_cases if item.case_id == case_id), None)
        if case is None:
            raise ValueError("Unknown financial case")
        assessment = self._assessments(day).get(case.trigger.event_id)
        if assessment is None:
            raise ValueError("The case does not have a retained event assessment")
        instrument = case.instrument or case.trigger.instrument or case.trigger.symbol
        intraday = await self.market_data.get_intraday(instrument) if instrument else []
        benchmark = await self.market_data.get_index_quote("NIFTY 50")
        sector = (
            await self.market_data.get_sector_snapshot(case.trigger.sector)
            if case.trigger.sector
            else None
        )
        return AlertDetailResponse(
            day_id=day.day_id,
            run_id=day.run_id,
            generated_at=datetime.now(timezone.utc),
            case=case,
            assessment=assessment,
            item=self._item(assessment, case),
            intraday=intraday,
            benchmark=benchmark,
            sector=sector,
        )

    async def timeline(self) -> TimelineResponse:
        day = self._day()
        next_checkpoint = next(
            (step for step in day.timeline if step.status in {StepStatus.PENDING, StepStatus.RUNNING}),
            None,
        )
        return TimelineResponse(
            day_id=day.day_id,
            run_id=day.run_id,
            trading_date=day.trading_date,
            generated_at=datetime.now(timezone.utc),
            status=day.status,
            run_mode=day.run_mode,
            completed_count=sum(step.status == StepStatus.COMPLETE for step in day.timeline),
            total_count=len(day.timeline),
            active_step_id=day.active_step_id,
            next_checkpoint=next_checkpoint,
            timeline=day.timeline,
            financial_day=day,
        )

    async def copilot_bootstrap(self, conversation_id: str | None = None) -> CopilotBootstrapResponse:
        dashboard = await dashboard_service.get_dashboard()
        day = self._day()
        record = conversation_store.get(conversation_id) if conversation_id else None
        active_case_count = sum(
            case.status != FinancialCaseStatus.CLOSED for case in day.financial_cases
        )
        suggestions = [
            "What deserves my attention right now?",
            "Summarize my largest portfolio exposures.",
            "What changed since my morning briefing?",
            "Explain today's portfolio movement simply.",
        ]
        if dashboard.important_event is not None:
            suggestions.insert(0, "Why does the latest alert matter to my portfolio?")
        context = (
            f"{dashboard.portfolio.holdings_count} holdings, "
            f"{len(dashboard.daily_brief.stories)} relevant stories, "
            f"and {active_case_count} active financial {'case' if active_case_count == 1 else 'cases'}."
        )
        if record and record.active_event_id:
            context += f" Continuing event {record.active_event_id}."
        elif record and record.active_story_id:
            context += f" Continuing story {record.active_story_id}."
        return CopilotBootstrapResponse(
            day_id=day.day_id,
            run_id=day.run_id,
            generated_at=datetime.now(timezone.utc),
            conversation_id=conversation_id,
            context_summary=context,
            suggested_questions=suggestions[:4],
            holdings_count=dashboard.portfolio.holdings_count,
            relevant_story_count=len(dashboard.daily_brief.stories),
            active_case_count=active_case_count,
            saved_story_count=len(day.saved_stories),
            saved_event_count=len(day.saved_events),
            voice_call_enabled=voice_session_service.configured(),
            voice_call_reason=(
                None
                if voice_session_service.configured()
                else "Live call is not configured yet."
            ),
        )

    def stream_snapshot(self) -> StreamSnapshot:
        day = self._day()
        audio = [
            item
            for item in [day.morning_brief_id, day.evening_brief_id, day.story_audio_brief_id]
            if item
        ]
        return StreamSnapshot(
            day_id=day.day_id,
            run_id=day.run_id,
            status=day.status,
            completed_steps=[
                step.step_id for step in day.timeline if step.status == StepStatus.COMPLETE
            ],
            case_versions={case.case_id: case.updated_at for case in day.financial_cases},
            alert_event_ids=[item.event.event_id for item in day.events_alerted],
            ready_audio_ids=audio,
        )


product_api_service = ProductApiService()
