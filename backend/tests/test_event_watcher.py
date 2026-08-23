from datetime import date

import pytest

from wealth_copilot.agents.event_watcher import run_event_watcher
from wealth_copilot.events import (
    EVENT_FIXTURES,
    DailyEventStore,
    EventDecision,
    EventDecisionEngine,
    FixtureEventInvestigator,
    get_event_fixture,
)
from wealth_copilot.events.schemas import InvestigationStatus, MarketEvent
from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider
from wealth_copilot.simulation import simulation_service


async def _portfolio():
    simulation_service.advance_to("12:17")
    return await DemoPortfolioProvider().get_summary()


def test_ten_provider_neutral_event_fixtures_validate() -> None:
    assert len(EVENT_FIXTURES) == 10
    assert all(isinstance(event, MarketEvent) for event in EVENT_FIXTURES)
    assert len({event.event_id for event in EVENT_FIXTURES}) == 10


async def test_hdfc_hero_event_is_a_complete_internal_alert() -> None:
    store = DailyEventStore()
    portfolio = await _portfolio()
    assessment = await EventDecisionEngine(store=store).assess(
        get_event_fixture("hdfc-bank-sudden-fall"), portfolio
    )
    hdfc = next(item for item in portfolio.holdings if item.symbol == "HDFCBANK")
    financials = next(
        item for item in portfolio.sector_exposure
        if item.sector == "Financial Services"
    )

    assert assessment.decision == EventDecision.ALERT
    assert assessment.notification_required is True
    assert assessment.affected_holdings == ["HDFCBANK"]
    assert assessment.affected_portfolio_percentage == pytest.approx(
        float(hdfc.portfolio_weight), abs=0.01
    )
    assert assessment.sector_exposure_percentage == pytest.approx(
        float(financials.portfolio_weight), abs=0.01
    )
    assert assessment.sector_relative_move_pct == 4.6
    assert assessment.relevance_score >= 80
    assert assessment.investigation_status == InvestigationStatus.COMPLETE
    assert len(assessment.developments) == 2
    assert [step.stage for step in assessment.trace] == [
        "EVENT_DETECTED",
        "PORTFOLIO_CHECK",
        "MARKET_INVESTIGATION",
        "RELEVANCE",
        "DECISION",
    ]
    assert assessment.actions == ["explain", "investigate", "save_for_evening"]


async def test_sector_aligned_noise_is_ignored_but_specific_move_alerts() -> None:
    engine = EventDecisionEngine(store=DailyEventStore())
    portfolio = await _portfolio()
    aligned = await engine.assess(get_event_fixture("tcs-sector-aligned-move"), portfolio)
    specific = await engine.assess(get_event_fixture("hdfc-bank-sudden-fall"), portfolio)

    assert aligned.decision == EventDecision.IGNORE
    assert aligned.trigger_detected is False
    assert aligned.sector_relative_move_pct == pytest.approx(0.1)
    assert specific.decision == EventDecision.ALERT
    assert specific.sector_relative_move_pct == 4.6


async def test_decision_fixture_set_covers_all_four_outcomes() -> None:
    engine = EventDecisionEngine(store=DailyEventStore())
    portfolio = await _portfolio()
    decisions = {
        (await engine.assess(event, portfolio)).decision for event in EVENT_FIXTURES
    }
    assert decisions == set(EventDecision)


async def test_market_investigation_failure_keeps_deterministic_decision() -> None:
    event_id = "hdfc-bank-sudden-fall"
    engine = EventDecisionEngine(
        investigator=FixtureEventInvestigator(fail_event_ids={event_id}),
        store=DailyEventStore(),
    )
    assessment = await engine.assess(get_event_fixture(event_id), await _portfolio())

    assert assessment.investigation_status == InvestigationStatus.FAILED
    assert assessment.investigation_error == "RuntimeError"
    assert assessment.decision == EventDecision.ALERT
    assert assessment.notification_required is True


async def test_event_memory_is_reusable_and_records_later_action() -> None:
    store = DailyEventStore()
    event = get_event_fixture("hdfc-bank-sudden-fall")
    await EventDecisionEngine(store=store).assess(event, await _portfolio())

    assert store.record_user_action(event.event_id, "save_for_evening") is True
    day = store.get_day(date(2026, 8, 18))
    assert len(day.events) == 1
    assert day.events[0].user_action == "save_for_evening"
    assert day.events[0].assessment.decision == EventDecision.ALERT


async def test_taskmaster_event_tool_runs_offline_hero_flow() -> None:
    result = await run_event_watcher("hdfc-bank-sudden-fall")

    assert result["status"] == "ok"
    assert result["mode"] == "deterministic_fixture"
    assert result["data"]["decision"] == "ALERT"
    assert result["data"]["notification_required"] is True
