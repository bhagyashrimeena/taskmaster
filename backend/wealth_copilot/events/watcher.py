"""Provider-independent event-stream watcher."""

from .engine import EventDecisionEngine
from .schemas import EventAssessment
from .stream import MarketEventStream
from ..portfolio.provider import PortfolioProvider


class EventWatcher:
    def __init__(
        self,
        *,
        stream: MarketEventStream,
        portfolio: PortfolioProvider,
        decision_engine: EventDecisionEngine | None = None,
    ) -> None:
        self.stream = stream
        self.portfolio = portfolio
        self.decision_engine = decision_engine or EventDecisionEngine()

    async def poll(
        self,
        *,
        cursor: str | None = None,
        day_id: str | None = None,
        run_id: str | None = None,
    ) -> tuple[list[EventAssessment], str | None]:
        batch = await self.stream.poll(cursor=cursor)
        if not batch.events:
            return [], batch.next_cursor
        portfolio = await self.portfolio.get_summary()
        assessments = [
            await self.decision_engine.assess(
                event, portfolio, day_id=day_id, run_id=run_id
            )
            for event in batch.events
        ]
        return assessments, batch.next_cursor
