"""Fixed scenario packs used by the simulated portfolio and judge feed."""

from datetime import datetime
from zoneinfo import ZoneInfo

from ..events.schemas import EventSeverity, MarketEvent, MarketEventType
from .schemas import SimulationScenario, SimulationSnapshot


IST = ZoneInfo("Asia/Kolkata")
TRADING_DATE = (2026, 8, 18)
CHECKPOINTS = ("07:00", "09:15", "12:17", "15:30", "20:00", "21:00")


def _at(value: str) -> datetime:
    hour, minute = (int(part) for part in value.split(":"))
    return datetime(*TRADING_DATE, hour, minute, tzinfo=IST)


def _snapshots(
    midday: dict[str, float],
    close: dict[str, float],
    sectors_midday: dict[str, float],
    sectors_close: dict[str, float] | None = None,
) -> list[SimulationSnapshot]:
    flat = {symbol: 0.0 for symbol in close}
    return [
        SimulationSnapshot(checkpoint="07:00", as_of=_at("07:00"), holding_returns_pct=flat),
        SimulationSnapshot(checkpoint="09:15", as_of=_at("09:15"), holding_returns_pct=flat),
        SimulationSnapshot(
            checkpoint="12:17",
            as_of=_at("12:17"),
            holding_returns_pct={**flat, **midday},
            sector_moves_pct=sectors_midday,
        ),
        SimulationSnapshot(
            checkpoint="15:30",
            as_of=_at("15:30"),
            holding_returns_pct=close,
            sector_moves_pct=sectors_close or sectors_midday,
        ),
        SimulationSnapshot(
            checkpoint="20:00",
            as_of=_at("20:00"),
            holding_returns_pct=close,
            sector_moves_pct=sectors_close or sectors_midday,
        ),
        SimulationSnapshot(
            checkpoint="21:00",
            as_of=_at("21:00"),
            holding_returns_pct=close,
            sector_moves_pct=sectors_close or sectors_midday,
        ),
    ]


HDFC_CLOSE = {
    "HDFCBANK": -5.4,
    "RELIANCE": 0.2,
    "INFY": 2.1,
    "TCS": -0.6,
    "ICICIBANK": -0.4,
    "BHARTIARTL": 0.8,
    "WIPRO": 0.4,
    "ITC": -0.3,
    "SUNPHARMA": 0.5,
}


SCENARIOS = {
    "hdfc-company-shock": SimulationScenario(
        scenario_id="hdfc-company-shock",
        name="HDFC company-specific shock",
        description="HDFC Bank falls far more than the banking sector and crosses the alert threshold.",
        snapshots=_snapshots(
            {"HDFCBANK": -5.4, "ICICIBANK": -0.6},
            HDFC_CLOSE,
            {"Financial Services": -0.8},
        ),
        event=MarketEvent(
            event_id="hdfc-bank-sudden-fall",
            timestamp=_at("12:17"),
            event_type=MarketEventType.PRICE_MOVE,
            symbol="HDFCBANK",
            company="HDFC Bank",
            sector="Financial Services",
            price_change_pct=-5.4,
            sector_change_pct=-0.8,
            index_change_pct=-0.4,
            volume_change_pct=185,
            headline="HDFC Bank falls sharply on company-specific concerns",
            source="Simulated Market Feed",
            source_url="https://events.example/hdfc-bank-sudden-fall",
            severity=EventSeverity.CRITICAL,
            has_material_news=True,
        ),
    ),
    "it-sector-wide-decline": SimulationScenario(
        scenario_id="it-sector-wide-decline",
        name="IT sector-wide decline",
        description="TCS, Infosys, and Wipro move with their sector, producing a monitor decision.",
        snapshots=_snapshots(
            {"TCS": -3.1, "INFY": -2.9, "WIPRO": -3.0},
            {"HDFCBANK": 0.1, "RELIANCE": -0.2, "INFY": -2.9, "TCS": -3.1, "ICICIBANK": 0.0, "BHARTIARTL": 0.2, "WIPRO": -3.0, "ITC": 0.1, "SUNPHARMA": -0.1},
            {"Information Technology": -3.0},
        ),
        event=MarketEvent(
            event_id="it-sector-wide-decline",
            timestamp=_at("12:17"),
            event_type=MarketEventType.PRICE_MOVE,
            symbol="TCS",
            company="TCS",
            sector="Information Technology",
            price_change_pct=-3.1,
            sector_change_pct=-3.0,
            index_change_pct=-0.5,
            volume_change_pct=18,
            headline="IT holdings decline with a broad sector move",
            source="Simulated Market Feed",
            source_url="https://events.example/it-sector-wide-decline",
            severity=EventSeverity.MEDIUM,
        ),
    ),
    "quiet-market-day": SimulationScenario(
        scenario_id="quiet-market-day",
        name="Quiet market day",
        description="All holdings remain within half a percent and no event requires interruption.",
        snapshots=_snapshots(
            {"HDFCBANK": 0.2, "INFY": -0.2, "TCS": 0.1},
            {"HDFCBANK": 0.3, "RELIANCE": -0.1, "INFY": -0.2, "TCS": 0.1, "ICICIBANK": 0.2, "BHARTIARTL": 0.1, "WIPRO": -0.1, "ITC": 0.0, "SUNPHARMA": 0.2},
            {"Financial Services": 0.2, "Information Technology": -0.1},
        ),
        event=None,
    ),
    "macro-rbi-event": SimulationScenario(
        scenario_id="macro-rbi-event",
        name="RBI macro event",
        description="An RBI liquidity change affects the portfolio's financial-services exposure.",
        snapshots=_snapshots(
            {"HDFCBANK": -1.8, "ICICIBANK": -1.6},
            {"HDFCBANK": -1.7, "RELIANCE": 0.1, "INFY": 0.2, "TCS": 0.1, "ICICIBANK": -1.5, "BHARTIARTL": 0.0, "WIPRO": 0.1, "ITC": 0.2, "SUNPHARMA": 0.1},
            {"Financial Services": -1.7},
        ),
        event=MarketEvent(
            event_id="rbi-liquidity-macro",
            timestamp=_at("12:17"),
            event_type=MarketEventType.MACRO,
            sector="Financial Services",
            sector_change_pct=-1.7,
            index_change_pct=-0.5,
            headline="RBI announces a material liquidity-policy adjustment",
            source="Simulated RBI Feed",
            source_url="https://events.example/rbi-liquidity-macro",
            severity=EventSeverity.HIGH,
            has_material_news=True,
        ),
    ),
    "positive-earnings-surprise": SimulationScenario(
        scenario_id="positive-earnings-surprise",
        name="Positive earnings surprise",
        description="Infosys rises sharply after a material earnings surprise.",
        snapshots=_snapshots(
            {"INFY": 6.2, "TCS": 0.8, "WIPRO": 0.7},
            {"HDFCBANK": 0.2, "RELIANCE": 0.3, "INFY": 6.2, "TCS": 0.8, "ICICIBANK": 0.1, "BHARTIARTL": 0.2, "WIPRO": 0.7, "ITC": 0.0, "SUNPHARMA": 0.2},
            {"Information Technology": 0.8},
        ),
        event=MarketEvent(
            event_id="infosys-positive-earnings",
            timestamp=_at("12:17"),
            event_type=MarketEventType.EARNINGS,
            symbol="INFY",
            company="Infosys",
            sector="Information Technology",
            price_change_pct=6.2,
            sector_change_pct=0.8,
            index_change_pct=0.3,
            volume_change_pct=160,
            headline="Infosys rises after a positive earnings surprise",
            source="Simulated Company Filing",
            source_url="https://events.example/infosys-positive-earnings",
            severity=EventSeverity.HIGH,
            has_material_news=True,
        ),
    ),
}
