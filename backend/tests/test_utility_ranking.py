from datetime import datetime, timedelta, timezone

from wealth_copilot.market.demo_provider import DemoNewsProvider
from wealth_copilot.market.schemas import EventType, NewsCandidate, SourceAuthority
from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider
from wealth_copilot.relevance.engine import RelevanceEngine
from wealth_copilot.relevance.utility import DiversityRanker, classify_source


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


async def test_source_authority_prefers_primary_and_established_sources() -> None:
    portfolio = await DemoPortfolioProvider().get_summary()
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    story = RelevanceEngine().score_candidate(batch.candidates[0], portfolio, now=NOW)

    primary = story.model_copy(
        update={"source_name": "Reserve Bank of India", "source_url": "https://rbi.org.in/notices/1"}
    )
    established = story.model_copy(
        update={"source_name": "Reuters", "source_url": "https://reuters.com/world/india/story"}
    )

    assert classify_source(primary) == SourceAuthority.TIER_1_PRIMARY
    assert classify_source(established) == SourceAuthority.TIER_2_ESTABLISHED


async def test_final_selector_caps_noncritical_company_saturation() -> None:
    portfolio = await DemoPortfolioProvider().get_summary()
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    hdfc_seed = next(item for item in batch.candidates if item.id == "hdfc-rbi")
    headlines = [
        "HDFC Bank reports quarterly earnings beat",
        "HDFC Bank appoints retail banking chief",
        "HDFC Bank launches credit card partnership",
        "HDFC Bank schedules institutional investor meeting",
    ]
    candidates = [
        NewsCandidate(
            **hdfc_seed.model_dump(exclude={"id", "headline", "source_url", "published_at", "event_type"}),
            id=f"hdfc-{index}",
            headline=headlines[index],
            source_url=f"https://news.example/hdfc-{index}",
            published_at=NOW - timedelta(hours=index),
            event_type=EventType.EARNINGS,
        )
        for index in range(4)
    ]
    candidates.extend(
        item for item in batch.candidates if item.id in {"infy-results", "reliance-action", "icici-results"}
    )
    feed = RelevanceEngine().rank(
        candidates,
        portfolio,
        news_source="test",
        limit=20,
        now=NOW,
    )

    selected = DiversityRanker().select(feed, limit=5)

    assert len(selected.stories) == 5
    assert sum("HDFCBANK" in story.affected_holdings for story in selected.stories) <= 2
    assert all(story.final_utility_score > 0 for story in selected.stories)
    assert all(story.selection_reason for story in selected.stories)
