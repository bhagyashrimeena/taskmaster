"""Deterministic trigger, investigation, relevance, and decision workflow."""

from datetime import datetime, timezone
from typing import Protocol

from ..market.schemas import EventType, NewsCandidate
from ..portfolio.schemas import PortfolioSummary
from ..relevance.engine import RelevanceEngine, _company_matches, _sector_token
from ..day.active import ArtifactProvenance
from .fixtures import DEVELOPMENT_FIXTURES
from .memory import DailyEventStore, daily_event_store
from .schemas import (
    EventAssessment,
    EventDecision,
    EventSeverity,
    EventTraceStep,
    InvestigationStatus,
    MarketEvent,
    MarketEventType,
    TriggerSignal,
)


class EventInvestigator(Protocol):
    async def investigate(self, event: MarketEvent) -> list[NewsCandidate]: ...


class FixtureEventInvestigator:
    """Offline investigation provider used by the deterministic demo."""

    def __init__(self, *, fail_event_ids: set[str] | None = None) -> None:
        self._fail_event_ids = fail_event_ids or set()

    async def investigate(self, event: MarketEvent) -> list[NewsCandidate]:
        if event.event_id in self._fail_event_ids:
            raise RuntimeError("simulated market investigation failure")
        return [
            item.model_copy(deep=True)
            for item in DEVELOPMENT_FIXTURES.get(event.event_id, [])
        ]


_NEWS_EVENT_TYPE = {
    MarketEventType.PRICE_MOVE: EventType.MARKET_MOVE,
    MarketEventType.VOLUME_SPIKE: EventType.MARKET_MOVE,
    MarketEventType.EARNINGS: EventType.EARNINGS,
    MarketEventType.CORPORATE_ANNOUNCEMENT: EventType.CORPORATE_ACTION,
    MarketEventType.REGULATORY: EventType.REGULATORY,
    MarketEventType.MACRO: EventType.MACRO,
    MarketEventType.NEWS: EventType.OTHER,
}


def _event_candidate(event: MarketEvent) -> NewsCandidate:
    company_tags = [value for value in (event.symbol, event.company) if value]
    return NewsCandidate(
        id=event.event_id,
        headline=event.headline,
        summary=(
            f"Observed {event.event_type.value} for {event.company or event.sector or 'the market'}; "
            f"price change {event.price_change_pct if event.price_change_pct is not None else 'n/a'}%."
        ),
        source_name=event.source,
        source_url=event.source_url,
        published_at=event.timestamp,
        companies=company_tags,
        sectors=[event.sector] if event.sector else [],
        event_type=_NEWS_EVENT_TYPE[event.event_type],
        market_move_pct=event.price_change_pct,
    )


class EventDecisionEngine:
    """Evaluates an event without using an LLM for triggers or decisions."""

    def __init__(
        self,
        *,
        investigator: EventInvestigator | None = None,
        store: DailyEventStore | None = None,
    ) -> None:
        self.investigator = investigator or FixtureEventInvestigator()
        self.store = store or daily_event_store
        self.relevance = RelevanceEngine()

    @staticmethod
    def _holding_and_exposure(event: MarketEvent, portfolio: PortfolioSummary):
        affected = [
            holding
            for holding in portfolio.holdings
            if event.symbol and _company_matches(holding.symbol, event.symbol)
        ]
        affected_value = sum((item.market_value for item in affected), start=0)
        direct = (
            round(float(affected_value / portfolio.portfolio_value * 100), 1)
            if portfolio.portfolio_value
            else 0.0
        )
        sector_key = _sector_token(event.sector or "")
        sector = round(
            sum(
                float(item.portfolio_weight)
                for item in portfolio.sector_exposure
                if sector_key and _sector_token(item.sector) == sector_key
            ),
            2,
        )
        return affected, direct, sector

    @staticmethod
    def _signals(
        event: MarketEvent, *, direct_holding: bool, direct: float, sector: float
    ) -> list[TriggerSignal]:
        move = abs(event.price_change_pct or 0.0)
        divergence = abs((event.price_change_pct or 0.0) - (event.sector_change_pct or 0.0))
        major_type = event.event_type in {
            MarketEventType.EARNINGS,
            MarketEventType.CORPORATE_ANNOUNCEMENT,
            MarketEventType.REGULATORY,
        }
        return [
            TriggerSignal(rule="holding_move_3pct", triggered=direct_holding and move >= 3.0, observed=move, threshold=3.0, reason="Direct holding moved at least 3%."),
            TriggerSignal(rule="holding_move_5pct", triggered=direct_holding and move >= 5.0, observed=move, threshold=5.0, reason="Direct holding moved at least 5%."),
            TriggerSignal(rule="sector_relative_move", triggered=direct_holding and divergence >= 2.0, observed=round(divergence, 2), threshold=2.0, reason="Holding materially outperformed or underperformed its sector."),
            TriggerSignal(rule="volume_spike", triggered=direct_holding and (event.volume_change_pct or 0.0) >= 100.0, observed=event.volume_change_pct, threshold=100.0, reason="Trading volume is at least 100% above its baseline."),
            TriggerSignal(rule="major_direct_news", triggered=direct_holding and (major_type or event.has_material_news), observed=event.event_type.value, threshold="material direct event", reason="A material development directly references a holding."),
            TriggerSignal(rule="macro_sector_exposure", triggered=event.event_type == MarketEventType.MACRO and sector >= 15.0, observed=sector, threshold=15.0, reason="A macro event affects a sector with significant portfolio exposure."),
        ]

    @staticmethod
    def _decision(
        event: MarketEvent,
        *,
        triggered: bool,
        direct_holding: bool,
        direct: float,
        sector: float,
        divergence: float | None,
        relevance_score: float,
    ) -> EventDecision:
        if not triggered:
            return EventDecision.IGNORE
        move = abs(event.price_change_pct or 0.0)
        company_specific = divergence is not None and divergence >= 2.0
        if (
            direct_holding
            and relevance_score >= 80
            and (
                (move >= 5.0 and company_specific)
                or event.severity == EventSeverity.CRITICAL
                or (event.has_material_news and move >= 4.0)
            )
        ):
            return EventDecision.ALERT
        if direct_holding and (
            company_specific
            or event.has_material_news
            or event.event_type == MarketEventType.VOLUME_SPIKE
        ):
            return EventDecision.INVESTIGATE
        if sector >= 15.0 or direct > 0:
            return EventDecision.MONITOR
        return EventDecision.IGNORE

    async def assess(
        self,
        event: MarketEvent,
        portfolio: PortfolioSummary,
        *,
        day_id: str | None = None,
        run_id: str | None = None,
    ) -> EventAssessment:
        affected, direct, sector = self._holding_and_exposure(event, portfolio)
        signals = self._signals(
            event, direct_holding=bool(affected), direct=direct, sector=sector
        )
        triggered = any(signal.triggered for signal in signals)
        divergence = (
            round(abs(event.price_change_pct - event.sector_change_pct), 2)
            if event.price_change_pct is not None and event.sector_change_pct is not None
            else None
        )
        scored = self.relevance.score_candidate(
            _event_candidate(event), portfolio, now=event.timestamp.astimezone(timezone.utc)
        )
        relevance_score = scored.relevance_score
        relevance_signals = scored.signals.model_dump()

        developments: list[NewsCandidate] = []
        investigation_status = InvestigationStatus.SKIPPED
        investigation_error = None
        if triggered:
            try:
                developments = await self.investigator.investigate(event)
                investigation_status = InvestigationStatus.COMPLETE
            except Exception as exc:
                investigation_status = InvestigationStatus.FAILED
                investigation_error = type(exc).__name__

        decision = self._decision(
            event,
            triggered=triggered,
            direct_holding=bool(affected),
            direct=direct,
            sector=sector,
            divergence=divergence,
            relevance_score=relevance_score,
        )
        notification_required = decision == EventDecision.ALERT
        if decision == EventDecision.ALERT:
            title = f"Unusual move in {event.company or event.symbol}"
            reason = (
                f"{event.company or event.symbol} moved {event.price_change_pct:.1f}% versus "
                f"{event.sector_change_pct:.1f}% for its sector; {direct:.1f}% of the portfolio is directly exposed "
                f"and total financial-sector exposure is {sector:.1f}%."
            )
            actions = ["explain", "investigate", "save_for_evening"]
        elif decision == EventDecision.IGNORE:
            title = f"No action needed for {event.company or event.sector or 'market event'}"
            reason = "The event did not cross a portfolio-aware investigation threshold."
            actions = []
        else:
            title = f"{decision.value.title()}: {event.company or event.sector or 'market event'}"
            reason = (
                f"The event crossed a deterministic trigger and affects {direct or sector:.2f}% "
                "of the portfolio."
            )
            actions = ["explain", "save_for_evening"]

        trace = [
            EventTraceStep(stage="EVENT_DETECTED", outcome="triggered" if triggered else "below_threshold", details={"event_id": event.event_id, "type": event.event_type.value}),
            EventTraceStep(stage="PORTFOLIO_CHECK", outcome="direct" if affected else ("sector" if sector else "unrelated"), details={"affected_holdings": [item.symbol for item in affected], "direct_exposure_pct": direct, "sector_exposure_pct": sector}),
            EventTraceStep(stage="MARKET_INVESTIGATION", outcome=investigation_status.value, details={"developments_found": len(developments), "error": investigation_error}),
            EventTraceStep(stage="RELEVANCE", outcome=f"{relevance_score:.2f}/100", details={"signals": relevance_signals}),
            EventTraceStep(stage="DECISION", outcome=decision.value, details={"notification_required": notification_required}),
        ]
        assessment = EventAssessment(
            day_id=day_id,
            run_id=run_id,
            event=event,
            portfolio_source=portfolio.source,
            direct_holding=bool(affected),
            affected_holdings=[item.symbol for item in affected],
            affected_portfolio_percentage=direct,
            sector_exposure_percentage=sector,
            sector_relative_move_pct=divergence,
            trigger_detected=triggered,
            trigger_signals=signals,
            investigation_status=investigation_status,
            investigation_error=investigation_error,
            developments=developments,
            relevance_score=relevance_score,
            decision=decision,
            notification_required=notification_required,
            title=title,
            reason=reason,
            actions=actions,
            trace=trace,
            evaluated_at=event.timestamp,
            provenance=(
                ArtifactProvenance(
                    day_id=day_id,
                    run_id=run_id,
                    source_checkpoint="12:17",
                    source_snapshot_id=event.event_id,
                    generated_at=datetime.now(timezone.utc),
                )
                if day_id and run_id
                else None
            ),
        )
        self.store.save(assessment)
        return assessment
