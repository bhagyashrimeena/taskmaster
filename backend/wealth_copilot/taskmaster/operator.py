"""Deterministic policy that turns verified evidence into an attention action."""

from datetime import timedelta

from ..cases.schemas import FinancialCase
from ..events.schemas import EventAssessment, EventDecision, InvestigationStatus
from .schemas import OperatorCycle, TaskmasterDecision


class TaskmasterOperator:
    def operate_event(
        self, assessment: EventAssessment, case: FinancialCase | None
    ) -> OperatorCycle:
        if assessment.decision == EventDecision.ALERT:
            decision = TaskmasterDecision.INTERRUPT_NOW
            reason = "A verified portfolio-aware alert crossed the interruption threshold."
            follow_up = assessment.evaluated_at + timedelta(minutes=30)
        elif assessment.decision == EventDecision.INVESTIGATE:
            decision = TaskmasterDecision.RESEARCH_FIRST
            reason = "The signal is material enough to investigate before interrupting the user."
            follow_up = assessment.evaluated_at + timedelta(minutes=20)
        elif assessment.decision == EventDecision.MONITOR:
            decision = TaskmasterDecision.MONITOR
            reason = "The signal is relevant but remains below the interruption threshold."
            follow_up = assessment.evaluated_at + timedelta(minutes=30)
        else:
            decision = TaskmasterDecision.CLOSE_CASE
            reason = "The signal did not cross a portfolio-aware attention threshold."
            follow_up = None
        return OperatorCycle(
            cycle_id=f"cycle-{assessment.event.event_id}-{int(assessment.evaluated_at.timestamp())}",
            subject_id=case.case_id if case else assessment.event.event_id,
            observed_at=assessment.evaluated_at,
            observations=[
                f"Decision engine: {assessment.decision.value}",
                f"Direct exposure: {assessment.affected_portfolio_percentage:.2f}%",
                f"Sector exposure: {assessment.sector_exposure_percentage:.2f}%",
                f"Relevance: {assessment.relevance_score:.2f}/100",
            ],
            plan=["Retain the event", "Verify evidence", "Apply attention policy"],
            delegated_to=(
                ["research_agent"]
                if assessment.investigation_status != InvestigationStatus.SKIPPED
                else []
            ),
            verification=[
                f"{len(assessment.developments)} source-backed development(s)",
                f"{len(assessment.trigger_signals)} deterministic trigger checks",
            ],
            decision=decision,
            reason=reason,
            follow_up_at=follow_up,
        )


taskmaster_operator = TaskmasterOperator()
