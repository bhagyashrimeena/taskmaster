"""Cross-test isolation for the process-wide deterministic simulation."""

import pytest

from wealth_copilot.simulation import simulation_service
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.events import daily_event_store
from wealth_copilot.interaction.memory import (
    conversation_store,
    daily_interaction_store,
    persistent_memory_store,
)
from wealth_copilot.market.cache import news_candidate_cache
from wealth_copilot.media.service import media_service
from wealth_copilot.story.narration import story_narration_service


@pytest.fixture(autouse=True)
def reset_simulation_state(tmp_path):
    media_service._cache_dir = tmp_path / "audio"
    media_service._cache_dir.mkdir(parents=True, exist_ok=True)
    media_service._briefs.clear()
    media_service._latest.clear()
    media_service._tasks.clear()
    story_narration_service._root = tmp_path / "story-scenes"
    story_narration_service._root.mkdir(parents=True, exist_ok=True)
    story_narration_service._items.clear()
    story_narration_service._tasks.clear()
    persistent_memory_store.reconfigure(tmp_path / "interaction-memory.db")
    persistent_memory_store.clear()
    conversation_store.clear()
    daily_interaction_store.clear()
    simulation_service.load_scenario("hdfc-company-shock")
    simulation_service.reset_scenario()
    financial_day_store.clear()
    daily_event_store.clear()
    news_candidate_cache.clear()
    yield
    media_service._briefs.clear()
    media_service._latest.clear()
    media_service._tasks.clear()
    story_narration_service._items.clear()
    story_narration_service._tasks.clear()
    persistent_memory_store.clear()
    conversation_store.clear()
    daily_interaction_store.clear()
    simulation_service.load_scenario("hdfc-company-shock")
    simulation_service.reset_scenario()
    financial_day_store.clear()
    daily_event_store.clear()
    news_candidate_cache.clear()
