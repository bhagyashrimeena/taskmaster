"""Phase 8.6 accelerated clock, idempotency, and API contract tests."""

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.day.orchestrator import DayOrchestrator
from wealth_copilot.day.presentation import (
    PresentationClockService,
    PresentationClockStatus,
)
from wealth_copilot.day.schemas import FinancialDayState, StepStatus
from wealth_copilot.day.store import FinancialDayStore
from wealth_copilot.day.integrity import checkpoint_released, validate_financial_day_consistency


def _stub_operation(
    orchestrator: DayOrchestrator, step_id: str, calls: list[str]
):
    async def run(*, trading_date: date):
        calls.append(step_id)

        def finish(state):
            step = next(item for item in state.timeline if item.step_id == step_id)
            step.status = StepStatus.COMPLETE
            step.started_at = datetime.now(timezone.utc)
            step.completed_at = datetime.now(timezone.utc)
            step.detail = f"{step.label} completed in the clock test."

        return orchestrator.store.update(finish, trading_date)

    return run


@pytest.mark.asyncio
async def test_clock_crosses_due_checkpoints_once_and_keeps_one_day_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = date(2026, 8, 18)
    orchestrator = DayOrchestrator(FinancialDayStore(tmp_path / "days"))
    calls: list[str] = []
    clock = PresentationClockService(orchestrator)
    for step_id, operation in clock.operations.items():
        monkeypatch.setattr(
            orchestrator, operation, _stub_operation(orchestrator, step_id, calls)
        )

    started = await clock.advance(317, selected)
    assert started.status == PresentationClockStatus.RUNNING
    assert clock._task is not None
    await clock._task

    state = clock.state(selected)
    day = orchestrator.store.get(selected)
    assert state.current_time == "12:17"
    assert state.status == PresentationClockStatus.PAUSED
    assert calls == ["morning", "health", "open", "watch", "sector", "event"]
    assert day.run_mode == "presentation"
    assert set(state.completed_checkpoint_ids) == {"morning", "health", "open", "watch", "sector", "event"}

    await clock.advance(1, selected)
    assert clock._task is not None
    await clock._task
    assert calls == ["morning", "health", "open", "watch", "sector", "event"]


@pytest.mark.asyncio
async def test_restart_is_the_only_backwards_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = date(2026, 8, 18)
    orchestrator = DayOrchestrator(FinancialDayStore(tmp_path / "days"))
    calls: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "run_morning_pulse",
        _stub_operation(orchestrator, "morning", calls),
    )
    clock = PresentationClockService(orchestrator)
    await clock.advance(1, selected)
    assert clock._task is not None
    await clock._task
    first_run = orchestrator.store.get(selected).run_id

    reset = await clock.restart(selected)
    second = orchestrator.store.get(selected)
    assert reset.current_time == "07:00"
    assert reset.status == PresentationClockStatus.PAUSED
    assert reset.completed_checkpoint_ids == []
    assert second.run_id != first_run
    assert all(step.status == StepStatus.PENDING for step in second.timeline)


@pytest.mark.asyncio
async def test_clock_reconstructs_persisted_position_after_service_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = date(2026, 8, 18)
    orchestrator = DayOrchestrator(FinancialDayStore(tmp_path / "days"))
    monkeypatch.setattr(
        orchestrator,
        "run_morning_pulse",
        _stub_operation(orchestrator, "morning", []),
    )
    monkeypatch.setattr(
        orchestrator,
        "run_portfolio_health",
        _stub_operation(orchestrator, "health", []),
    )
    first_clock = PresentationClockService(orchestrator)
    await first_clock.advance(60, selected)
    assert first_clock._task is not None
    await first_clock._task

    restarted_clock = PresentationClockService(orchestrator)
    state = restarted_clock.state(selected)

    assert state.current_time == "08:00"
    assert state.status == PresentationClockStatus.PAUSED
    assert state.completed_checkpoint_ids == ["morning", "health"]


def test_presentation_clock_api_is_separate_from_normal_day_api() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/presentation-clock")
        assert response.status_code == 200
        assert response.json()["current_time"] == "07:00"
        assert response.json()["speed"] == 600

        paused = client.post("/api/v1/presentation-clock/pause")
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

        canonical = client.get("/api/v1/day/clock")
        assert canonical.status_code == 200
        assert canonical.json() == paused.json()


@pytest.mark.asyncio
async def test_clock_completes_all_thirteen_checkpoints_in_scheduled_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = date(2026, 8, 18)
    orchestrator = DayOrchestrator(FinancialDayStore(tmp_path / "days"))
    calls: list[str] = []
    clock = PresentationClockService(orchestrator)
    await orchestrator.initialize_presentation_day(selected)
    for step_id, operation in clock.operations.items():
        monkeypatch.setattr(
            orchestrator, operation, _stub_operation(orchestrator, step_id, calls)
        )

    await clock.advance(841, selected)
    assert clock._task is not None
    await clock._task

    assert calls == [
        "morning", "health", "open", "watch", "sector", "event", "learning",
        "close", "intelligence", "actions", "evening", "tomorrow", "story",
    ]
    assert clock.state(selected).status == PresentationClockStatus.COMPLETE
    assert len(clock.state(selected).completed_checkpoint_ids) == 13


@pytest.mark.parametrize(
    ("minute", "event", "close", "evening", "tomorrow", "story"),
    [
        (420, False, False, False, False, False),
        (421, False, False, False, False, False),
        (480, False, False, False, False, False),
        (736, False, False, False, False, False),
        (737, True, False, False, False, False),
        (930, True, True, False, False, False),
        (1200, True, True, True, False, False),
        (1260, True, True, True, True, False),
        (1261, True, True, True, True, True),
    ],
)
def test_presentation_checkpoint_release_matrix(
    minute: int,
    event: bool,
    close: bool,
    evening: bool,
    tomorrow: bool,
    story: bool,
) -> None:
    state = FinancialDayState(trading_date=date(2026, 8, 18), run_mode="presentation")
    state.presentation_minute = minute
    assert checkpoint_released(state, "12:17") is event
    assert checkpoint_released(state, "15:30") is close
    assert checkpoint_released(state, "20:00") is evening
    assert checkpoint_released(state, "21:00") is tomorrow
    assert checkpoint_released(state, "21:01") is story
    assert validate_financial_day_consistency(state) == []
