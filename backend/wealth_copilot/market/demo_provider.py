"""Deterministic Phase 1 news candidates, including noise and a duplicate."""

from datetime import datetime, timedelta, timezone

from ..simulation import simulation_service
from .provider import NewsProvider
from .schemas import EventType, NewsCandidate, NewsCandidateBatch


_FIXTURES = (
    ("infy-results", "Infosys raises full-year revenue guidance after strong quarter", "Infosys reported stronger-than-expected quarterly growth and raised its full-year revenue guidance.", "INFY", "Information Technology", EventType.EARNINGS, 5.2, 2),
    ("hdfc-rbi", "RBI changes liquidity rules affecting HDFC Bank", "The central bank announced a liquidity-rule change with a direct capital and funding impact for large private banks.", "HDFCBANK", "Financial Services", EventType.REGULATORY, -3.1, 3),
    ("reliance-action", "Reliance board approves consumer business demerger plan", "Reliance Industries approved a material corporate restructuring subject to shareholder and regulatory approvals.", "RELIANCE", "Energy", EventType.CORPORATE_ACTION, 2.7, 8),
    ("tcs-deal", "TCS wins multi-year cloud transformation contract", "TCS signed a large multi-year technology transformation agreement with a global enterprise customer.", "TCS", "Information Technology", EventType.PRODUCT, 1.4, 5),
    ("icici-results", "ICICI Bank profit rises as asset quality improves", "ICICI Bank reported higher profit and lower bad-loan ratios in its latest quarterly results.", "ICICIBANK", "Financial Services", EventType.EARNINGS, 1.8, 18),
    ("airtel-spectrum", "Bharti Airtel acquires additional spectrum in key circles", "Bharti Airtel acquired spectrum intended to expand capacity in high-demand telecom markets.", "BHARTIARTL", "Telecommunication", EventType.REGULATORY, 2.2, 20),
    ("wipro-leadership", "Wipro names new chief strategy officer", "Wipro appointed a new strategy leader as it reorganizes its consulting and growth functions.", "WIPRO", "Information Technology", EventType.MANAGEMENT, 0.8, 27),
    ("itc-tax", "Tobacco tax proposal puts cigarette margins in focus", "A proposed excise-duty change could affect cigarette volumes and margins for companies including ITC.", "ITC", "Consumer Staples", EventType.REGULATORY, -2.0, 10),
    ("sunpharma-fda", "Sun Pharma receives US FDA approval for specialty medicine", "The US regulator approved a specialty medicine from Sun Pharma for commercial launch.", "SUNPHARMA", "Healthcare", EventType.REGULATORY, 3.8, 12),
    ("rbi-rates", "RBI keeps policy rate unchanged while retaining neutral stance", "The monetary-policy decision influences lending margins, credit demand, and rate-sensitive sectors.", "", "Financial Services", EventType.MACRO, None, 6),
    ("it-spending", "Global enterprise technology spending outlook improves", "A revised industry forecast points to stronger discretionary technology spending over the next year.", "", "Information Technology", EventType.SECTOR, None, 22),
    ("oil-prices", "Crude oil jumps on renewed supply concerns", "Higher crude prices may affect refining margins, input costs, and inflation expectations in India.", "RELIANCE", "Energy", EventType.MARKET_MOVE, 4.5, 16),
    ("pharma-pricing", "India reviews essential-medicine pricing framework", "A proposed pricing-framework revision could affect domestic pharmaceutical manufacturers.", "", "Healthcare", EventType.REGULATORY, None, 30),
    ("tesla-noise", "Tesla previews next-generation manufacturing line", "The electric vehicle maker shared details about a manufacturing system unrelated to the sample Indian portfolio.", "TESLA", "Automobiles", EventType.PRODUCT, 1.1, 4),
    ("infy-results-duplicate", "Infosys raises revenue guidance following strong quarterly results", "Infosys raised annual guidance after reporting stronger quarterly revenue growth.", "INFY", "Information Technology", EventType.EARNINGS, 5.2, 3),
)


_SCENARIO_LEAD = {
    "hdfc-company-shock": ("hdfc-rbi", "HDFC Bank drops on company-specific concerns", "HDFC Bank fell 5.4% versus a 0.8% banking-sector decline on high volume.", "HDFCBANK", "Financial Services", EventType.MARKET_MOVE, -5.4, 0),
    "it-sector-wide-decline": ("scenario-it-decline", "Indian IT shares decline together in broad sector move", "TCS, Infosys, and Wipro moved closely with a 3% decline in the broader IT sector.", "TCS", "Information Technology", EventType.SECTOR, -3.1, 0),
    "quiet-market-day": ("scenario-quiet-day", "Indian equities trade in a narrow range", "Portfolio holdings and major sectors remained within a narrow range with no material company-specific development.", "", "", EventType.MARKET_MOVE, None, 0),
    "macro-rbi-event": ("scenario-rbi-event", "RBI announces liquidity-policy adjustment", "The policy change may affect funding conditions across private-sector banks.", "", "Financial Services", EventType.MACRO, None, 0),
    "positive-earnings-surprise": ("scenario-infy-earnings", "Infosys rises after positive earnings surprise", "Infosys reported a material earnings surprise and rose 6.2%, well ahead of the IT sector.", "INFY", "Information Technology", EventType.EARNINGS, 6.2, 0),
}


class SimulatedNewsProvider(NewsProvider):
    source = "simulated_scenario_news"
    is_live = False

    async def get_candidates(
        self, *, limit: int = 15, as_of: datetime | None = None
    ) -> NewsCandidateBatch:
        now = as_of or datetime.now(timezone.utc)
        fixtures = list(_FIXTURES)
        fixtures[1] = _SCENARIO_LEAD[simulation_service.state().scenario_id]
        candidates = [
            NewsCandidate(
                id=identifier,
                headline=headline,
                summary=summary,
                source_name="Simulated Financial Wire",
                source_url=(
                    "https://news.example/infy-results?utm_source=duplicate"
                    if identifier == "infy-results-duplicate"
                    else f"https://news.example/{identifier}"
                ),
                published_at=now - timedelta(hours=hours_ago),
                companies=[company] if company else [],
                sectors=[sector],
                event_type=event_type,
                market_move_pct=move,
            )
            for identifier, headline, summary, company, sector, event_type, move, hours_ago in fixtures[:limit]
        ]
        return NewsCandidateBatch(
            source=self.source,
            is_live=False,
            generated_at=now,
            candidates=candidates,
        )


DemoNewsProvider = SimulatedNewsProvider

__all__ = ["DemoNewsProvider", "SimulatedNewsProvider"]
