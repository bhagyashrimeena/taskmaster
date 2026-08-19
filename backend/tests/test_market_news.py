from datetime import datetime, timezone

from google.adk.tools.google_search_tool import GoogleSearchTool
import pytest
from pydantic import ValidationError

from wealth_copilot.agents.market_agent import market_agent
from wealth_copilot.agents.relevance_agent import rank_personalized_news, relevance_agent
from wealth_copilot.market.demo_provider import DemoNewsProvider
from wealth_copilot.market.canonical import _is_rejected, _domain_matches, story_identity
from wealth_copilot.market.normalization import normalize_candidates
from wealth_copilot.market.schemas import NewsCandidate


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


async def test_demo_provider_returns_fifteen_sourced_candidates() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    assert batch.is_live is False
    assert len(batch.candidates) == 15
    assert len({candidate.id for candidate in batch.candidates}) == 15
    assert all(candidate.source_name for candidate in batch.candidates)
    assert all(candidate.source_url.startswith("https://") for candidate in batch.candidates)
    assert all(candidate.published_at.tzinfo for candidate in batch.candidates)


async def test_normalization_removes_tracking_url_duplicate() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    normalized = normalize_candidates(batch.candidates)
    assert len(normalized) == 14
    assert sum("Infosys raises" in candidate.headline for candidate in normalized) == 1


def test_live_market_agent_has_search_tool_only() -> None:
    assert len(market_agent.tools) == 1
    assert isinstance(market_agent.tools[0], GoogleSearchTool)
    assert market_agent.tools[0].name == "google_search"


def test_relevance_agent_does_not_have_search_tool() -> None:
    assert len(relevance_agent.tools) == 1
    assert not isinstance(relevance_agent.tools[0], GoogleSearchTool)


def test_candidate_rejects_publisher_homepage() -> None:
    with pytest.raises(ValidationError, match="publisher homepage"):
        NewsCandidate.model_validate(
            {
                "id": "homepage",
                "headline": "A sufficiently long financial headline",
                "summary": "A sufficiently long summary for schema validation.",
                "source_name": "Example",
                "source_url": "https://example.com/",
                "published_at": NOW,
            }
        )


async def test_normalization_drops_bad_source_without_losing_batch() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    raw = [candidate.model_dump() for candidate in batch.candidates]
    raw[1]["source_url"] = "https://example.com/"

    normalized = normalize_candidates(raw)

    assert len(normalized) == 13
    assert all(candidate.source_url != "https://example.com/" for candidate in normalized)


async def test_relevance_tool_skips_bad_candidate_instead_of_failing_batch() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=15, as_of=NOW)
    raw = [candidate.model_dump(mode="json") for candidate in batch.candidates]
    raw[1]["source_url"] = "https://example.com/"

    result = await rank_personalized_news(raw, news_source="test", news_is_live=True, limit=5)

    assert result["status"] == "ok"
    assert result["data"]["news_is_live"] is True
    assert len(result["data"]["stories"]) == 5
    assert all(story["source_url"] != "https://example.com/" for story in result["data"]["stories"])


def test_canonical_resolution_rejects_transient_and_wrong_domains() -> None:
    assert _is_rejected("https://vertexaisearch.cloud.google.com/grounding-api-redirect/token")
    assert _is_rejected("https://news.google.com/search?q=hdfc")
    assert _domain_matches("https://www.business-standard.com/markets/news/article-123", "Business Standard")
    assert not _domain_matches("https://example.com/article-123", "Business Standard")


async def test_story_identity_is_stable_for_resolution_cache() -> None:
    batch = await DemoNewsProvider().get_candidates(limit=1, as_of=NOW)
    normalized = normalize_candidates(batch.candidates)
    first = normalized[0]
    second = first.model_copy(deep=True)
    assert story_identity(first) == story_identity(second)
