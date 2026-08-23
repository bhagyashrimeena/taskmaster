"""Explainable deterministic scoring over news and portfolio exposure."""

from datetime import datetime, timezone
import re

from ..market.normalization import normalize_candidates
from ..market.schemas import (
    EventType,
    Materiality,
    NewsCandidate,
    PersonalizedNews,
    PersonalizedNewsFeed,
    RelevanceSignals,
)
from ..portfolio.schemas import Holding, PortfolioSummary


_COMPANY_ALIASES = {
    "HDFCBANK": {"HDFCBANK", "HDFCBANKLTD", "HDFCBANKLIMITED", "HDFCBANK"},
    "RELIANCE": {"RELIANCE", "RELIANCEINDUSTRIES", "RELIANCEINDUSTRIESLTD", "RIL"},
    "INFY": {"INFY", "INFOSYS", "INFOSYSLTD", "INFOSYSLIMITED"},
    "TCS": {"TCS", "TATACONSULTANCYSERVICES"},
    "ICICIBANK": {"ICICIBANK", "ICICIBANKLTD", "ICICI"},
    "BHARTIARTL": {"BHARTIARTL", "BHARTIAIRTEL", "AIRTEL"},
    "WIPRO": {"WIPRO", "WIPROLTD"},
    "ITC": {"ITC", "ITCLTD"},
    "SUNPHARMA": {"SUNPHARMA", "SUNPHARMACEUTICAL", "SUNPHARMACEUTICALINDUSTRIES"},
}

_SECTOR_ALIASES = {
    "it": "informationtechnology",
    "technology": "informationtechnology",
    "software": "informationtechnology",
    "banking": "financialservices",
    "banks": "financialservices",
    "finance": "financialservices",
    "financials": "financialservices",
    "telecom": "telecommunication",
    "pharma": "healthcare",
    "pharmaceuticals": "healthcare",
    "oilgas": "energy",
    "consumer": "consumerstaples",
    "fmcg": "consumerstaples",
}

_MATERIALITY = {
    EventType.REGULATORY: (Materiality.CRITICAL, 15.0),
    EventType.CORPORATE_ACTION: (Materiality.CRITICAL, 15.0),
    EventType.EARNINGS: (Materiality.HIGH, 13.0),
    EventType.MARKET_MOVE: (Materiality.HIGH, 12.0),
    EventType.MANAGEMENT: (Materiality.HIGH, 10.0),
    EventType.MACRO: (Materiality.MEDIUM, 9.0),
    EventType.PRODUCT: (Materiality.MEDIUM, 8.0),
    EventType.SECTOR: (Materiality.MEDIUM, 7.0),
    EventType.OTHER: (Materiality.LOW, 3.0),
}


def _token(value: str) -> str:
    return "".join(re.findall(r"[A-Z0-9]+", value.upper()))


def _sector_token(value: str) -> str:
    raw = _token(value).lower()
    return _SECTOR_ALIASES.get(raw, raw)


def _company_matches(symbol: str, company: str) -> bool:
    symbol_key = _token(symbol)
    company_key = _token(company)
    aliases = _COMPANY_ALIASES.get(symbol_key, {symbol_key})
    return company_key in aliases or symbol_key == company_key


def _freshness_score(published_at: datetime, now: datetime) -> float:
    published = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - published.astimezone(timezone.utc)).total_seconds() / 3600)
    if age_hours <= 6:
        return 10.0
    if age_hours <= 24:
        return 8.0
    if age_hours <= 48:
        return 5.0
    if age_hours <= 72:
        return 2.0
    return 0.0


def _holding_day_move(holding: Holding) -> float:
    if not holding.previous_close:
        return 0.0
    return float((holding.current_price - holding.previous_close) / holding.previous_close * 100)


class RelevanceEngine:
    """Ranks news with auditable signals; it never calls an LLM."""

    def score_candidate(
        self,
        candidate: NewsCandidate,
        portfolio: PortfolioSummary,
        *,
        now: datetime | None = None,
    ) -> PersonalizedNews:
        current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        affected = [
            holding
            for holding in portfolio.holdings
            if any(_company_matches(holding.symbol, company) for company in candidate.companies)
        ]
        affected_symbols = [holding.symbol for holding in affected]
        affected_value = sum((holding.market_value for holding in affected), start=0)
        direct_exposure = (
            round(float(affected_value / portfolio.portfolio_value * 100), 1)
            if portfolio.portfolio_value
            else 0.0
        )

        candidate_sectors = {_sector_token(sector) for sector in candidate.sectors}
        candidate_sectors.update(
            _sector_token(holding.sector or "") for holding in affected if holding.sector
        )
        sector_exposure = round(
            sum(
                float(sector.portfolio_weight)
                for sector in portfolio.sector_exposure
                if _sector_token(sector.sector) in candidate_sectors
            ),
            1,
        )

        materiality, materiality_points = _MATERIALITY[candidate.event_type]
        observed_moves = [abs(_holding_day_move(holding)) for holding in affected]
        if candidate.market_move_pct is not None:
            observed_moves.append(abs(candidate.market_move_pct))
        largest_move = max(observed_moves, default=0.0)

        signals = RelevanceSignals(
            direct_holding=35.0 if affected else 0.0,
            exposure_magnitude=round(min(20.0, direct_exposure), 2),
            sector_exposure=round(min(12.0, sector_exposure / 30.0 * 12.0), 2),
            event_materiality=materiality_points,
            freshness=_freshness_score(candidate.published_at, current_time),
            market_movement=round(min(8.0, largest_move * 2.0), 2),
        )
        score = signals.total

        if affected_symbols:
            why = (
                f"Directly affects {', '.join(affected_symbols)}, representing "
                f"{direct_exposure:.2f}% of this portfolio."
            )
        elif sector_exposure:
            why = (
                f"Matches sectors representing {sector_exposure:.2f}% of this portfolio, "
                "even though no holding was named directly."
            )
        else:
            why = "No direct holding or portfolio-sector match was detected."

        movement_text = f" The largest associated move is {largest_move:.2f}%." if largest_move else ""
        return PersonalizedNews(
            **candidate.model_dump(),
            affected_holdings=affected_symbols,
            direct_exposure_pct=direct_exposure,
            sector_exposure_pct=sector_exposure,
            relevance_score=score,
            materiality=materiality,
            signals=signals,
            why_it_matters=f"{why} This is a {materiality.value} materiality {candidate.event_type.value} event.{movement_text}",
            why_am_i_seeing_this=why,
            notification_required=score >= 85.0 and materiality in {Materiality.HIGH, Materiality.CRITICAL},
        )

    def rank(
        self,
        candidates: list[NewsCandidate | dict],
        portfolio: PortfolioSummary,
        *,
        news_source: str,
        news_is_live: bool = False,
        limit: int = 5,
        now: datetime | None = None,
    ) -> PersonalizedNewsFeed:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        normalized = normalize_candidates(candidates)
        scored = [self.score_candidate(candidate, portfolio, now=now) for candidate in normalized]
        scored.sort(
            key=lambda story: (story.relevance_score, story.published_at), reverse=True
        )
        generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return PersonalizedNewsFeed(
            portfolio_source=portfolio.source,
            news_source=news_source,
            news_is_live=news_is_live,
            generated_at=generated_at,
            candidate_count=len(candidates),
            deduplicated_count=len(normalized),
            stories=scored[:limit],
        )
