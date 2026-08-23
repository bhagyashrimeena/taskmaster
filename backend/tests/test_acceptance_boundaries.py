"""Acceptance-level boundary checks for deterministic event triage."""

import pytest

from wealth_copilot.events.engine import EventDecisionEngine
from wealth_copilot.events.schemas import (
    EventDecision,
    EventSeverity,
    MarketEvent,
    MarketEventType,
)


def _event(
    *,
    move: float,
    sector_move: float = 0.0,
    event_type: MarketEventType = MarketEventType.PRICE_MOVE,
    volume_change_pct: float | None = None,
) -> MarketEvent:
    return MarketEvent(
        event_id="boundary-event",
        event_type=event_type,
        symbol="HDFCBANK",
        company="HDFC Bank",
        sector="Financial Services",
        price_change_pct=move,
        sector_change_pct=sector_move,
        volume_change_pct=volume_change_pct,
        headline="Boundary event for deterministic acceptance testing",
        source="Acceptance fixture",
        source_url="https://events.example/boundary-event",
        severity=EventSeverity.MEDIUM,
    )


@pytest.mark.parametrize(
    ("move", "expected"),
    [
        (2.999, False),
        (3.0, True),
        (3.001, True),
    ],
)
def test_direct_holding_move_trigger_boundary(move: float, expected: bool) -> None:
    signals = EventDecisionEngine._signals(
        _event(move=move), direct_holding=True, direct=17.21, sector=27.26
    )

    signal = next(item for item in signals if item.rule == "holding_move_3pct")
    assert signal.triggered is expected


@pytest.mark.parametrize(
    ("volume", "expected"),
    [
        (99.999, False),
        (100.0, True),
        (100.001, True),
    ],
)
def test_volume_spike_trigger_boundary(volume: float, expected: bool) -> None:
    signals = EventDecisionEngine._signals(
        _event(move=0.0, volume_change_pct=volume),
        direct_holding=True,
        direct=17.21,
        sector=27.26,
    )

    signal = next(item for item in signals if item.rule == "volume_spike")
    assert signal.triggered is expected


@pytest.mark.parametrize(
    ("move", "divergence", "relevance", "expected"),
    [
        (5.0, 2.0, 79.999, EventDecision.INVESTIGATE),
        (4.999, 2.0, 80.0, EventDecision.INVESTIGATE),
        (5.0, 1.999, 80.0, EventDecision.MONITOR),
        (5.0, 2.0, 80.0, EventDecision.ALERT),
        (5.001, 2.001, 80.001, EventDecision.ALERT),
    ],
)
def test_alert_decision_boundaries(
    move: float,
    divergence: float,
    relevance: float,
    expected: EventDecision,
) -> None:
    result = EventDecisionEngine._decision(
        _event(move=move),
        triggered=True,
        direct_holding=True,
        direct=17.21,
        sector=27.26,
        divergence=divergence,
        relevance_score=relevance,
    )

    assert result is expected


@pytest.mark.parametrize(
    ("sector_exposure", "expected_trigger", "expected_decision"),
    [
        (14.999, False, EventDecision.IGNORE),
        (15.0, True, EventDecision.MONITOR),
        (15.001, True, EventDecision.MONITOR),
    ],
)
def test_macro_sector_exposure_boundary(
    sector_exposure: float,
    expected_trigger: bool,
    expected_decision: EventDecision,
) -> None:
    event = _event(move=0.0, event_type=MarketEventType.MACRO)
    signals = EventDecisionEngine._signals(
        event,
        direct_holding=False,
        direct=0.0,
        sector=sector_exposure,
    )
    triggered = next(
        item for item in signals if item.rule == "macro_sector_exposure"
    ).triggered

    decision = EventDecisionEngine._decision(
        event,
        triggered=triggered,
        direct_holding=False,
        direct=0.0,
        sector=sector_exposure,
        divergence=0.0,
        relevance_score=20.0,
    )

    assert triggered is expected_trigger
    assert decision is expected_decision
