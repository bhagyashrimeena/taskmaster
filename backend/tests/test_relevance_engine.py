from datetime import datetime, timezone

from wealth_copilot.market.demo_provider import DemoNewsProvider
from wealth_copilot.portfolio.demo_provider import DemoPortfolioProvider
from wealth_copilot.relevance.engine import RelevanceEngine


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


async def test_engine_returns_explainable_top_five() -> None:
    portfolio = await DemoPortfolioProvider().get_summary()
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    feed = RelevanceEngine().rank(
        batch.candidates,
        portfolio,
        news_source=batch.source,
        limit=5,
        now=NOW,
    )

    assert feed.candidate_count == 15
    assert feed.news_is_live is False
    assert feed.deduplicated_count == 14
    assert len(feed.stories) == 5
    assert [story.relevance_score for story in feed.stories] == sorted(
        (story.relevance_score for story in feed.stories), reverse=True
    )
    assert all(story.relevance_score == story.signals.total for story in feed.stories)
    assert all(story.source_url and story.why_am_i_seeing_this for story in feed.stories)
    assert all(story.affected_holdings for story in feed.stories)
    assert "tesla-noise" not in {story.id for story in feed.stories}


async def test_direct_holding_beats_unrelated_noise() -> None:
    portfolio = await DemoPortfolioProvider().get_summary()
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    by_id = {candidate.id: candidate for candidate in batch.candidates}
    engine = RelevanceEngine()
    infosys = engine.score_candidate(by_id["infy-results"], portfolio, now=NOW)
    tesla = engine.score_candidate(by_id["tesla-noise"], portfolio, now=NOW)

    assert infosys.affected_holdings == ["INFY"]
    assert infosys.direct_exposure_pct == 14.0
    assert infosys.sector_exposure_pct == 32.0
    assert infosys.relevance_score > tesla.relevance_score
    assert tesla.affected_holdings == []
    assert tesla.direct_exposure_pct == 0


async def test_sector_story_uses_sector_exposure_without_direct_match() -> None:
    portfolio = await DemoPortfolioProvider().get_summary()
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    story = next(candidate for candidate in batch.candidates if candidate.id == "it-spending")
    scored = RelevanceEngine().score_candidate(story, portfolio, now=NOW)

    assert scored.affected_holdings == []
    assert scored.direct_exposure_pct == 0
    assert scored.sector_exposure_pct == 32.0
    assert scored.signals.sector_exposure == 12.0
