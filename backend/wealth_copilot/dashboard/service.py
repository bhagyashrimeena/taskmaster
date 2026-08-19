"""Fast bootstrap and non-blocking refresh service for the dashboard."""

import asyncio
from datetime import datetime, time, timezone
import json
from uuid import uuid4

from google.adk.runners import InMemoryRunner
from google.genai import types

from ..agents.daily_brief_workflow import (
    NEWS_METADATA_KEY,
    CachedMarketFetchAgent,
)
from ..agents.market_agent import create_market_agent
from ..agents.portfolio_agent import get_portfolio_summary
from ..config import get_settings
from ..events import EventDecisionEngine, daily_event_store
from ..events.schemas import EventSeverity, MarketEvent, MarketEventType
from ..market.cache import news_candidate_cache, refresh_news
from ..market.canonical import resolve_canonical_urls, story_identity
from ..interaction.memory import daily_interaction_store
from ..market.demo_provider import SimulatedNewsProvider
from ..portfolio.schemas import PortfolioSummary
from ..relevance import DiversityRanker, RelevanceEngine
from ..simulation import simulation_service
from ..day.schemas import FinancialDayState
from ..day.active import ArtifactProvenance
from ..day.integrity import build_attention_summary, checkpoint_released, presentation_minute
from ..events.schemas import (
    EventAssessment,
    EventDecision,
    EventSeverity,
    EventTraceStep,
    InvestigationStatus,
    MarketEvent,
    MarketEventType,
    TriggerSignal,
)
from .schemas import (
    ActivityItem,
    DailyBriefView,
    DashboardResponse,
    DataSource,
    FreshnessStatus,
    FreshnessView,
    HoldingView,
    PortfolioView,
    RefreshPhase,
    RefreshView,
    SectorView,
    StoryView,
)


settings = get_settings()


class DashboardService:
    """Assembles existing Phase 1/2 outputs without waiting for live Search."""

    def __init__(self) -> None:
        self._refresh = RefreshView()
        self._refresh_task: asyncio.Task | None = None
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_news_status: FreshnessStatus | None = None
        self._canonical_task: asyncio.Task | None = None

    @staticmethod
    def _source_label(source: str, is_live: bool) -> str:
        if source == "simulated":
            return "Simulated Portfolio"
        return "Live Portfolio" if is_live else "Portfolio"

    async def _portfolio(self, financial_day: FinancialDayState | None = None) -> PortfolioSummary:
        if financial_day and financial_day.run_mode == "presentation":
            minute = presentation_minute(financial_day) or 7 * 60
            checkpoint = "07:00"
            for candidate in ("09:15", "12:17", "15:30", "20:00", "21:00"):
                hour, value = (int(part) for part in candidate.split(":"))
                if hour * 60 + value <= minute:
                    checkpoint = candidate
            simulation_service.advance_to(checkpoint)
        result = await get_portfolio_summary()
        if result.get("status") != "ok":
            raise RuntimeError(result.get("error") or "Portfolio is unavailable")
        return PortfolioSummary.model_validate(result["data"])

    async def _brief(
        self, portfolio: PortfolioSummary, financial_day: FinancialDayState
    ) -> DailyBriefView:
        snapshot = news_candidate_cache.snapshot()
        if snapshot is None:
            batch = await SimulatedNewsProvider().get_candidates(
                limit=settings.news_candidate_count
            )
            # This is the instant bootstrap and the safety net for a failed
            # background refresh. It never claims to be live.
            news_candidate_cache.set(batch)
            snapshot = news_candidate_cache.snapshot()
        assert snapshot is not None

        expired = snapshot.age_seconds > settings.news_cache_ttl_seconds
        if self._last_refresh_news_status == FreshnessStatus.STALE:
            freshness_status = FreshnessStatus.STALE
        elif snapshot.batch.is_live and not expired and not snapshot.refresh_required:
            freshness_status = FreshnessStatus.LIVE
        elif expired or snapshot.refresh_required:
            freshness_status = FreshnessStatus.STALE
        else:
            freshness_status = FreshnessStatus.CACHED

        feed = RelevanceEngine().rank(
            snapshot.batch.candidates,
            portfolio,
            news_source=snapshot.batch.source,
            news_is_live=snapshot.batch.is_live,
            limit=20,
            now=snapshot.batch.generated_at,
        )
        selected = DiversityRanker().select(feed, limit=5)
        canonical_urls = news_candidate_cache.canonical_urls()
        unresolved = [
            story for story in selected.stories
            if story_identity(story) not in canonical_urls
        ]
        if unresolved and snapshot.batch.is_live:
            self._schedule_canonical_resolution(unresolved)
        labels = {
            FreshnessStatus.LIVE: "Updated just now",
            FreshnessStatus.CACHED: (
                "Updated just now"
                if snapshot.age_seconds < 60
                else f"Updated {max(1, round(snapshot.age_seconds / 60))} min ago"
            ),
            FreshnessStatus.STALE: f"Last updated {max(1, round(snapshot.age_seconds / 60))} min ago",
        }
        freshness = FreshnessView(
            status=freshness_status,
            label=labels[freshness_status],
            fetched_at=snapshot.fetched_at,
            cache_age_seconds=round(snapshot.age_seconds, 2),
            refresh_attempted=self._refresh.phase
            in {RefreshPhase.QUEUED, RefreshPhase.RUNNING, RefreshPhase.COMPLETE, RefreshPhase.FAILED},
        )
        stories = [
            StoryView(
                id=story.id,
                headline=story.headline,
                summary=story.summary,
                source_name=story.source_name,
                source_url=story.source_url,
                canonical_url=(canonical_urls.get(story_identity(story)).canonical_url if canonical_urls.get(story_identity(story)) else None),
                canonical_url_status=(canonical_urls.get(story_identity(story)).status if canonical_urls.get(story_identity(story)) else "unavailable"),
                published_at=story.published_at,
                affected_holdings=story.affected_holdings,
                direct_exposure_pct=story.direct_exposure_pct,
                sector_exposure_pct=story.sector_exposure_pct,
                relevance_score=story.relevance_score,
                final_utility_score=story.final_utility_score,
                source_authority=story.source_authority.value,
                why_am_i_seeing_this=story.why_am_i_seeing_this,
            )
            for story in selected.stories
        ]
        return DailyBriefView(
            day_id=financial_day.day_id,
            run_id=financial_day.run_id,
            freshness=freshness,
            candidate_count=selected.candidate_count,
            analyzed_count=selected.deduplicated_count,
            stories=stories,
            provenance=ArtifactProvenance(
                day_id=financial_day.day_id,
                run_id=financial_day.run_id,
                source_checkpoint=(
                    (financial_day.presentation_active_checkpoint or "07:00")
                    if financial_day.run_mode == "presentation"
                    else "normal"
                ),
                source_snapshot_id=f"{snapshot.fetched_at.isoformat()}:{snapshot.batch.generated_at.isoformat()}",
                generated_at=datetime.now(timezone.utc),
            ),
        )

    def _schedule_canonical_resolution(self, stories) -> None:
        if self._canonical_task and not self._canonical_task.done():
            return

        async def resolve() -> None:
            resolutions = await resolve_canonical_urls(list(stories))
            news_candidate_cache.update_canonical_urls(resolutions)

        self._canonical_task = asyncio.create_task(resolve())

    @staticmethod
    def _portfolio_view(portfolio: PortfolioSummary) -> PortfolioView:
        previous_value = float(portfolio.portfolio_value) - float(portfolio.day_pnl or 0)
        day_change_pct = (
            round(float(portfolio.day_pnl or 0) / previous_value * 100, 2)
            if portfolio.day_pnl is not None and previous_value
            else None
        )
        holdings = []
        for holding in portfolio.holdings[:4]:
            move = None
            if holding.previous_close:
                move = round(
                    float((holding.current_price - holding.previous_close) / holding.previous_close * 100),
                    2,
                )
            holdings.append(
                HoldingView(
                    symbol=holding.symbol,
                    market_value=float(holding.market_value),
                    portfolio_weight=float(holding.portfolio_weight),
                    day_change_pct=move,
                )
            )
        return PortfolioView(
            source=DataSource(
                label=DashboardService._source_label(portfolio.source, portfolio.is_live),
                is_live=portfolio.is_live,
                provider=portfolio.provider,
                scenario_id=portfolio.scenario_id,
                checkpoint=(simulation_service.state().checkpoint if portfolio.provider == "simulated" else None),
            ),
            as_of=portfolio.as_of,
            currency=portfolio.currency,
            portfolio_value=float(portfolio.portfolio_value),
            invested_value=float(portfolio.invested_value),
            unrealized_pnl=float(portfolio.unrealized_pnl),
            day_pnl=float(portfolio.day_pnl) if portfolio.day_pnl is not None else None,
            day_change_pct=day_change_pct,
            holdings_count=len(portfolio.holdings),
            largest_holdings=holdings,
            sector_exposure=[
                SectorView(
                    sector=item.sector,
                    portfolio_weight=float(item.portfolio_weight),
                )
                for item in portfolio.sector_exposure
            ],
        )

    @staticmethod
    async def _event(portfolio: PortfolioSummary, financial_day: FinancialDayState):
        if financial_day.run_mode == "presentation" and not checkpoint_released(financial_day, "12:17"):
            snapshot = simulation_service.snapshot()
            quiet_event = MarketEvent(
                event_id=f"{financial_day.run_id}-monitoring",
                timestamp=snapshot.as_of,
                event_type=MarketEventType.MACRO,
                sector="Broad Market",
                headline="No portfolio event currently needs your attention",
                source="Simulated Market Feed",
                source_url="https://events.example/quiet-market-check",
                severity=EventSeverity.LOW,
            )
            return EventAssessment(
                day_id=financial_day.day_id,
                run_id=financial_day.run_id,
                event=quiet_event,
                portfolio_source=portfolio.source,
                direct_holding=False,
                affected_holdings=[],
                affected_portfolio_percentage=0,
                sector_exposure_percentage=0,
                trigger_detected=False,
                trigger_signals=[TriggerSignal(
                    rule="presentation_checkpoint",
                    triggered=False,
                    observed=snapshot.as_of.isoformat(),
                    threshold="12:17",
                    reason="Monitoring holdings until the event checkpoint.",
                )],
                investigation_status=InvestigationStatus.SKIPPED,
                relevance_score=0,
                decision=EventDecision.IGNORE,
                notification_required=False,
                title="Monitoring holdings",
                reason="No portfolio event currently needs your attention.",
                trace=[EventTraceStep(
                    stage="MONITORING",
                    outcome="Monitoring holdings",
                    details={"checkpoint": "12:17"},
                )],
            )
        event = simulation_service.get_market_event()
        if event is None:
            snapshot = simulation_service.snapshot()
            event = MarketEvent(
                event_id=f"{simulation_service.state().scenario_id}-market-check",
                timestamp=snapshot.as_of,
                event_type=MarketEventType.PRICE_MOVE,
                sector="Broad Market",
                price_change_pct=0.2,
                sector_change_pct=0.1,
                headline="Routine market check remains below attention thresholds",
                source="Simulated Market Feed",
                source_url="https://events.example/quiet-market-check",
                severity=EventSeverity.LOW,
            )
        durable = financial_day
        persisted = next(
            (
                item
                for item in durable.events_detected
                if item.event.event_id == event.event_id
                and item.run_id == durable.run_id
            ),
            None,
        )
        if persisted is not None:
            daily_event_store.save(persisted)
            return persisted
        day = daily_event_store.get_day(event.timestamp.date())
        existing = next(
            (
                item.assessment
                for item in day.events
                if item.assessment.event.event_id == event.event_id
                and item.assessment.run_id == financial_day.run_id
            ),
            None,
        )
        if existing is not None:
            return existing
        return await EventDecisionEngine(store=daily_event_store).assess(
            event,
            portfolio,
            day_id=financial_day.day_id,
            run_id=financial_day.run_id,
        )

    async def get_dashboard(self) -> DashboardResponse:
        from ..day.store import financial_day_store

        financial_day = financial_day_store.get()
        portfolio = await self._portfolio(financial_day)
        brief, important_event = await asyncio.gather(
            self._brief(portfolio, financial_day),
            self._event(portfolio, financial_day),
        )
        day = daily_event_store.get_day(important_event.event.timestamp.date())
        today_events = [
            item.assessment
            for item in day.events
            if item.assessment.run_id == financial_day.run_id
        ]
        trace_labels = {
            "EVENT_DETECTED": "Unusual event detected",
            "PORTFOLIO_CHECK": "Portfolio exposure checked",
            "MARKET_INVESTIGATION": "Market context investigated",
            "RELEVANCE": "Portfolio relevance calculated",
            "DECISION": "Attention decision made",
        }
        activity = [
            ActivityItem(
                stage=step.stage,
                label=trace_labels.get(step.stage, step.stage.replace("_", " ").title()),
                status="attention" if step.stage == "DECISION" else "complete",
                detail=step.outcome,
            )
            for step in important_event.trace
        ]
        high_relevance = sum(story.relevance_score >= 85 for story in brief.stories)
        attention_count = min(3, high_relevance + (1 if important_event.notification_required else 0))
        attention_summary = build_attention_summary(
            financial_day,
            [story.id for story in brief.stories],
            attention_count,
        )
        attention_label = "thing" if attention_count == 1 else "things"
        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        return DashboardResponse(
            day_id=financial_day.day_id,
            run_id=financial_day.run_id,
            generated_at=datetime.now(timezone.utc),
            greeting=greeting,
            attention_count=attention_count,
            attention_summary=attention_summary,
            attention_message=f"{attention_count} {attention_label} deserve your attention today",
            portfolio=self._portfolio_view(portfolio),
            daily_brief=brief,
            important_event=important_event,
            today_events=today_events,
            agent_activity=activity,
            refresh=self._refresh.model_copy(deep=True),
            daily_state=daily_interaction_store.get(),
            disclaimer="We surface relevant information and context. You decide what to do.",
        )

    async def start_refresh(self) -> RefreshView:
        async with self._refresh_lock:
            if self._refresh_task and not self._refresh_task.done():
                return self._refresh.model_copy(deep=True)
            now = datetime.now(timezone.utc)
            if (
                self._refresh.completed_at
                and (now - self._refresh.completed_at).total_seconds() < 300
            ):
                return self._refresh.model_copy(deep=True)
            refresh_id = uuid4().hex
            self._refresh = RefreshView(
                refresh_id=refresh_id,
                phase=RefreshPhase.QUEUED,
                started_at=datetime.now(timezone.utc),
                message="Checking for a newer market update in the background.",
            )
            self._refresh_task = asyncio.create_task(self._run_refresh(refresh_id))
            return self._refresh.model_copy(deep=True)

    async def _run_refresh(self, refresh_id: str) -> None:
        self._refresh.phase = RefreshPhase.RUNNING
        refresh_news()
        runner: InMemoryRunner | None = None
        session_id = f"dashboard-{refresh_id}"
        try:
            if settings.simulation_mode == "judge" or settings.news_provider == "simulated":
                batch = await SimulatedNewsProvider().get_candidates(
                    limit=settings.news_candidate_count
                )
                news_candidate_cache.set(batch)
                status = FreshnessStatus.CACHED
            else:
                refresh_agent = CachedMarketFetchAgent(
                    name="dashboard_market_refresh",
                    description="Refreshes the retained dashboard candidate pool.",
                    sub_agents=[create_market_agent()],
                )
                runner = InMemoryRunner(
                    agent=refresh_agent, app_name="dashboard_refresh"
                )
                await runner.session_service.create_session(
                    app_name="dashboard_refresh", user_id="dashboard", session_id=session_id
                )
                async for _ in runner.run_async(
                    user_id="dashboard",
                    session_id=session_id,
                    new_message=types.Content(
                        role="user", parts=[types.Part(text="Refresh market candidates.")]
                    ),
                ):
                    pass
                session = await runner.session_service.get_session(
                    app_name="dashboard_refresh", user_id="dashboard", session_id=session_id
                )
                metadata = (
                    json.loads(session.state[NEWS_METADATA_KEY]) if session else {}
                )
                status = FreshnessStatus(metadata.get("news_status", "cached"))
            self._last_refresh_news_status = status
            self._refresh = RefreshView(
                refresh_id=refresh_id,
                phase=RefreshPhase.COMPLETE,
                started_at=self._refresh.started_at,
                completed_at=datetime.now(timezone.utc),
                message=(
                    "A newer market update is ready."
                    if status == FreshnessStatus.LIVE
                    else "Refresh paused; the latest update remains available."
                    if status == FreshnessStatus.STALE
                    else "Market intelligence is up to date."
                ),
            )
        except Exception:
            self._last_refresh_news_status = FreshnessStatus.STALE
            news_candidate_cache.finish_failed_refresh()
            self._refresh = RefreshView(
                refresh_id=refresh_id,
                phase=RefreshPhase.FAILED,
                started_at=self._refresh.started_at,
                completed_at=datetime.now(timezone.utc),
                message="Refresh paused; the latest update remains available.",
            )
        finally:
            if runner is not None:
                await runner.close()


dashboard_service = DashboardService()
