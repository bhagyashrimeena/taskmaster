"""Deterministic event and investigation fixtures for the Phase 2 demo."""

from datetime import datetime, timedelta, timezone

from ..market.schemas import EventType, NewsCandidate
from .schemas import EventSeverity, MarketEvent, MarketEventType


AS_OF = datetime(2026, 8, 18, 6, 47, tzinfo=timezone.utc)  # 12:17 PM IST


EVENT_FIXTURES = (
    MarketEvent(event_id="hdfc-bank-sudden-fall", timestamp=AS_OF, event_type=MarketEventType.PRICE_MOVE, symbol="HDFCBANK", company="HDFC Bank", sector="Financial Services", price_change_pct=-5.4, sector_change_pct=-0.8, index_change_pct=-0.4, volume_change_pct=185, headline="HDFC Bank falls sharply on company-specific concerns", source="Demo Market Feed", source_url="https://events.example/hdfc-bank-sudden-fall", severity=EventSeverity.CRITICAL, has_material_news=True),
    MarketEvent(event_id="tcs-sector-aligned-move", timestamp=AS_OF + timedelta(minutes=3), event_type=MarketEventType.PRICE_MOVE, symbol="TCS", company="TCS", sector="Information Technology", price_change_pct=-1.1, sector_change_pct=-1.0, index_change_pct=-0.5, volume_change_pct=8, headline="TCS tracks a modest decline in the IT sector", source="Demo Market Feed", source_url="https://events.example/tcs-sector-aligned-move", severity=EventSeverity.LOW),
    MarketEvent(event_id="hdfc-sector-wide-selloff", timestamp=AS_OF + timedelta(minutes=7), event_type=MarketEventType.PRICE_MOVE, symbol="HDFCBANK", company="HDFC Bank", sector="Financial Services", price_change_pct=-3.4, sector_change_pct=-3.1, index_change_pct=-1.8, volume_change_pct=22, headline="HDFC Bank declines with a broad banking selloff", source="Demo Market Feed", source_url="https://events.example/hdfc-sector-wide-selloff", severity=EventSeverity.MEDIUM),
    MarketEvent(event_id="infosys-volume-spike", timestamp=AS_OF + timedelta(minutes=10), event_type=MarketEventType.VOLUME_SPIKE, symbol="INFY", company="Infosys", sector="Information Technology", price_change_pct=2.1, sector_change_pct=0.3, index_change_pct=0.1, volume_change_pct=240, headline="Infosys trading volume jumps far above normal", source="Demo Market Feed", source_url="https://events.example/infosys-volume-spike", severity=EventSeverity.HIGH),
    MarketEvent(event_id="reliance-earnings", timestamp=AS_OF + timedelta(minutes=13), event_type=MarketEventType.EARNINGS, symbol="RELIANCE", company="Reliance Industries", sector="Energy", price_change_pct=4.2, sector_change_pct=0.7, headline="Reliance reports material earnings surprise", source="Demo Company Filing", source_url="https://events.example/reliance-earnings", severity=EventSeverity.HIGH, has_material_news=True),
    MarketEvent(event_id="sunpharma-regulatory", timestamp=AS_OF + timedelta(minutes=16), event_type=MarketEventType.REGULATORY, symbol="SUNPHARMA", company="Sun Pharma", sector="Healthcare", price_change_pct=-2.6, sector_change_pct=0.2, headline="Regulatory update affects a Sun Pharma facility", source="Demo Regulator", source_url="https://events.example/sunpharma-regulatory", severity=EventSeverity.HIGH, has_material_news=True),
    MarketEvent(event_id="rbi-liquidity-macro", timestamp=AS_OF + timedelta(minutes=20), event_type=MarketEventType.MACRO, sector="Financial Services", sector_change_pct=-1.7, index_change_pct=-0.5, headline="RBI announces a material liquidity-policy adjustment", source="Demo RBI Feed", source_url="https://events.example/rbi-liquidity-macro", severity=EventSeverity.HIGH, has_material_news=True),
    MarketEvent(event_id="tesla-unrelated-news", timestamp=AS_OF + timedelta(minutes=24), event_type=MarketEventType.NEWS, symbol="TSLA", company="Tesla", sector="Automobiles", price_change_pct=4.0, headline="Tesla previews a manufacturing platform", source="Demo Global Wire", source_url="https://events.example/tesla-unrelated-news", severity=EventSeverity.MEDIUM, has_material_news=True),
    MarketEvent(event_id="airtel-corporate-announcement", timestamp=AS_OF + timedelta(minutes=28), event_type=MarketEventType.CORPORATE_ANNOUNCEMENT, symbol="BHARTIARTL", company="Bharti Airtel", sector="Telecommunication", price_change_pct=2.4, sector_change_pct=0.4, headline="Bharti Airtel announces a material spectrum transaction", source="Demo Exchange Filing", source_url="https://events.example/airtel-corporate-announcement", severity=EventSeverity.HIGH, has_material_news=True),
    MarketEvent(event_id="itc-specific-drop", timestamp=AS_OF + timedelta(minutes=32), event_type=MarketEventType.PRICE_MOVE, symbol="ITC", company="ITC", sector="Consumer Staples", price_change_pct=-5.2, sector_change_pct=-0.4, index_change_pct=-0.2, volume_change_pct=150, headline="ITC drops sharply after a tax-policy development", source="Demo Market Feed", source_url="https://events.example/itc-specific-drop", severity=EventSeverity.CRITICAL, has_material_news=True),
)


def get_event_fixture(event_id: str) -> MarketEvent:
    try:
        event = next(item for item in EVENT_FIXTURES if item.event_id == event_id)
    except StopIteration as exc:
        available = ", ".join(item.event_id for item in EVENT_FIXTURES)
        raise ValueError(f"Unknown event fixture '{event_id}'. Available: {available}") from exc
    return event.model_copy(deep=True)


def _development(identifier: str, headline: str, summary: str, event: MarketEvent, event_type: EventType) -> NewsCandidate:
    return NewsCandidate(
        id=identifier,
        headline=headline,
        summary=summary,
        source_name=event.source,
        source_url=f"https://investigation.example/{identifier}",
        published_at=event.timestamp - timedelta(minutes=5),
        companies=[event.company] if event.company else [],
        sectors=[event.sector] if event.sector else [],
        event_type=event_type,
        market_move_pct=event.price_change_pct,
    )


DEVELOPMENT_FIXTURES = {
    "hdfc-bank-sudden-fall": [
        _development("hdfc-regulatory-review", "Regulatory review puts HDFC Bank disclosures in focus", "A new regulatory review created company-specific uncertainty around recent disclosures.", EVENT_FIXTURES[0], EventType.REGULATORY),
        _development("hdfc-block-trade", "Large HDFC Bank block trades accompany unusual decline", "Trading activity was substantially above normal while the stock underperformed its sector.", EVENT_FIXTURES[0], EventType.MARKET_MOVE),
    ],
    "reliance-earnings": [_development("reliance-earnings-detail", "Reliance earnings exceed market expectations", "The reported earnings surprise was led by a material improvement in consumer businesses.", EVENT_FIXTURES[4], EventType.EARNINGS)],
    "sunpharma-regulatory": [_development("sunpharma-regulator-detail", "Regulator issues observations for Sun Pharma facility", "The observations may delay approvals associated with the affected manufacturing site.", EVENT_FIXTURES[5], EventType.REGULATORY)],
    "airtel-corporate-announcement": [_development("airtel-spectrum-detail", "Airtel files details of spectrum transaction", "The exchange filing describes the transaction size and expected network-capacity impact.", EVENT_FIXTURES[8], EventType.CORPORATE_ACTION)],
    "itc-specific-drop": [_development("itc-tax-detail", "Tax proposal creates company-specific pressure for ITC", "The proposed tax change could affect cigarette volumes and near-term operating margins.", EVENT_FIXTURES[9], EventType.REGULATORY)],
}

