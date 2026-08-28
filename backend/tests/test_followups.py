import pytest
from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.dashboard.service import dashboard_service
from wealth_copilot.day.orchestrator import day_orchestrator
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.followups import followup_service
from wealth_copilot.persistence import firestore_persistence


@pytest.mark.asyncio
async def test_likely_scenarios_are_created_from_relevant_news_without_prediction_language():
    dashboard = await dashboard_service.get_dashboard()
    state = followup_service.ensure_from_stories(dashboard.daily_brief.stories)

    reliance = [item for item in state.likely_scenarios if item.symbol == "RELIANCE"]
    assert len(reliance) == 3
    assert {item.scenario_type for item in reliance} == {"bullish", "neutral", "risk"}
    joined = " ".join(
        f"{item.why_it_could_happen} {item.what_to_monitor}" for item in reliance
    ).lower()
    for blocked in ["guaranteed", "definitely", "invest now", "target price"]:
        assert blocked not in joined
    assert "not predictions" not in joined


@pytest.mark.asyncio
async def test_internal_watch_event_links_to_scenario_and_does_not_claim_external_calendar():
    dashboard = await dashboard_service.get_dashboard()
    state = followup_service.ensure_from_stories(dashboard.daily_brief.stories)
    scenario = next(item for item in state.likely_scenarios if item.symbol == "RELIANCE")

    event = followup_service.create_watch_event(
        title="Review Reliance market reaction",
        description="Review price movement, sector reaction, and follow-up announcements.",
        symbol="RELIANCE",
        story_id=scenario.story_id,
        scenario_id=scenario.scenario_id,
    )

    assert event.status == "scheduled"
    assert event.external_event_id is None
    assert event.external_provider is None
    assert event.scenario_id == scenario.scenario_id


@pytest.mark.asyncio
async def test_product_api_exposes_scenarios_and_watch_events():
    await day_orchestrator.run_morning_pulse()
    followup_service.ensure_reliance_watch_event()

    client = TestClient(app)
    today = client.get("/api/v1/today").json()
    timeline = client.get("/api/v1/timeline").json()
    copilot = client.get("/api/v1/copilot").json()

    assert today["likely_scenarios"]
    assert timeline["calendar_watch_events"]
    assert copilot["likely_scenario_count"] >= 1
    assert copilot["watch_event_count"] >= 1
    assert "not predictions" in (copilot["scenario_context"] or "").lower()


def test_firestore_status_reports_safe_mode_without_secrets():
    firestore_persistence.configured()
    client = TestClient(app)
    payload = client.get("/api/v1/persistence/status").json()
    assert isinstance(payload["firestore_enabled"], bool)
    assert "reason" in payload
    assert "secret" not in str(payload["reason"]).lower()


def test_watch_event_endpoint_creates_internal_event_only():
    client = TestClient(app)
    response = client.post(
        "/api/v1/watch-events",
        json={
            "title": "Review Reliance market reaction",
            "description": "Review price movement, sector reaction, and follow-up announcements.",
            "symbol": "RELIANCE",
            "trigger_type": "news_followup",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["external_calendar_synced"] is False
    assert payload["event"]["symbol"] == "RELIANCE"
    assert payload["event"]["external_event_id"] is None
    assert "Internal watch event" in payload["message"]
