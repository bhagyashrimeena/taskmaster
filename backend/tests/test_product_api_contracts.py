from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.config import application_today
from wealth_copilot.day.orchestrator import day_orchestrator
from wealth_copilot.day.schemas import DayRunMode
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.product_api.schemas import (
    AlertCategory,
    ProductEventType,
    StreamSnapshot,
)
from wealth_copilot.product_api.service import product_api_service
from wealth_copilot.product_api.stream import events_since
from wealth_copilot.simulation import simulation_service


def test_focused_product_routes_have_stable_page_contracts() -> None:
    client = TestClient(app)

    today = client.get("/api/v1/today")
    portfolio = client.get("/api/v1/portfolio")
    alerts = client.get("/api/v1/alerts")
    timeline = client.get("/api/v1/timeline")
    copilot = client.get("/api/v1/copilot")

    assert today.status_code == 200
    assert set(today.json()) >= {
        "day_id", "run_id", "trading_date", "attention_items", "portfolio",
        "daily_brief", "recent_timeline", "next_checkpoint",
    }
    assert portfolio.status_code == 200
    assert portfolio.json()["portfolio"]["portfolio_value"] > 0
    assert alerts.status_code == 200
    assert set(alerts.json()["counts"]) == {item.value for item in AlertCategory}
    assert timeline.status_code == 200
    assert timeline.json()["total_count"] == 13
    assert copilot.status_code == 200
    assert len(copilot.json()["suggested_questions"]) == 4


def test_sse_route_returns_named_snapshot_event_without_buffering() -> None:
    response = TestClient(app).get("/api/v1/events/stream?once=true")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: SNAPSHOT" in response.text
    assert '"event_type":"SNAPSHOT"' in response.text


async def test_alert_inbox_and_detail_are_derived_from_a_financial_case() -> None:
    selected = application_today()
    financial_day_store.update(
        lambda state: setattr(state, "run_mode", DayRunMode.DEMO),
        selected,
    )
    simulation_service.advance_to("12:17")
    state = await day_orchestrator.handle_market_event(trading_date=selected)
    case_id = state.financial_cases[0].case_id

    inbox = await product_api_service.alerts(AlertCategory.ATTENTION)
    detail = await product_api_service.alert_detail(case_id)

    assert len(inbox.items) == 1
    assert inbox.items[0].case_id == case_id
    assert inbox.items[0].portfolio_impact_pct is not None
    assert detail.case.case_id == case_id
    assert detail.assessment is not None
    assert detail.intraday
    assert detail.benchmark is not None


def test_stream_diff_emits_typed_checkpoint_case_alert_and_audio_events() -> None:
    now = datetime.now(timezone.utc)
    previous = StreamSnapshot(
        day_id="day",
        run_id="run",
        status="running",
        completed_steps=[],
        case_versions={},
        alert_event_ids=[],
        ready_audio_ids=[],
    )
    current = StreamSnapshot(
        day_id="day",
        run_id="run",
        status="running",
        completed_steps=["open"],
        case_versions={"case-1": now + timedelta(seconds=1)},
        alert_event_ids=["event-1"],
        ready_audio_ids=["morning-1"],
    )

    emitted = events_since(previous, current)

    assert {item.event_type for item in emitted} == {
        ProductEventType.CHECKPOINT_COMPLETED,
        ProductEventType.FINANCIAL_CASE_UPDATED,
        ProductEventType.EVENT_ALERT_CREATED,
        ProductEventType.AUDIO_READY,
    }
