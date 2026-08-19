"""Cheap financial-day identity and cross-surface integrity checks."""

from datetime import date

from .active import ActiveFinancialDay, AttentionSummary
from .schemas import FinancialDayState, StepStatus


def active_financial_day(state: FinancialDayState) -> ActiveFinancialDay:
    current_checkpoint = state.presentation_active_checkpoint
    if current_checkpoint is None and state.active_step_id:
        current_checkpoint = next(
            (step.scheduled_time for step in state.timeline if step.step_id == state.active_step_id),
            None,
        )
    return ActiveFinancialDay(
        day_id=state.day_id,
        run_id=state.run_id,
        mode=state.run_mode,
        presentation_time=(
            f"{int(state.presentation_minute or 0) // 60:02d}:{int(state.presentation_minute or 0) % 60:02d}"
            if state.presentation_minute is not None
            else None
        ),
        current_checkpoint=current_checkpoint,
        started_at=state.started_at,
        status=state.status.value,
        attention_summary=state.attention_summary,
    )


def presentation_minute(state: FinancialDayState) -> int | None:
    return round(state.presentation_minute) if state.run_mode == "presentation" and state.presentation_minute is not None else None


def checkpoint_released(state: FinancialDayState, checkpoint: str) -> bool:
    current = presentation_minute(state)
    if current is None:
        return True
    hour, minute = (int(part) for part in checkpoint.split(":"))
    return current >= hour * 60 + minute


def build_attention_summary(state: FinancialDayState, story_ids: list[str], high_priority_count: int) -> AttentionSummary:
    active_events = [
        item for item in state.events_alerted
        if item.run_id == state.run_id and checkpoint_released(state, "12:17")
    ]
    return AttentionSummary(
        high_priority_count=high_priority_count,
        portfolio_relevant_story_count=len(story_ids),
        active_event_count=len(active_events),
        story_ids=story_ids,
        event_ids=[item.event.event_id for item in active_events],
    )


def validate_financial_day_consistency(state: FinancialDayState) -> list[str]:
    errors: list[str] = []
    current_run = state.run_id
    for label, artifacts in (
        ("events", [*state.events_detected, *state.events_alerted, *state.events_ignored]),
        ("advisor requests", state.advisor_requests),
        ("advisor responses", state.advisor_responses),
    ):
        for artifact in artifacts:
            if getattr(artifact, "run_id", current_run) not in {None, current_run}:
                errors.append(f"{label} contains run {artifact.run_id}, active run is {current_run}")
            provenance = getattr(artifact, "provenance", None)
            if provenance and (
                provenance.day_id != state.day_id
                or provenance.run_id != current_run
            ):
                errors.append(f"{label} provenance does not match active day/run")
    for label, provenance in (
        ("morning pulse", state.morning_pulse_provenance),
        ("market close", state.market_close_review.provenance if state.market_close_review else None),
        ("daily story", state.daily_story.provenance if state.daily_story else None),
    ):
        if provenance and (
            provenance.day_id != state.day_id
            or provenance.run_id != current_run
        ):
            errors.append(f"{label} provenance does not match active day/run")
    if state.market_close_review and state.timeline:
        close = next((step for step in state.timeline if step.step_id == "close"), None)
        if close and close.status == StepStatus.PENDING:
            errors.append("market close review exists before the close checkpoint")
    if state.daily_story and not checkpoint_released(state, "21:01"):
        errors.append("daily story exists before the story checkpoint")
    if not checkpoint_released(state, "12:17") and state.events_alerted:
        errors.append("alerted event exists before the event checkpoint")
    if state.attention_summary.active_event_count != len(state.attention_summary.event_ids):
        errors.append("attention summary event count does not match event IDs")
    return errors


def assert_financial_day_consistent(state: FinancialDayState) -> None:
    errors = validate_financial_day_consistency(state)
    if errors:
        raise ValueError("; ".join(errors))
