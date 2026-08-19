"""Cross-test isolation for the process-wide deterministic simulation."""

import pytest

from wealth_copilot.simulation import simulation_service
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.events import daily_event_store
from wealth_copilot.market.cache import news_candidate_cache


@pytest.fixture(autouse=True)
def reset_simulation_state():
    simulation_service.load_scenario("hdfc-company-shock")
    simulation_service.reset_scenario()
    financial_day_store.clear()
    daily_event_store.clear()
    news_candidate_cache.clear()
    yield
    simulation_service.load_scenario("hdfc-company-shock")
    simulation_service.reset_scenario()
    financial_day_store.clear()
    daily_event_store.clear()
    news_candidate_cache.clear()
