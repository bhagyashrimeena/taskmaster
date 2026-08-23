"""Generic event-stream contracts and deterministic fixture adapter."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import Field

from .schemas import EventModel, MarketEvent


class MarketEventBatch(EventModel):
    source: str
    events: list[MarketEvent] = Field(default_factory=list)
    next_cursor: str | None = None


class MarketEventStream(ABC):
    source: str

    @abstractmethod
    async def poll(
        self, *, cursor: str | None = None, since: datetime | None = None
    ) -> MarketEventBatch: ...


class InMemoryMarketEventStream(MarketEventStream):
    """Repeatable stream used by tests, demos, and provider adapters."""

    source = "fixture_event_stream"

    def __init__(self, events: list[MarketEvent] | None = None) -> None:
        self._events = sorted(
            (item.model_copy(deep=True) for item in (events or [])),
            key=lambda item: (item.timestamp, item.event_id),
        )

    async def poll(
        self, *, cursor: str | None = None, since: datetime | None = None
    ) -> MarketEventBatch:
        try:
            offset = max(0, int(cursor or "0"))
        except ValueError:
            offset = 0
        available = self._events[offset:]
        if since is not None:
            available = [item for item in available if item.timestamp > since]
        return MarketEventBatch(
            source=self.source,
            events=[item.model_copy(deep=True) for item in available],
            next_cursor=str(len(self._events)),
        )
