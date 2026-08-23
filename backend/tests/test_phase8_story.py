"""Phase 8 deterministic Daily Wealth Story acceptance tests."""

from datetime import date, datetime, timezone
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from wealth_copilot.advisor.schemas import (
    AdvisorEmailDraft,
    AdvisorPacket,
    AdvisorResponse,
    AdvisorStatus,
)
from wealth_copilot.config import application_today
from wealth_copilot.api import app
from wealth_copilot.day.orchestrator import DayOrchestrator
from wealth_copilot.day.store import FinancialDayStore
from wealth_copilot.media.schemas import AudioBriefType
from wealth_copilot.media.service import media_service
from wealth_copilot.story.schemas import StorySceneKind
from wealth_copilot.story.service import DailyStoryService
from wealth_copilot.story.service import daily_story_service


@pytest.fixture
def store(tmp_path: Path) -> FinancialDayStore:
    return FinancialDayStore(tmp_path / "days")


@pytest.mark.asyncio
async def test_demo_day_generates_accurate_cached_visual_story(store: FinancialDayStore) -> None:
    selected = date(2026, 8, 18)
    state = await DayOrchestrator(store).run_demo_day(selected, duration_seconds=0)
    story = state.daily_story

    assert story is not None
    assert 20 <= story.duration_seconds <= 30
    assert 3 <= len(story.scenes) <= 5
    assert story.portfolio_close == state.portfolio_close_snapshot.portfolio_value
    assert story.portfolio_change_pct == state.market_close_review.portfolio_return_pct
    assert story.top_negative_contributors[0].symbol == "HDFCBANK"
    assert story.top_positive_contributors
    assert story.important_event.event_id == "hdfc-bank-sudden-fall"
    assert len(story.tomorrow_events) == 2
    assert story.audio_brief_id

    cached = await DailyStoryService(store).prepare(selected)
    assert cached.story_id == story.story_id
    assert cached.cached is True


@pytest.mark.asyncio
async def test_advisor_scene_is_conditional_and_invalidates_cached_story(
    store: FinancialDayStore,
) -> None:
    selected = date(2026, 8, 18)
    initial = await DayOrchestrator(store).run_demo_day(selected, duration_seconds=0)
    initial_id = initial.daily_story.story_id
    now = datetime.now(timezone.utc)
    request = AdvisorPacket(
        request_id="advisor-story-test",
        created_at=now,
        updated_at=now,
        target_type="event",
        target_id="hdfc-bank-sudden-fall",
        title="HDFC Bank unusual move",
        exposure="17.21% direct exposure",
        relevance="93.11 relevance",
        facts=["HDFC Bank moved -5.4%."],
        interpretations=["The move differed from the sector."],
        unknowns=["The confirmed cause remains uncertain."],
        sources=[],
        user_question="Does this materially change the view?",
        suggested_questions=[],
        status=AdvisorStatus.REPLIED,
        provider="demo",
        email=AdvisorEmailDraft(
            to_name="Ananya Rao",
            to_email="advisor@example.com",
            subject="Perspective requested",
            body="Reviewed context",
        ),
        sent_at=now,
        response_id="reply-story-test",
    )
    response = AdvisorResponse(
        response_id="reply-story-test",
        request_id=request.request_id,
        received_at=now,
        advisor_name="Ananya Rao",
        message="Worth monitoring; the confirmed cause remains uncertain.",
    )

    def add_advisor(state):
        state.advisor_requests.append(request)
        state.advisor_responses.append(response)

    store.update(add_advisor, selected)
    story = await DailyStoryService(store).prepare(selected)

    assert story.story_id != initial_id
    assert story.advisor_interaction.response_id == response.response_id
    assert StorySceneKind.ADVISOR in {scene.kind for scene in story.scenes}
    assert any("Perspective received" in (scene.secondary_text or "") for scene in story.scenes)


@pytest.mark.asyncio
async def test_missing_optional_sections_are_skipped_gracefully(store: FinancialDayStore) -> None:
    selected = date(2026, 8, 18)
    await DayOrchestrator(store).run_demo_day(selected, duration_seconds=0)

    def make_quiet(state):
        state.events_alerted = []
        state.events_detected = []
        state.advisor_requests = []
        state.advisor_responses = []
        state.saved_stories = []
        state.saved_events = []
        state.tomorrow_events = []

    store.update(make_quiet, selected)
    story = await DailyStoryService(store).prepare(selected)
    kinds = {scene.kind for scene in story.scenes}

    assert StorySceneKind.QUIET in kinds
    assert StorySceneKind.ALERT not in kinds
    assert StorySceneKind.ADVISOR not in kinds
    assert StorySceneKind.SAVED not in kinds
    assert 20 <= story.duration_seconds <= 30


@pytest.mark.asyncio
async def test_short_narration_reuses_media_cache_and_contains_no_recommendation(
    store: FinancialDayStore,
) -> None:
    selected = date(2026, 8, 18)
    state = await DayOrchestrator(store).run_demo_day(selected, duration_seconds=0)
    first = await media_service.prepare(AudioBriefType.STORY, state)
    second = await media_service.prepare(AudioBriefType.STORY, state)

    assert first.brief_id == second.brief_id
    assert first.duration_target_seconds == 24
    assert 20 <= first.estimated_duration_seconds <= 30
    assert re.search(r"\b(buy|sell|hold|rebalance)\b", first.script, re.I) is None


@pytest.mark.asyncio
async def test_story_endpoint_uses_completed_financial_day(
    store: FinancialDayStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    await DayOrchestrator(store).run_demo_day(application_today(), duration_seconds=0)
    monkeypatch.setattr(daily_story_service, "store", store)
    response = TestClient(app).get("/api/v1/story/today")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert 20 <= payload["duration_seconds"] <= 30
