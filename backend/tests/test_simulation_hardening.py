from datetime import date, datetime, timezone
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.day.orchestrator import DayOrchestrator
from wealth_copilot.day.store import FinancialDayStore
from wealth_copilot.events import EventDecisionEngine
from wealth_copilot.events.schemas import EventDecision
from wealth_copilot.portfolio.simulated_provider import SimulatedPortfolioProvider
from wealth_copilot.simulation import simulation_service
from wealth_copilot.media.provider import pcm_to_wav
from wealth_copilot.market.cache import NewsCandidateCache
from wealth_copilot.market.schemas import CanonicalUrlResolution
from wealth_copilot.market.demo_provider import SimulatedNewsProvider
from wealth_copilot.story.narration import StoryNarrationService
from wealth_copilot.story.schemas import StoryNarrationStatus


async def test_scenario_controller_changes_prices_and_provenance() -> None:
    provider = SimulatedPortfolioProvider()
    simulation_service.load_scenario("hdfc-company-shock")
    simulation_service.advance_to("09:15")
    opening = await provider.get_summary()

    state = simulation_service.advance_to("12:17")
    event = await provider.get_summary()

    assert state.provider == "simulated"
    assert event.provider == "simulated"
    assert event.scenario_id == "hdfc-company-shock"
    assert event.as_of.isoformat() == "2026-08-18T12:17:00+05:30"
    assert event.portfolio_value < opening.portfolio_value
    hdfc = next(item for item in event.holdings if item.symbol == "HDFCBANK")
    assert round(float(hdfc.day_pnl / (hdfc.quantity * hdfc.previous_close) * 100), 1) == -5.4


async def test_all_scenario_decisions_are_repeatable() -> None:
    expected = {
        "hdfc-company-shock": EventDecision.ALERT,
        "it-sector-wide-decline": EventDecision.MONITOR,
        "macro-rbi-event": EventDecision.MONITOR,
        "positive-earnings-surprise": EventDecision.ALERT,
    }
    provider = SimulatedPortfolioProvider()
    for scenario_id, decision in expected.items():
        simulation_service.load_scenario(scenario_id)
        event = simulation_service.get_market_event()
        assert event is not None
        assessment = await EventDecisionEngine().assess(event, await provider.get_summary())
        assert assessment.decision == decision


async def test_quiet_scenario_finishes_without_alert() -> None:
    simulation_service.load_scenario("quiet-market-day")
    store = FinancialDayStore()
    state = await DayOrchestrator(store).run_demo_day(
        date(2026, 8, 18), duration_seconds=0
    )
    assert state.events_alerted == []
    assert state.events_detected == []
    assert state.market_close_review is not None
    assert abs(state.market_close_review.portfolio_return_pct) < 0.5


def test_simulation_api_load_advance_reset_and_errors() -> None:
    client = TestClient(app)
    loaded = client.post("/api/v1/simulation/scenarios/it-sector-wide-decline")
    assert loaded.status_code == 200
    assert loaded.json()["scenario_id"] == "it-sector-wide-decline"
    assert loaded.json()["checkpoint"] == "12:17"

    advanced = client.post("/api/v1/simulation/advance", json={"checkpoint": "15:30"})
    assert advanced.status_code == 200
    assert advanced.json()["checkpoint"] == "15:30"

    reset = client.post("/api/v1/simulation/reset")
    assert reset.status_code == 200
    assert reset.json()["checkpoint"] == "07:00"
    assert client.post("/api/v1/simulation/scenarios/not-real").status_code == 404


async def test_each_financial_day_replay_gets_one_consistent_run_id(tmp_path: Path) -> None:
    store = FinancialDayStore(tmp_path / "run-days")
    orchestrator = DayOrchestrator(store)
    first = await orchestrator.run_demo_day(date(2026, 8, 18), duration_seconds=0)
    second = await orchestrator.run_demo_day(date(2026, 8, 18), duration_seconds=0)

    assert first.day_id == second.day_id
    assert first.run_id != second.run_id
    assert all(event.run_id == first.run_id for event in first.events_detected)
    assert all(event.run_id == second.run_id for event in second.events_detected)
    assert first.daily_story.run_id == first.run_id
    assert second.daily_story.run_id == second.run_id


class _ShortSceneAudio:
    async def synthesize(self, script: str) -> bytes:
        assert script.endswith(".")
        return pcm_to_wav(b"\x00\x00" * 24000)


async def test_story_narration_is_generated_and_timed_per_scene(tmp_path: Path) -> None:
    store = FinancialDayStore(tmp_path / "days")
    state = await DayOrchestrator(store).run_demo_day(
        date(2026, 8, 18), duration_seconds=0
    )
    story = state.daily_story
    assert story is not None
    service = StoryNarrationService(_ShortSceneAudio(), tmp_path / "narration")
    queued = service.start(story)
    assert queued.status == StoryNarrationStatus.QUEUED

    for _ in range(200):
        narration = service.get(story.story_id)
        if narration and narration.status == StoryNarrationStatus.READY:
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("scene narration did not finish")

    assert len(narration.scenes) == len(story.scenes)
    assert all(scene.actual_duration_seconds == 1.25 for scene in narration.scenes)
    assert narration.total_duration_seconds == len(story.scenes) * 1.25
    assert all(service.audio_path(story.story_id, scene.scene_id) for scene in narration.scenes)


async def test_successful_live_market_snapshot_survives_process_restart(tmp_path: Path) -> None:
    batch = await SimulatedNewsProvider().get_candidates(limit=10)
    batch.source = "google_search_grounding"
    batch.is_live = True
    snapshot_path = tmp_path / "market" / "latest.json"

    first_process = NewsCandidateCache(snapshot_path)
    first_process.set(batch)
    second_process = NewsCandidateCache(snapshot_path)
    restored = second_process.snapshot()

    assert restored is not None
    assert restored.batch.source == "google_search_grounding"
    assert restored.batch.is_live is True
    assert len(restored.batch.candidates) == 10


async def test_canonical_url_resolution_survives_process_restart(tmp_path: Path) -> None:
    batch = await SimulatedNewsProvider().get_candidates(limit=1)
    batch.source = "google_search_grounding"
    batch.is_live = True
    snapshot_path = tmp_path / "market" / "latest.json"
    first_process = NewsCandidateCache(snapshot_path)
    first_process.set(batch)
    first_process.update_canonical_urls({
        "story-key": CanonicalUrlResolution(
            canonical_url="https://business-standard.com/article-123",
            status="verified",
            resolved_at=datetime.now(timezone.utc),
        )
    })
    second_process = NewsCandidateCache(snapshot_path)
    assert second_process.canonical_urls()["story-key"].canonical_url == "https://business-standard.com/article-123"
