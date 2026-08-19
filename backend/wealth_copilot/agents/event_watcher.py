"""TaskMaster tools for the deterministic Phase 2 Event Watcher."""

from datetime import date

from ..events import EventDecisionEngine, daily_event_store, get_event_fixture
from .portfolio_agent import get_portfolio_summary
from ..portfolio.schemas import PortfolioSummary


event_decision_engine = EventDecisionEngine(store=daily_event_store)


async def run_event_watcher(
    event_id: str = "hdfc-bank-sudden-fall",
) -> dict[str, object]:
    """Evaluate one deterministic market-event fixture against the active portfolio."""

    try:
        event = get_event_fixture(event_id)
        portfolio_result = await get_portfolio_summary()
        if portfolio_result.get("status") != "ok":
            return {
                "status": "error",
                "error": portfolio_result.get("error", "Portfolio is unavailable."),
            }
        portfolio = PortfolioSummary.model_validate(portfolio_result["data"])
        assessment = await event_decision_engine.assess(event, portfolio)
        # Lazy import keeps the Event Watcher usable independently while also
        # joining its result to the durable financial-day record.
        from ..day.orchestrator import day_orchestrator

        day_orchestrator.record_event(assessment)
        return {
            "status": "ok",
            "mode": "deterministic_fixture",
            "data": assessment.model_dump(mode="json"),
        }
    except Exception as exc:
        return {"status": "error", "error": f"Event Watcher failed: {exc}"}


def get_event_day_state(trading_date: str = "2026-08-18") -> dict[str, object]:
    """Return retained event decisions and user actions for one trading day."""

    try:
        parsed = date.fromisoformat(trading_date)
    except ValueError:
        return {"status": "error", "error": "trading_date must use YYYY-MM-DD"}
    return {
        "status": "ok",
        "data": daily_event_store.get_day(parsed).model_dump(mode="json"),
    }


def save_event_action(event_id: str, action: str) -> dict[str, object]:
    """Attach a later user action to an event retained in today's state."""

    saved = daily_event_store.record_user_action(event_id, action)
    return {
        "status": "ok" if saved else "error",
        "event_id": event_id,
        "action": action,
        "saved": saved,
    }


__all__ = [
    "event_decision_engine",
    "get_event_day_state",
    "run_event_watcher",
    "save_event_action",
]
