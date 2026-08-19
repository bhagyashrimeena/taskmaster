import asyncio
from pathlib import Path
import re
from time import perf_counter

from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.dashboard.schemas import FreshnessStatus, RefreshPhase
from wealth_copilot.dashboard.service import DashboardService
from wealth_copilot.events import daily_event_store
from wealth_copilot.market.cache import news_candidate_cache


async def test_dashboard_bootstrap_is_immediate_and_complete() -> None:
    news_candidate_cache.clear()
    daily_event_store.clear()
    service = DashboardService()

    started = perf_counter()
    dashboard = await service.get_dashboard()
    elapsed = perf_counter() - started

    assert elapsed < 1.0
    assert dashboard.portfolio.source.label == "Simulated Portfolio"
    assert dashboard.portfolio.portfolio_value == 841999.8
    assert len(dashboard.daily_brief.stories) == 5
    assert dashboard.daily_brief.freshness.status == FreshnessStatus.CACHED
    assert dashboard.important_event.decision.value == "ALERT"
    assert dashboard.important_event.affected_portfolio_percentage == 18.01
    assert dashboard.important_event.relevance_score == 94.21
    assert len(dashboard.agent_activity) == 5
    assert len(dashboard.today_events) >= 1


async def test_stale_status_keeps_full_dashboard_available() -> None:
    service = DashboardService()
    await service.get_dashboard()
    service._last_refresh_news_status = FreshnessStatus.STALE

    dashboard = await service.get_dashboard()

    assert dashboard.daily_brief.freshness.status == FreshnessStatus.STALE
    assert dashboard.daily_brief.freshness.label.startswith("Last updated ")
    assert len(dashboard.daily_brief.stories) == 5


async def test_background_refresh_start_does_not_wait_for_work() -> None:
    release = asyncio.Event()

    class PausedRefreshService(DashboardService):
        async def _run_refresh(self, refresh_id: str) -> None:
            del refresh_id
            await release.wait()

    service = PausedRefreshService()
    started = perf_counter()
    refresh = await service.start_refresh()
    elapsed = perf_counter() - started

    assert elapsed < 0.1
    assert refresh.phase == RefreshPhase.QUEUED
    assert refresh.refresh_id
    release.set()
    await service._refresh_task


async def test_demo_background_refresh_stays_offline(monkeypatch) -> None:
    from wealth_copilot.dashboard import service as service_module

    monkeypatch.setattr(service_module.settings, "news_provider", "simulated")
    news_candidate_cache.clear()
    service = DashboardService()
    await service.get_dashboard()

    queued = await service.start_refresh()
    await service._refresh_task
    complete = await service.start_refresh()

    assert queued.phase == RefreshPhase.QUEUED
    assert complete.phase == RefreshPhase.COMPLETE
    assert complete.refresh_id == queued.refresh_id
    dashboard = await service.get_dashboard()
    assert dashboard.daily_brief.freshness.status == FreshnessStatus.CACHED


def test_http_dashboard_contract_and_event_action() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["portfolio"]["source"]) == {
        "label", "is_live", "provider", "scenario_id", "checkpoint"
    }
    assert len(payload["daily_brief"]["stories"]) == 5
    assert payload["important_event"]["notification_required"] is True

    event_id = payload["important_event"]["event"]["event_id"]
    saved = client.post(
        f"/api/v1/events/{event_id}/actions",
        json={"action": "save_for_evening"},
    )
    assert saved.status_code == 200
    assert saved.json()["saved"] is True


def test_frontend_contains_no_investment_recommendation_language() -> None:
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for pattern in ("*.tsx", "*.ts", "*.css")
        for path in frontend.rglob(pattern)
        if "node_modules" not in path.parts and ".next" not in path.parts
    )
    banned = re.compile(r"\b(buy|sell|hold|rebalance)\b", re.IGNORECASE)
    assert banned.search(source) is None
