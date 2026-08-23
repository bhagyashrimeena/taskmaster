"""Deterministic operations that turn existing intelligence into one financial day."""

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4

from ..agents.portfolio_agent import get_portfolio_summary
from ..config import application_today, get_settings
from ..dashboard.service import dashboard_service
from ..events import EventDecisionEngine, daily_event_store, get_event_fixture
from ..events.schemas import EventAssessment, EventDecision, EventSeverity
from ..cases import FinancialCaseStatus, financial_case_service
from ..market_data import MarketDataProvider, get_market_data_provider
from ..media.schemas import AudioBriefType
from ..media.service import media_service
from ..portfolio.schemas import PortfolioSummary
from ..story.service import DailyStoryService
from ..simulation import simulation_service
from ..taskmaster import TaskmasterDecision, taskmaster_operator
from .schemas import (
    DayRunMode,
    DayStatus,
    FinancialDayState,
    HoldingContribution,
    MarketCloseReview,
    PortfolioHealth,
    PortfolioHealthStatus,
    PortfolioSnapshot,
    SnapshotHolding,
    StepStatus,
    TomorrowEvent,
)
from .active import ArtifactProvenance, AttentionDisposition
from .store import FinancialDayStore, financial_day_store


class DayOrchestrator:
    """Runs known checkpoints; it never asks a model what operation comes next."""

    step_order = (
        "morning", "health", "open", "event", "watch", "sector", "learning",
        "close", "intelligence", "actions", "evening", "tomorrow", "story",
    )

    def __init__(
        self,
        store: FinancialDayStore | None = None,
        *,
        step_timeout_seconds: float | None = None,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        self.store = store or financial_day_store
        self._task: asyncio.Task | None = None
        self._task_date: date | None = None
        self._lock = asyncio.Lock()
        self.market_data = market_data_provider or get_market_data_provider()
        self.step_timeout_seconds = (
            step_timeout_seconds
            if step_timeout_seconds is not None
            else get_settings().demo_step_timeout_seconds
        )

    def _advance_developer_clock(self, trading_date: date, checkpoint: str) -> None:
        """Advance fixture time only for demo modes or the fixture trading date."""

        state = self.store.get(trading_date)
        fixture_date = simulation_service.snapshot().as_of.date()
        if state.run_mode in {
            DayRunMode.DEMO,
            DayRunMode.PRESENTATION,
        } or trading_date == fixture_date:
            requested_hour, requested_minute = (
                int(part) for part in checkpoint.split(":")
            )
            requested = requested_hour * 60 + requested_minute
            available = [
                snapshot.checkpoint
                for snapshot in simulation_service.scenario().snapshots
            ]
            eligible = [
                candidate
                for candidate in available
                if sum(
                    part * multiplier
                    for part, multiplier in zip(
                        (int(value) for value in candidate.split(":")),
                        (60, 1),
                        strict=True,
                    )
                )
                <= requested
            ]
            simulation_service.advance_to(eligible[-1] if eligible else available[0])

    @staticmethod
    async def _portfolio() -> PortfolioSummary:
        result = await get_portfolio_summary()
        if result.get("status") != "ok":
            raise RuntimeError(result.get("error") or "Portfolio is unavailable")
        return PortfolioSummary.model_validate(result["data"])

    @staticmethod
    def _snapshot(portfolio: PortfolioSummary, session: str) -> PortfolioSnapshot:
        holdings: list[SnapshotHolding] = []
        portfolio_return = 0.0
        for holding in portfolio.holdings:
            if session == "open":
                daily_return = 0.0
            elif holding.previous_close:
                daily_return = float(
                    (holding.current_price - holding.previous_close)
                    / holding.previous_close
                    * 100
                )
            else:
                daily_return = 0.0
            weight = float(holding.portfolio_weight)
            portfolio_return += weight * daily_return / 100
            holdings.append(
                SnapshotHolding(
                    symbol=holding.symbol,
                    sector=holding.sector or "Unclassified",
                    market_value=float(holding.market_value),
                    portfolio_weight=weight,
                    daily_return_pct=round(daily_return, 2),
                )
            )
        value = float(portfolio.portfolio_value)
        return PortfolioSnapshot(
            captured_at=portfolio.as_of,
            session=session,
            source=portfolio.source,
            portfolio_value=value,
            holdings=holdings,
        )

    def _step_start(self, trading_date: date, step_id: str) -> None:
        def mutate(state: FinancialDayState) -> None:
            now = datetime.now(timezone.utc)
            step = next(item for item in state.timeline if item.step_id == step_id)
            step.status = StepStatus.RUNNING
            step.started_at = now
            step.completed_at = None
            step.detail = "Running this financial-day checkpoint."
            state.status = DayStatus.RUNNING
            if state.started_at is None:
                state.started_at = now
            state.active_step_id = step_id
            state.heartbeat_at = now
            state.last_error = None

        self.store.update(mutate, trading_date)

    def _step_complete(
        self, trading_date: date, step_id: str, detail: str, linked_ids: list[str] | None = None
    ) -> FinancialDayState:
        def mutate(state: FinancialDayState) -> None:
            now = datetime.now(timezone.utc)
            step = next(item for item in state.timeline if item.step_id == step_id)
            step.status = StepStatus.COMPLETE
            step.completed_at = now
            step.detail = detail
            step.linked_ids = linked_ids or []
            state.active_step_id = None
            state.heartbeat_at = now

        return self.store.update(mutate, trading_date)

    def _step_failed(self, trading_date: date, step_id: str, exc: BaseException) -> None:
        def mutate(state: FinancialDayState) -> None:
            now = datetime.now(timezone.utc)
            step = next(item for item in state.timeline if item.step_id == step_id)
            step.status = StepStatus.FAILED
            step.completed_at = now
            if isinstance(exc, TimeoutError):
                step.detail = "This checkpoint timed out. Run Demo Day again to retry safely."
            elif isinstance(exc, asyncio.CancelledError):
                step.detail = "This checkpoint was interrupted. Run Demo Day again to resume safely."
            else:
                step.detail = "This checkpoint could not complete; earlier day state is intact."
            state.status = DayStatus.FAILED
            state.active_step_id = None
            state.heartbeat_at = now
            state.last_error = f"{step_id}: {type(exc).__name__}"

        self.store.update(mutate, trading_date)

    async def run_morning_pulse(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "morning")
        try:
            self._advance_developer_clock(selected, "07:00")
            dashboard = await dashboard_service.get_dashboard()
            portfolio = await self._portfolio()
            brief = await media_service.prepare(
                AudioBriefType.MORNING, self.store.get(selected)
            )
            snapshot = self._snapshot(portfolio, "open")
            story_ids = [story.id for story in dashboard.daily_brief.stories]

            def mutate(state: FinancialDayState) -> None:
                state.morning_brief_id = brief.brief_id
                state.portfolio_open_snapshot = snapshot
                state.news_considered = [
                    story.id for story in dashboard.daily_brief.stories
                ]
                state.top_stories = story_ids
                state.attention_summary = dashboard.attention_summary
                state.morning_pulse_provenance = ArtifactProvenance(
                    day_id=state.day_id,
                    run_id=state.run_id,
                    source_checkpoint="07:00",
                    source_snapshot_id=brief.brief_id,
                    generated_at=brief.generated_at,
                )
                state.attention_summary = dashboard.attention_summary

            self.store.update(mutate, selected)
            return self._step_complete(
                selected,
                "morning",
                f"{dashboard.daily_brief.candidate_count} stories scanned; {len(story_ids)} most relevant.",
                [brief.brief_id, *story_ids],
            )
        except Exception as exc:
            self._step_failed(selected, "morning", exc)
            raise

    async def run_portfolio_health(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "health")
        try:
            self._advance_developer_clock(selected, "08:00")
            portfolio = await self._portfolio()
            largest_holding = max(portfolio.holdings, key=lambda item: item.portfolio_weight)
            largest_sector = max(portfolio.sector_exposure, key=lambda item: item.portfolio_weight)
            flags = [
                f"{item.symbol} represents {float(item.portfolio_weight):.2f}% of the portfolio."
                for item in portfolio.holdings
                if float(item.portfolio_weight) >= 15
            ]
            flags.extend(
                f"{item.sector} represents {float(item.portfolio_weight):.2f}% of the portfolio."
                for item in portfolio.sector_exposure
                if float(item.portfolio_weight) >= 30
            )
            current = self.store.get(selected)
            critical = len(current.events_alerted)
            status = (
                PortfolioHealthStatus.ATTENTION
                if critical or len(flags) >= 2
                else PortfolioHealthStatus.WATCH
                if flags
                else PortfolioHealthStatus.NORMAL
            )
            health = PortfolioHealth(
                assessed_at=datetime.now(timezone.utc),
                largest_holding=largest_holding.symbol,
                largest_holding_pct=float(largest_holding.portfolio_weight),
                largest_sector=largest_sector.sector,
                largest_sector_pct=float(largest_sector.portfolio_weight),
                concentration_flags=flags,
                relevant_overnight_events=len(current.top_stories),
                critical_events=critical,
                status=status,
                explanation=(
                    f"{len(flags)} concentration {'flag' if len(flags) == 1 else 'flags'} and "
                    f"{critical} critical {'event' if critical == 1 else 'events'} were found. "
                    "This is an attention classification, not an investment recommendation."
                ),
            )
            self.store.update(lambda state: setattr(state, "portfolio_health", health), selected)
            return self._step_complete(
                selected,
                "health",
                f"{status.value} · {len(flags)} concentration {'flag' if len(flags) == 1 else 'flags'}.",
            )
        except Exception as exc:
            self._step_failed(selected, "health", exc)
            raise

    async def run_market_open_monitor(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "open")
        try:
            snapshot = await self.market_data.get_market_snapshot()

            def mutate(state: FinancialDayState) -> None:
                if snapshot.snapshot_id not in state.market_snapshot_ids:
                    state.market_snapshot_ids.append(snapshot.snapshot_id)

            self.store.update(mutate, selected)
            return self._step_complete(
                selected,
                "open",
                f"Compared {len(snapshot.quotes)} portfolio instruments with index and sector context.",
                [snapshot.snapshot_id],
            )
        except Exception as exc:
            self._step_failed(selected, "open", exc)
            raise

    async def run_adaptive_market_watch(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "watch")
        try:
            snapshot = await self.market_data.get_market_snapshot()
            observed_at = datetime.now(timezone.utc)

            def mutate(state: FinancialDayState) -> None:
                if snapshot.snapshot_id not in state.market_snapshot_ids:
                    state.market_snapshot_ids.append(snapshot.snapshot_id)
                state.market_watch_runs.append(observed_at)

            self.store.update(mutate, selected)
            return self._step_complete(
                selected,
                "watch",
                f"Observed {len(snapshot.quotes)} instruments; no move crossed the alert rules.",
                [snapshot.snapshot_id],
            )
        except Exception as exc:
            self._step_failed(selected, "watch", exc)
            raise

    async def run_sector_deep_dive(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "sector")
        try:
            portfolio = await self._portfolio()
            current = self.store.get(selected)
            case_sectors = [
                item.trigger.sector
                for item in current.financial_cases
                if item.trigger.sector and item.status != FinancialCaseStatus.CLOSED
            ]
            selected_sector = (
                case_sectors[0]
                if case_sectors
                else max(portfolio.sector_exposure, key=lambda item: item.market_value).sector
            )
            exposure = next(
                (
                    float(item.portfolio_weight)
                    for item in portfolio.sector_exposure
                    if item.sector == selected_sector
                ),
                0.0,
            )
            self.store.update(
                lambda state: setattr(state, "selected_sector", selected_sector), selected
            )
            return self._step_complete(
                selected,
                "sector",
                f"{selected_sector} selected as today’s relevant sector ({exposure:.2f}% portfolio exposure).",
            )
        except Exception as exc:
            self._step_failed(selected, "sector", exc)
            raise

    async def run_contextual_learning(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "learning")
        try:
            current = self.store.get(selected)
            active_case = next(
                (
                    item
                    for item in current.financial_cases
                    if item.status != FinancialCaseStatus.CLOSED
                ),
                None,
            )
            if active_case and active_case.trigger.price_change_pct is not None and active_case.trigger.sector_change_pct is not None:
                topic = "Sector divergence"
                detail = "Explains why a holding can move differently from its sector using today's retained case."
            elif current.portfolio_health and current.portfolio_health.concentration_flags:
                topic = "Portfolio concentration"
                detail = "Explains concentration using today's calculated portfolio health."
            else:
                topic = "Diversification"
                detail = "Explains diversification using today's asset allocation."
            self.store.update(
                lambda state: setattr(state, "learning_topic", topic), selected
            )
            return self._step_complete(selected, "learning", f"{topic} · {detail}")
        except Exception as exc:
            self._step_failed(selected, "learning", exc)
            raise

    async def handle_market_event(
        self, event_id: str | None = None, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "event")
        try:
            self._advance_developer_clock(selected, "12:17")
            portfolio = await self._portfolio()
            day_state = self.store.get(selected)
            event = get_event_fixture(event_id) if event_id is not None else None
            if event_id is None and day_state.run_mode != DayRunMode.REAL:
                event = simulation_service.get_market_event()
            if event is None:
                return self._step_complete(
                    selected,
                    "event",
                    "No market event crossed an interruption threshold.",
                )
            assessment = await EventDecisionEngine(store=daily_event_store).assess(
                event,
                portfolio,
                day_id=day_state.day_id,
                run_id=day_state.run_id,
            )
            self.record_event(assessment, selected)
            return self._step_complete(
                selected,
                "event",
                f"{assessment.event.company or assessment.event.symbol} · {assessment.decision.value} · relevance {assessment.relevance_score:.2f}.",
                [event.event_id],
            )
        except Exception as exc:
            self._step_failed(selected, "event", exc)
            raise

    def record_event(
        self, assessment: EventAssessment, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()

        def mutate(state: FinancialDayState) -> None:
            already_recorded = any(
                item.event.event_id == assessment.event.event_id
                for item in state.events_detected
            )

            def upsert(items: list[EventAssessment]) -> None:
                items[:] = [item for item in items if item.event.event_id != assessment.event.event_id]
                items.append(assessment)

            upsert(state.events_detected)
            state.events_alerted[:] = [
                item for item in state.events_alerted if item.event.event_id != assessment.event.event_id
            ]
            state.events_ignored[:] = [
                item for item in state.events_ignored if item.event.event_id != assessment.event.event_id
            ]
            if assessment.decision == EventDecision.ALERT:
                state.events_alerted.append(assessment)
                uncertainty = (
                    f"The confirmed cause of {assessment.event.company or assessment.event.symbol}'s move remains unresolved."
                )
                if uncertainty not in state.unresolved_items:
                    state.unresolved_items.append(uncertainty)
            elif assessment.decision == EventDecision.IGNORE:
                state.events_ignored.append(assessment)

            existing_case = next(
                (
                    item
                    for item in state.financial_cases
                    if item.trigger.event_id == assessment.event.event_id
                ),
                None,
            )
            financial_case = financial_case_service.from_assessment(
                assessment, existing=existing_case
            )
            if financial_case and existing_case is None:
                state.financial_cases.append(financial_case)

            cycle = taskmaster_operator.operate_event(assessment, financial_case)
            if (
                cycle.decision == TaskmasterDecision.INTERRUPT_NOW
                and state.attention_budget.interrupted
                >= state.attention_budget.interrupt_limit
                and assessment.event.severity != EventSeverity.CRITICAL
            ):
                cycle.decision = TaskmasterDecision.DEFER_TO_EVENING
                cycle.reason = (
                    "The daily interruption budget is exhausted; retain this for the evening wrap."
                )
            state.operator_cycles[:] = [
                item for item in state.operator_cycles if item.cycle_id != cycle.cycle_id
            ]
            state.operator_cycles.append(cycle)
            if not already_recorded:
                disposition = {
                    TaskmasterDecision.INTERRUPT_NOW: AttentionDisposition.INTERRUPTED,
                    TaskmasterDecision.MONITOR: AttentionDisposition.MONITORED,
                    TaskmasterDecision.CLOSE_CASE: AttentionDisposition.IGNORED,
                }.get(cycle.decision, AttentionDisposition.DEFERRED)
                state.attention_budget.record(disposition)
            state.open_case_ids = [
                item.case_id
                for item in state.financial_cases
                if item.status != FinancialCaseStatus.CLOSED
            ]

        return self.store.update(mutate, selected)

    async def run_market_close(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "close")
        try:
            self._advance_developer_clock(selected, "15:30")
            portfolio = await self._portfolio()
            current = self.store.get(selected)
            open_snapshot = current.portfolio_open_snapshot or self._snapshot(portfolio, "open")
            close_snapshot = self._snapshot(portfolio, "close")
            open_weights = {
                item.symbol: item.portfolio_weight for item in open_snapshot.holdings
            }
            contributions = [
                HoldingContribution(
                    symbol=item.symbol,
                    portfolio_weight_pct=open_weights.get(item.symbol, item.portfolio_weight),
                    daily_return_pct=item.daily_return_pct,
                    contribution_percentage_points=round(
                        open_weights.get(item.symbol, item.portfolio_weight)
                        * item.daily_return_pct
                        / 100,
                        2,
                    ),
                    direction=(
                        "positive" if item.daily_return_pct > 0 else "negative" if item.daily_return_pct < 0 else "flat"
                    ),
                )
                for item in close_snapshot.holdings
            ]
            positives = sorted(
                (item for item in contributions if item.contribution_percentage_points > 0),
                key=lambda item: item.contribution_percentage_points,
                reverse=True,
            )[:3]
            negatives = sorted(
                (item for item in contributions if item.contribution_percentage_points < 0),
                key=lambda item: item.contribution_percentage_points,
            )[:3]
            portfolio_return = round(
                sum(item.contribution_percentage_points for item in contributions), 2
            )
            alerts = [item.event.event_id for item in current.events_alerted]
            advisor_request_ids = [item.request_id for item in current.advisor_requests]
            advisor_response_ids = [item.response_id for item in current.advisor_responses]
            driver = negatives[0].symbol if negatives else positives[0].symbol if positives else "No single holding"
            review = MarketCloseReview(
                generated_at=datetime.now(timezone.utc),
                portfolio_return_pct=portfolio_return,
                top_positive_contributors=positives,
                top_negative_contributors=negatives,
                alert_event_ids=alerts,
                advisor_request_ids=advisor_request_ids,
                advisor_response_ids=advisor_response_ids,
                explanation=(
                    f"The portfolio moved {portfolio_return:+.2f}% in the closing simulation. "
                    f"{driver} was the largest contributor by magnitude. "
                    f"{len(alerts)} alert event(s) and {len(advisor_response_ids)} advisor response(s) "
                    "from earlier today were carried into this review."
                ),
                provenance=ArtifactProvenance(
                    day_id=current.day_id,
                    run_id=current.run_id,
                    source_checkpoint="15:30",
                    source_snapshot_id=close_snapshot.captured_at.isoformat(),
                    generated_at=datetime.now(timezone.utc),
                ),
            )

            def mutate(state: FinancialDayState) -> None:
                state.portfolio_open_snapshot = open_snapshot
                state.portfolio_close_snapshot = close_snapshot
                state.market_close_review = review

            self.store.update(mutate, selected)
            return self._step_complete(
                selected, "close", f"Portfolio {portfolio_return:+.2f}% · {driver} drove the largest move.", alerts
            )
        except Exception as exc:
            self._step_failed(selected, "close", exc)
            raise

    async def run_portfolio_intelligence(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "intelligence")
        try:
            portfolio = await self._portfolio()
            holdings = sorted(
                portfolio.holdings, key=lambda item: item.portfolio_weight, reverse=True
            )
            top_three = sum(float(item.portfolio_weight) for item in holdings[:3])
            current = self.store.get(selected)
            case_count = len(current.open_case_ids)
            gap_count = len(current.unresolved_items)
            summary = (
                f"Top three holdings are {top_three:.2f}% of value; "
                f"{case_count} {'case remains' if case_count == 1 else 'cases remain'} open and "
                f"{gap_count} research {'gap remains' if gap_count == 1 else 'gaps remain'}."
            )
            self.store.update(
                lambda state: setattr(
                    state, "portfolio_intelligence_summary", summary
                ),
                selected,
            )
            return self._step_complete(selected, "intelligence", summary)
        except Exception as exc:
            self._step_failed(selected, "intelligence", exc)
            raise

    async def run_action_queue(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "actions")
        try:
            current = self.store.get(selected)
            queue = [
                f"Review {item.instrument or item.trigger.event_id} · {item.status.value}"
                for item in current.financial_cases
                if item.status != FinancialCaseStatus.CLOSED
            ]
            queue.extend(f"Resolve: {item}" for item in current.unresolved_items)
            queue = list(dict.fromkeys(queue))
            self.store.update(
                lambda state: setattr(state, "action_queue", queue), selected
            )
            detail = (
                "Nothing needs review or follow-up."
                if not queue
                else f"{len(queue)} {'item is' if len(queue) == 1 else 'items are'} ready for review or follow-up."
            )
            return self._step_complete(
                selected,
                "actions",
                detail,
            )
        except Exception as exc:
            self._step_failed(selected, "actions", exc)
            raise

    async def run_evening_wrap(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "evening")
        try:
            self._advance_developer_clock(selected, "20:00")
            brief = await media_service.prepare(
                AudioBriefType.EVENING, self.store.get(selected)
            )
            self.store.update(lambda state: setattr(state, "evening_brief_id", brief.brief_id), selected)
            current = self.store.get(selected)
            return self._step_complete(
                selected,
                "evening",
                f"Wrap prepared from {len(current.events_alerted)} alert(s), {len(current.saved_stories)} save(s), "
                f"{len(current.questions_asked)} question(s), and {len(current.advisor_responses)} advisor response(s).",
                [brief.brief_id],
            )
        except Exception as exc:
            self._step_failed(selected, "evening", exc)
            raise

    async def prepare_tomorrow(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "tomorrow")
        try:
            self._advance_developer_clock(selected, "21:00")
            portfolio = await self._portfolio()
            weights = {item.symbol: float(item.portfolio_weight) for item in portfolio.holdings}
            sectors = {item.sector: float(item.portfolio_weight) for item in portfolio.sector_exposure}
            ist = ZoneInfo("Asia/Kolkata")
            tomorrow = selected + timedelta(days=1)
            candidates = [
                TomorrowEvent(
                    event_id="tomorrow-hdfc-investor-update",
                    title="HDFC Bank investor update",
                    scheduled_at=datetime.combine(tomorrow, time(10, 0), ist),
                    event_type="company_update",
                    affected_holdings=["HDFCBANK"],
                    affected_sector="Financial Services",
                    portfolio_exposure_pct=weights.get("HDFCBANK", 0),
                    why_relevant="A scheduled company update directly relates to a large portfolio holding.",
                    relevance_rank=0,
                ),
                TomorrowEvent(
                    event_id="tomorrow-rbi-liquidity",
                    title="RBI liquidity announcement",
                    scheduled_at=datetime.combine(tomorrow, time(14, 0), ist),
                    event_type="macro",
                    affected_holdings=["HDFCBANK", "ICICIBANK"],
                    affected_sector="Financial Services",
                    portfolio_exposure_pct=sectors.get("Financial Services", 0),
                    why_relevant="The scheduled announcement relates to the portfolio's financial-services exposure.",
                    relevance_rank=0,
                ),
                TomorrowEvent(
                    event_id="tomorrow-infosys-investor-event",
                    title="Infosys scheduled investor event",
                    scheduled_at=datetime.combine(tomorrow, time(16, 30), ist),
                    event_type="investor_event",
                    affected_holdings=["INFY"],
                    affected_sector="Information Technology",
                    portfolio_exposure_pct=weights.get("INFY", 0),
                    why_relevant="The event directly references a portfolio holding and its sector context.",
                    relevance_rank=0,
                ),
            ]
            candidates.sort(key=lambda item: item.portfolio_exposure_pct, reverse=True)
            for rank, item in enumerate(candidates, 1):
                item.relevance_rank = rank
            selected_events = candidates[:2]
            self.store.update(lambda state: setattr(state, "tomorrow_events", selected_events), selected)
            return self._step_complete(
                selected, "tomorrow", f"{len(selected_events)} portfolio-relevant events ranked for tomorrow.", [item.event_id for item in selected_events]
            )
        except Exception as exc:
            self._step_failed(selected, "tomorrow", exc)
            raise

    async def generate_daily_story(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        self._step_start(selected, "story")
        try:
            story = await DailyStoryService(self.store).prepare(selected)
            completed = self._step_complete(
                selected,
                "story",
                f"{len(story.scenes)} moments · {story.duration_seconds} sec recap ready.",
                [story.story_id, *( [story.audio_brief_id] if story.audio_brief_id else [] )],
            )
            if all(step.status == StepStatus.COMPLETE for step in completed.timeline):
                def finish(state: FinancialDayState) -> None:
                    now = datetime.now(timezone.utc)
                    state.status = DayStatus.COMPLETE
                    state.completed_at = now
                    state.active_step_id = None
                    state.heartbeat_at = now

                completed = self.store.update(finish, selected)
            return completed
        except Exception as exc:
            self._step_failed(selected, "story", exc)
            raise

    def _initialize_demo(self, selected: date, duration_seconds: float) -> None:
        simulation_service.reset_scenario()
        def initialize(state: FinancialDayState) -> None:
            attempt = state.run_attempt + 1
            fresh = FinancialDayState(trading_date=selected)
            fresh.run_id = f"run-{selected.isoformat()}-{uuid4().hex[:12]}"
            fresh.scenario_id = simulation_service.state().scenario_id
            event = simulation_service.get_market_event()
            event_step = next(item for item in fresh.timeline if item.step_id == "event")
            event_step.scheduled_time = "12:17"
            event_step.label = (
                f"{event.company or event.sector} event" if event else "Market event check"
            )
            for name, value in fresh:
                setattr(state, name, value)
            now = datetime.now(timezone.utc)
            state.status = DayStatus.RUNNING
            state.run_mode = DayRunMode.DEMO
            state.started_at = now
            state.heartbeat_at = now
            state.simulated_duration_seconds = int(duration_seconds)
            state.run_attempt = attempt

        self.store.update(initialize, selected)

    async def initialize_presentation_day(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        """Start a fresh clock-driven day without launching the legacy replay loop."""

        selected = trading_date or application_today()
        await self.cancel_background_run()
        self._initialize_demo(selected, 0)

        def mark_presentation(state: FinancialDayState) -> None:
            state.run_mode = DayRunMode.PRESENTATION
            state.simulated_duration_seconds = None

        return self.store.update(mark_presentation, selected)

    def complete_presentation_day(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        """Mark a clock-driven day complete after its final idempotent checkpoint."""

        selected = trading_date or application_today()

        def finish(state: FinancialDayState) -> None:
            now = datetime.now(timezone.utc)
            state.status = DayStatus.COMPLETE
            state.completed_at = now
            state.active_step_id = None
            state.heartbeat_at = now
            state.last_error = None

        return self.store.update(finish, selected)

    async def cancel_background_run(self) -> None:
        """Stop only the legacy sequential replay task, if one is active."""

        async with self._lock:
            task = self._task
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._task = None
            self._task_date = None

    @staticmethod
    def _operation_map(orchestrator: "DayOrchestrator"):
        return (
            ("morning", orchestrator.run_morning_pulse),
            ("health", orchestrator.run_portfolio_health),
            ("open", orchestrator.run_market_open_monitor),
            ("watch", orchestrator.run_adaptive_market_watch),
            ("sector", orchestrator.run_sector_deep_dive),
            ("event", orchestrator.handle_market_event),
            ("learning", orchestrator.run_contextual_learning),
            ("close", orchestrator.run_market_close),
            ("intelligence", orchestrator.run_portfolio_intelligence),
            ("actions", orchestrator.run_action_queue),
            ("evening", orchestrator.run_evening_wrap),
            ("tomorrow", orchestrator.prepare_tomorrow),
            ("story", orchestrator.generate_daily_story),
        )

    async def run_demo_day(
        self,
        trading_date: date | None = None,
        *,
        duration_seconds: float = 72,
        resume: bool = False,
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        if not resume:
            self._initialize_demo(selected, duration_seconds)
        else:
            def mark_resuming(state: FinancialDayState) -> None:
                interrupted = any(
                    step.status in {StepStatus.RUNNING, StepStatus.FAILED}
                    for step in state.timeline
                )
                state.status = DayStatus.RUNNING
                state.run_mode = DayRunMode.DEMO
                state.last_error = None
                state.heartbeat_at = datetime.now(timezone.utc)
                if interrupted:
                    state.run_attempt += 1
                for step in state.timeline:
                    if step.status in {StepStatus.RUNNING, StepStatus.FAILED}:
                        step.status = StepStatus.PENDING
                        step.completed_at = None
                        step.detail = "Resuming this checkpoint after an interruption."

            self.store.update(mark_resuming, selected)

        operations = self._operation_map(self)
        delay = max(0.0, duration_seconds / len(operations))
        active_step = self.store.get(selected).active_step_id or "morning"
        try:
            remaining = [
                (step_id, operation)
                for step_id, operation in operations
                if next(
                    step
                    for step in self.store.get(selected).timeline
                    if step.step_id == step_id
                ).status
                != StepStatus.COMPLETE
            ]
            for index, (step_id, operation) in enumerate(remaining):
                active_step = step_id
                try:
                    await asyncio.wait_for(
                        operation(trading_date=selected),
                        timeout=self.step_timeout_seconds,
                    )
                except TimeoutError as exc:
                    self._step_failed(selected, step_id, exc)
                    raise
                if index < len(remaining) - 1 and delay:
                    await asyncio.sleep(delay)

            def finish(state: FinancialDayState) -> None:
                now = datetime.now(timezone.utc)
                state.status = DayStatus.COMPLETE
                state.completed_at = now
                state.active_step_id = None
                state.heartbeat_at = now
                state.last_error = None

            return self.store.update(finish, selected)
        except asyncio.CancelledError as exc:
            current = self.store.get(selected)
            if current.status == DayStatus.RUNNING:
                self._step_failed(selected, current.active_step_id or active_step, exc)
            raise

    def _supervise(self, task: asyncio.Task, selected: date) -> None:
        if self._task is not task:
            return
        try:
            error = task.exception()
        except asyncio.CancelledError as exc:
            error = exc
        if error is not None:
            state = self.store.get(selected)
            if state.status == DayStatus.RUNNING:
                self._step_failed(
                    selected,
                    state.active_step_id or "morning",
                    error,
                )

    def _launch(self, selected: date, duration: float, *, resume: bool) -> None:
        task = asyncio.create_task(
            self.run_demo_day(
                selected,
                duration_seconds=duration,
                resume=resume,
            )
        )
        self._task = task
        self._task_date = selected
        task.add_done_callback(lambda completed: self._supervise(completed, selected))

    async def start_demo_day(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        async with self._lock:
            if self._task and not self._task.done():
                return self.store.get(selected)
            duration = get_settings().demo_day_duration_seconds
            self._initialize_demo(selected, duration)
            self._launch(selected, duration, resume=True)
            return self.store.get(selected)

    async def recover_interrupted_demo(
        self, trading_date: date | None = None
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        async with self._lock:
            state = self.store.get(selected)
            if state.status != DayStatus.RUNNING or state.run_mode != "demo":
                return state
            if self._task and not self._task.done():
                return state
            duration = (
                state.simulated_duration_seconds
                if state.simulated_duration_seconds is not None
                else get_settings().demo_day_duration_seconds
            )
            self._launch(selected, duration, resume=True)
            return self.store.get(selected)

    def current_state(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        state = self.store.get(selected)
        if (
            state.status == DayStatus.RUNNING
            and self._task_date == selected
            and self._task is not None
            and self._task.done()
        ):
            try:
                error = self._task.exception()
            except asyncio.CancelledError as exc:
                error = exc
            if error is not None:
                self._step_failed(
                    selected, state.active_step_id or "morning", error
                )
                state = self.store.get(selected)
        return state


day_orchestrator = DayOrchestrator()
