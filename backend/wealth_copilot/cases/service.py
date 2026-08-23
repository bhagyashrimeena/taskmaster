"""Deterministic creation and transition policy for financial cases."""

from datetime import datetime, timezone

from ..events.schemas import EventAssessment, EventDecision, EventSeverity
from .schemas import (
    FinancialCase,
    FinancialCasePriority,
    FinancialCaseStatus,
    PortfolioExposure,
)


_ALLOWED_TRANSITIONS: dict[FinancialCaseStatus, set[FinancialCaseStatus]] = {
    FinancialCaseStatus.DETECTED: {
        FinancialCaseStatus.INVESTIGATING,
        FinancialCaseStatus.MONITORING,
        FinancialCaseStatus.ALERTED,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.INVESTIGATING: {
        FinancialCaseStatus.MONITORING,
        FinancialCaseStatus.ALERTED,
        FinancialCaseStatus.CARRY_FORWARD,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.MONITORING: {
        FinancialCaseStatus.INVESTIGATING,
        FinancialCaseStatus.ALERTED,
        FinancialCaseStatus.CARRY_FORWARD,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.ALERTED: {
        FinancialCaseStatus.USER_ENGAGED,
        FinancialCaseStatus.ADVISOR_PENDING,
        FinancialCaseStatus.CARRY_FORWARD,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.USER_ENGAGED: {
        FinancialCaseStatus.ADVISOR_PENDING,
        FinancialCaseStatus.MONITORING,
        FinancialCaseStatus.CARRY_FORWARD,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.ADVISOR_PENDING: {
        FinancialCaseStatus.MONITORING,
        FinancialCaseStatus.CARRY_FORWARD,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.CARRY_FORWARD: {
        FinancialCaseStatus.INVESTIGATING,
        FinancialCaseStatus.MONITORING,
        FinancialCaseStatus.ALERTED,
        FinancialCaseStatus.CLOSED,
    },
    FinancialCaseStatus.CLOSED: set(),
}


class FinancialCaseService:
    @staticmethod
    def _status(assessment: EventAssessment) -> FinancialCaseStatus:
        return {
            EventDecision.MONITOR: FinancialCaseStatus.MONITORING,
            EventDecision.INVESTIGATE: FinancialCaseStatus.INVESTIGATING,
            EventDecision.ALERT: FinancialCaseStatus.ALERTED,
        }.get(assessment.decision, FinancialCaseStatus.DETECTED)

    @staticmethod
    def _priority(assessment: EventAssessment) -> FinancialCasePriority:
        if assessment.event.severity == EventSeverity.CRITICAL or assessment.relevance_score >= 90:
            return FinancialCasePriority.CRITICAL
        if assessment.event.severity == EventSeverity.HIGH or assessment.relevance_score >= 75:
            return FinancialCasePriority.HIGH
        if assessment.relevance_score < 40:
            return FinancialCasePriority.LOW
        return FinancialCasePriority.MEDIUM

    def from_assessment(
        self, assessment: EventAssessment, existing: FinancialCase | None = None
    ) -> FinancialCase | None:
        if assessment.decision == EventDecision.IGNORE:
            return existing
        now = datetime.now(timezone.utc)
        status = self._status(assessment)
        sources = list(
            dict.fromkeys(
                [
                    assessment.event.source_url,
                    *(item.source_url for item in assessment.developments),
                ]
            )
        )
        if existing:
            existing.updated_at = now
            existing.priority = self._priority(assessment)
            existing.portfolio_exposure = PortfolioExposure(
                direct_pct=assessment.affected_portfolio_percentage,
                sector_pct=assessment.sector_exposure_percentage,
                affected_holdings=assessment.affected_holdings,
            )
            existing.research = [item.model_copy(deep=True) for item in assessment.developments]
            existing.sources = sources
            if existing.status != status and status in _ALLOWED_TRANSITIONS[existing.status]:
                existing.status = status
            return existing
        return FinancialCase(
            case_id=f"case-{assessment.event.timestamp.date().isoformat()}-{assessment.event.event_id}",
            instrument=assessment.event.instrument,
            opened_at=assessment.event.timestamp,
            updated_at=now,
            status=status,
            priority=self._priority(assessment),
            trigger=assessment.event.model_copy(deep=True),
            portfolio_exposure=PortfolioExposure(
                direct_pct=assessment.affected_portfolio_percentage,
                sector_pct=assessment.sector_exposure_percentage,
                affected_holdings=assessment.affected_holdings,
            ),
            research=[item.model_copy(deep=True) for item in assessment.developments],
            sources=sources,
        )

    @staticmethod
    def transition(
        case: FinancialCase, status: FinancialCaseStatus
    ) -> FinancialCase:
        if status == case.status:
            return case
        if status not in _ALLOWED_TRANSITIONS[case.status]:
            raise ValueError(f"Invalid financial-case transition: {case.status} -> {status}")
        case.status = status
        case.updated_at = datetime.now(timezone.utc)
        if status == FinancialCaseStatus.CLOSED:
            case.closed_at = case.updated_at
        return case


financial_case_service = FinancialCaseService()
