"""Deterministic source-quality and diversity-aware final selection."""

from collections import Counter
import re
from urllib.parse import urlsplit

from ..market.schemas import (
    Materiality,
    PersonalizedNews,
    PersonalizedNewsFeed,
    SourceAuthority,
)


_PRIMARY_MARKERS = {
    "nse", "national stock exchange", "bse", "bombay stock exchange", "rbi",
    "reserve bank of india", "sebi", "press information bureau", "ministry of finance",
    "company filing", "exchange filing",
}
_ESTABLISHED_MARKERS = {
    "reuters", "bloomberg", "financial times", "economic times", "business standard",
    "businessline", "the hindu", "livemint", "mint", "moneycontrol", "cnbc",
    "ndtv profit", "financial express",
}
_SECONDARY_MARKERS = {
    "morningstar", "tipranks", "equitymaster", "tradingview",
    "analytics india magazine", "newsfile", "outlook business",
}
_PRIMARY_DOMAINS = {"nseindia.com", "bseindia.com", "rbi.org.in", "sebi.gov.in", "pib.gov.in"}
_SOURCE_POINTS = {
    SourceAuthority.TIER_1_PRIMARY: 8.0,
    SourceAuthority.TIER_2_ESTABLISHED: 5.0,
    SourceAuthority.TIER_3_SECONDARY: 2.0,
    SourceAuthority.TIER_4_OTHER: 0.0,
}


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def classify_source(story: PersonalizedNews) -> SourceAuthority:
    """Classify source authority from publisher identity and direct domains."""

    name = _normalized(story.source_name)
    hostname = (urlsplit(story.source_url).hostname or "").lower()
    if any(hostname == domain or hostname.endswith(f".{domain}") for domain in _PRIMARY_DOMAINS):
        return SourceAuthority.TIER_1_PRIMARY
    if any(marker in name for marker in _PRIMARY_MARKERS):
        return SourceAuthority.TIER_1_PRIMARY
    if any(marker in name for marker in _ESTABLISHED_MARKERS):
        return SourceAuthority.TIER_2_ESTABLISHED
    if any(marker in name for marker in _SECONDARY_MARKERS):
        return SourceAuthority.TIER_3_SECONDARY
    return SourceAuthority.TIER_4_OTHER


def _headline_similarity(left: str, right: str) -> float:
    left_tokens = set(_normalized(left).split())
    right_tokens = set(_normalized(right).split())
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _event_similarity(candidate: PersonalizedNews, selected: PersonalizedNews) -> float:
    similarity = _headline_similarity(candidate.headline, selected.headline)
    holdings_overlap = bool(set(candidate.affected_holdings) & set(selected.affected_holdings))
    sectors_overlap = bool(set(map(_normalized, candidate.sectors)) & set(map(_normalized, selected.sectors)))
    if candidate.event_type == selected.event_type and (holdings_overlap or sectors_overlap):
        similarity = max(similarity, 0.55)
    return similarity


class DiversityRanker:
    """Greedy final-utility selector with auditable bonuses and penalties."""

    def select(self, feed: PersonalizedNewsFeed, *, limit: int = 5) -> PersonalizedNewsFeed:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")

        remaining = list(feed.stories)
        selected: list[PersonalizedNews] = []
        company_counts: Counter[str] = Counter()

        while remaining and len(selected) < limit:
            evaluated: list[PersonalizedNews] = []
            for story in remaining:
                saturation_count = max(
                    (company_counts[symbol] for symbol in story.affected_holdings), default=0
                )
                max_similarity = max(
                    (_event_similarity(story, previous) for previous in selected), default=0.0
                )

                # Two stories per company is the normal ceiling. A third must be
                # independently critical and dissimilar to what is already selected.
                if saturation_count >= 2 and not (
                    story.materiality == Materiality.CRITICAL and max_similarity < 0.55
                ):
                    continue

                authority = classify_source(story)
                source_points = _SOURCE_POINTS[authority]
                prior_event_types = {item.event_type for item in selected}
                holdings_overlap = any(
                    set(story.affected_holdings) & set(item.affected_holdings)
                    for item in selected
                )
                if not selected or (not holdings_overlap and story.event_type not in prior_event_types):
                    novelty = 4.0
                elif story.event_type not in prior_event_types:
                    novelty = 2.0
                else:
                    novelty = 0.0

                similarity_penalty = round(12.0 * max_similarity, 2)
                saturation_penalty = float(10 * saturation_count)
                materiality_points = story.signals.event_materiality / 15.0 * 8.0
                freshness_points = story.signals.freshness / 10.0 * 5.0
                utility = round(
                    max(
                        0.0,
                        min(
                            100.0,
                            story.relevance_score * 0.75
                            + materiality_points
                            + freshness_points
                            + source_points
                            + novelty
                            - similarity_penalty
                            - saturation_penalty,
                        ),
                    ),
                    2,
                )
                evaluated.append(
                    story.model_copy(
                        update={
                            "source_authority": authority,
                            "source_quality_score": source_points,
                            "novelty_score": novelty,
                            "similarity_penalty": similarity_penalty,
                            "company_saturation_penalty": saturation_penalty,
                            "final_utility_score": utility,
                            "selection_reason": (
                                f"Utility combines {story.relevance_score:.2f} relevance with "
                                f"{authority.value} source authority and diversity adjustments."
                            ),
                        }
                    )
                )

            if not evaluated:
                break
            winner = max(
                evaluated,
                key=lambda item: (item.final_utility_score, item.relevance_score, item.published_at),
            )
            selected.append(winner)
            company_counts.update(winner.affected_holdings)
            remaining = [story for story in remaining if story.id != winner.id]

        return feed.model_copy(update={"stories": selected})
