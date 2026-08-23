"""Phase 6 financial-day continuity, attribution, scheduling, and API tests."""

import asyncio
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.config import application_today
from wealth_copilot.day.orchestrator import DayOrchestrator
from wealth_copilot.day.scheduler import DayScheduler
from wealth_copilot.day.schemas import (
    DayRunMode,
    DayStatus,
    FinancialDayState,
    QuestionAsked,
    StepStatus,
)
from wealth_copilot.day.store import FinancialDayStore
from wealth_copilot.media.service import media_service


@pytest.fixture
def store(tmp_path: Path) -> FinancialDayStore:
    return FinancialDayStore(tmp_path / "days")


def test_day_store_survives_restart_and_preserves_corrupt_input(store: FinancialDayStore) -> None:
    selected = date(2026, 8, 18)
    state = FinancialDayState(trading_date=selected, status=DayStatus.RUNNING)
    state.saved_stories.append("rbi-liquidity")
    store.save(state)

    restarted = FinancialDayStore(store.root)
    assert restarted.get(selected).saved_stories == ["rbi-liquidity"]

    path = store.root / "2026-08-18.json"
    path.write_text("{not-json", encoding="utf-8")
    recovered = restarted.get(selected)
    assert recovered.status == DayStatus.NOT_STARTED
    assert "could not be read" in (recovered.last_error or "")
    assert path.read_text(encoding="utf-8") == "{not-json"


@pytest.mark.asyncio
async def test_demo_day_completes_with_attribution_and_continuity(
    store: FinancialDayStore,
) -> None:
    orchestrator = DayOrchestrator(store)
    state = await orchestrator.run_demo_day(date(2026, 8, 18), duration_seconds=0)

    assert state.status == DayStatus.COMPLETE
    assert all(step.status == StepStatus.COMPLETE for step in state.timeline)
    assert state.morning_brief_id
    assert state.evening_brief_id
    assert state.portfolio_open_snapshot
    assert state.portfolio_close_snapshot
    assert state.portfolio_close_snapshot.source == "simulated"
    assert state.events_alerted[0].event.event_id == "hdfc-bank-sudden-fall"
    assert state.market_close_review
    hdfc = next(
        item
        for item in state.market_close_review.top_negative_contributors
        if item.symbol == "HDFCBANK"
    )
    assert hdfc.daily_return_pct == -5.4
    assert hdfc.contribution_percentage_points == round(
        hdfc.portfolio_weight_pct * hdfc.daily_return_pct / 100,
        2,
    )
    assert "hdfc-bank-sudden-fall" in state.market_close_review.alert_event_ids
    assert [item.relevance_rank for item in state.tomorrow_events] == [1, 2]
    assert state.tomorrow_events[0].portfolio_exposure_pct >= state.tomorrow_events[1].portfolio_exposure_pct
    assert state.daily_story is not None
    assert state.timeline[-1].step_id == "story"
    assert state.timeline[-1].status == StepStatus.COMPLETE


@pytest.mark.asyncio
async def test_evening_wrap_uses_saves_questions_close_and_unresolved_state(
    store: FinancialDayStore,
) -> None:
    selected = date(2026, 8, 18)
    orchestrator = DayOrchestrator(store)
    store.update(lambda state: setattr(state, "run_mode", DayRunMode.DEMO), selected)
    await orchestrator.run_morning_pulse(selected)
    await orchestrator.handle_market_event(trading_date=selected)
    await orchestrator.run_market_close(selected)

    def interact(state: FinancialDayState) -> None:
        state.saved_stories.append(state.top_stories[0])
        state.saved_events.append("hdfc-bank-sudden-fall")
        state.questions_asked.append(
            QuestionAsked(question="Why did HDFC Bank diverge from its sector?")
        )

    store.update(interact, selected)
    state = await orchestrator.run_evening_wrap(selected)
    brief = media_service.get(state.evening_brief_id or "")

    assert brief is not None
    assert "market close" in brief.script.lower()
    assert "asked 1 question" in brief.script.lower()
    assert "buy" not in brief.script.lower()
    assert state.unresolved_items


@pytest.mark.asyncio
async def test_scheduler_runs_due_operations_once() -> None:
    calls: list[str] = []

    class FakeOrchestrator:
        async def run_morning_pulse(self, **_): calls.append("morning")
        async def run_portfolio_health(self, **_): calls.append("health")
        async def run_market_close(self, **_): calls.append("close")
        async def run_evening_wrap(self, **_): calls.append("evening")
        async def prepare_tomorrow(self, **_): calls.append("tomorrow")
        async def generate_daily_story(self, **_): calls.append("story")

    scheduler = DayScheduler(FakeOrchestrator())
    now = datetime(2026, 8, 18, 21, 1, tzinfo=ZoneInfo("Asia/Kolkata"))
    first = await scheduler.run_due(now)
    second = await scheduler.run_due(now)

    assert first == [
        "run_morning_pulse",
        "run_portfolio_health",
        "run_market_close",
        "run_evening_wrap",
        "prepare_tomorrow",
        "generate_daily_story",
    ]
    assert calls == ["morning", "health", "close", "evening", "tomorrow", "story"]
    assert second == []


@pytest.mark.asyncio
async def test_scheduler_retries_failed_checkpoint_without_dying() -> None:
    calls: list[str] = []

    class FlakyOrchestrator:
        def __init__(self) -> None:
            self.failed = False

        async def run_morning_pulse(self, **_):
            calls.append("morning")
            if not self.failed:
                self.failed = True
                raise RuntimeError("temporary failure")

        async def run_portfolio_health(self, **_):
            calls.append("health")

        async def run_market_close(self, **_):
            calls.append("close")

        async def run_evening_wrap(self, **_):
            calls.append("evening")

        async def prepare_tomorrow(self, **_):
            calls.append("tomorrow")

        async def generate_daily_story(self, **_):
            calls.append("story")

    scheduler = DayScheduler(FlakyOrchestrator())
    now = datetime(2026, 8, 18, 7, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    assert await scheduler.run_due(now) == []
    assert await scheduler.run_due(now) == ["run_morning_pulse"]
    assert calls == ["morning", "morning"]


@pytest.mark.asyncio
async def test_scheduler_recovers_completed_checkpoint_from_day_store(
    store: FinancialDayStore,
) -> None:
    selected = date(2026, 8, 18)

    def mark_morning_complete(state: FinancialDayState) -> None:
        morning = next(step for step in state.timeline if step.step_id == "morning")
        morning.status = StepStatus.COMPLETE

    store.update(mark_morning_complete, selected)

    class RestartedOrchestrator:
        def __init__(self) -> None:
            self.store = store
            self.calls = 0

        async def run_morning_pulse(self, trading_date: date) -> None:
            self.calls += 1

    orchestrator = RestartedOrchestrator()
    scheduler = DayScheduler(orchestrator)
    now = datetime(2026, 8, 18, 7, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    assert await scheduler.run_due(now) == []
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_demo_step_timeout_becomes_retryable_failure(
    store: FinancialDayStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    orchestrator = DayOrchestrator(store, step_timeout_seconds=0.01)

    async def stuck_morning(*, trading_date):
        orchestrator._step_start(trading_date, "morning")
        await asyncio.Event().wait()

    monkeypatch.setattr(orchestrator, "run_morning_pulse", stuck_morning)
    with pytest.raises(TimeoutError):
        await orchestrator.run_demo_day(
            date(2026, 8, 18), duration_seconds=0
        )

    state = store.get(date(2026, 8, 18))
    assert state.status == DayStatus.FAILED
    assert state.timeline[0].status == StepStatus.FAILED
    assert "timed out" in state.timeline[0].detail.lower()
    assert state.active_step_id is None


@pytest.mark.asyncio
async def test_interrupted_demo_resumes_from_first_unfinished_step(
    store: FinancialDayStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = date(2026, 8, 18)
    interrupted = FinancialDayState(
        trading_date=selected,
        status=DayStatus.RUNNING,
        run_mode="demo",
        simulated_duration_seconds=0,
        active_step_id="health",
    )
    interrupted.timeline[0].status = StepStatus.COMPLETE
    interrupted.timeline[1].status = StepStatus.RUNNING
    interrupted.saved_stories = ["hdfc-rbi"]
    store.save(interrupted)
    orchestrator = DayOrchestrator(store, step_timeout_seconds=1)
    called: list[str] = []

    def operation(step_id: str):
        async def run(*, trading_date):
            called.append(step_id)
            orchestrator._step_start(trading_date, step_id)
            return orchestrator._step_complete(trading_date, step_id, "resumed")

        return run

    monkeypatch.setattr(orchestrator, "run_portfolio_health", operation("health"))
    monkeypatch.setattr(orchestrator, "handle_market_event", operation("event"))
    monkeypatch.setattr(orchestrator, "run_market_close", operation("close"))
    monkeypatch.setattr(orchestrator, "run_evening_wrap", operation("evening"))
    monkeypatch.setattr(orchestrator, "prepare_tomorrow", operation("tomorrow"))
    monkeypatch.setattr(orchestrator, "generate_daily_story", operation("story"))

    await orchestrator.recover_interrupted_demo(selected)
    assert orchestrator._task is not None
    await orchestrator._task
    state = store.get(selected)

    assert called == ["health", "event", "close", "evening", "tomorrow", "story"]
    assert state.status == DayStatus.COMPLETE
    assert state.saved_stories == ["hdfc-rbi"]
    assert all(step.status == StepStatus.COMPLETE for step in state.timeline)


def test_day_api_is_nonblocking(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = FinancialDayState(
        trading_date=application_today(), status=DayStatus.RUNNING, run_mode="demo"
    )

    async def fake_start():
        return expected

    async def fake_recover():
        return expected

    monkeypatch.setattr("wealth_copilot.api.day_orchestrator.start_demo_day", fake_start)
    monkeypatch.setattr(
        "wealth_copilot.api.day_orchestrator.recover_interrupted_demo", fake_recover
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/day/demo")
    assert response.status_code == 202
    assert response.json()["status"] == "running"
