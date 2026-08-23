from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from wealth_copilot.cases import FinancialCaseStatus, financial_case_service
from wealth_copilot.day.orchestrator import DayOrchestrator
from wealth_copilot.day.schemas import DayRunMode, DayStatus, FinancialDayState, StepStatus
from wealth_copilot.day.scheduler import DayScheduler
from wealth_copilot.day.store import FinancialDayStore
from wealth_copilot.events import EventDecisionEngine, get_event_fixture
from wealth_copilot.events.memory import DailyEventStore
from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider
from wealth_copilot.simulation import simulation_service
from wealth_copilot.taskmaster import TaskmasterDecision


@pytest.mark.asyncio
async def test_material_event_opens_case_and_records_operator_attention_once(
    tmp_path: Path,
) -> None:
    selected = date(2026, 8, 18)
    store = FinancialDayStore(tmp_path)
    assessment = await EventDecisionEngine(store=DailyEventStore()).assess(
        get_event_fixture("hdfc-bank-sudden-fall"),
        await DemoPortfolioProvider().get_summary(),
        day_id="financial-day-2026-08-18",
        run_id="run-test",
    )
    orchestrator = DayOrchestrator(store)

    first = orchestrator.record_event(assessment, selected)
    second = orchestrator.record_event(assessment, selected)

    assert len(first.financial_cases) == 1
    case = first.financial_cases[0]
    assert case.status == FinancialCaseStatus.ALERTED
    assert case.instrument == "NSE:HDFCBANK"
    assert case.case_id in first.open_case_ids
    assert first.operator_cycles[-1].decision == TaskmasterDecision.INTERRUPT_NOW
    assert first.attention_budget.signals_processed == 1
    assert first.attention_budget.interrupted == 1
    assert second.attention_budget.signals_processed == 1
    assert store.get(selected).financial_cases[0].case_id == case.case_id

    financial_case_service.transition(case, FinancialCaseStatus.CLOSED)
    assert case.closed_at is not None
    with pytest.raises(ValueError):
        financial_case_service.transition(case, FinancialCaseStatus.MONITORING)


def test_real_day_has_generic_timeline_and_never_advances_fixture_clock(
    tmp_path: Path,
) -> None:
    selected = date(2026, 8, 22)
    store = FinancialDayStore(tmp_path)
    orchestrator = DayOrchestrator(store)
    state = store.get(selected)
    event_step = next(item for item in state.timeline if item.step_id == "event")

    assert state.run_mode == DayRunMode.REAL
    assert event_step.label == "Event Investigations"
    assert all("HDFC" not in item.label for item in state.timeline)

    simulation_service.reset_scenario()
    orchestrator._advance_developer_clock(selected, "12:17")
    assert simulation_service.state().checkpoint == "07:00"
    store.update(lambda item: setattr(item, "run_mode", DayRunMode.DEMO), selected)
    orchestrator._advance_developer_clock(selected, "12:17")
    assert simulation_service.state().checkpoint == "12:17"


@pytest.mark.asyncio
async def test_scheduler_covers_full_day_and_recurring_market_watch() -> None:
    calls: list[str] = []

    class FullOrchestrator:
        async def run_morning_pulse(self, **_): calls.append("morning")
        async def run_portfolio_health(self, **_): calls.append("health")
        async def run_market_open_monitor(self, **_): calls.append("open")
        async def handle_market_event(self, **_): calls.append("event")
        async def run_adaptive_market_watch(self, **_): calls.append("watch")
        async def run_sector_deep_dive(self, **_): calls.append("sector")
        async def run_contextual_learning(self, **_): calls.append("learning")
        async def run_market_close(self, **_): calls.append("close")
        async def run_portfolio_intelligence(self, **_): calls.append("intelligence")
        async def run_action_queue(self, **_): calls.append("actions")
        async def run_evening_wrap(self, **_): calls.append("evening")
        async def prepare_tomorrow(self, **_): calls.append("tomorrow")
        async def generate_daily_story(self, **_): calls.append("story")

    scheduler = DayScheduler(FullOrchestrator())
    zone = ZoneInfo("Asia/Kolkata")
    assert await scheduler.run_due(datetime(2026, 8, 22, 9, 15, tzinfo=zone)) == [
        "run_morning_pulse",
        "run_portfolio_health",
        "run_market_open_monitor",
    ]
    assert await scheduler.run_due(datetime(2026, 8, 22, 10, 7, tzinfo=zone)) == [
        "handle_market_event",
        "run_adaptive_market_watch"
    ]
    assert await scheduler.run_due(datetime(2026, 8, 22, 10, 14, tzinfo=zone)) == []
    assert await scheduler.run_due(datetime(2026, 8, 22, 10, 15, tzinfo=zone)) == [
        "run_adaptive_market_watch"
    ]
    late = await scheduler.run_due(datetime(2026, 8, 22, 21, 1, tzinfo=zone))
    assert late == [
        "run_sector_deep_dive",
        "run_contextual_learning",
        "run_market_close",
        "run_portfolio_intelligence",
        "run_action_queue",
        "run_evening_wrap",
        "prepare_tomorrow",
        "generate_daily_story",
    ]
    assert calls.count("watch") == 2


@pytest.mark.asyncio
async def test_real_event_checkpoint_does_not_inject_the_demo_fixture(
    tmp_path: Path,
) -> None:
    selected = date(2026, 8, 22)
    store = FinancialDayStore(tmp_path)
    orchestrator = DayOrchestrator(store)

    state = await orchestrator.handle_market_event(trading_date=selected)
    event_step = next(item for item in state.timeline if item.step_id == "event")

    assert state.started_at is not None
    assert event_step.status.value == "complete"
    assert event_step.linked_ids == []
    assert state.events_detected == []
    assert "No market event crossed" in event_step.detail


@pytest.mark.asyncio
async def test_final_story_checkpoint_completes_the_real_financial_day(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = date(2026, 8, 22)
    store = FinancialDayStore(tmp_path)
    orchestrator = DayOrchestrator(store)

    def complete_prior_steps(state: FinancialDayState) -> None:
        for step in state.timeline:
            if step.step_id != "story":
                step.status = StepStatus.COMPLETE

    store.update(complete_prior_steps, selected)

    async def quiet_story(_service, _selected):
        return SimpleNamespace(
            scenes=[1, 2, 3],
            duration_seconds=24,
            story_id="quiet-story",
            audio_brief_id="quiet-audio",
        )

    monkeypatch.setattr(
        "wealth_copilot.day.orchestrator.DailyStoryService.prepare",
        quiet_story,
    )
    state = await orchestrator.generate_daily_story(selected)

    assert state.status == DayStatus.COMPLETE
    assert state.completed_at is not None
    assert state.timeline[-1].status == StepStatus.COMPLETE
