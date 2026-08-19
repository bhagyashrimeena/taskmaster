"""Small in-process stores for today's interactions and conversation context."""

from dataclasses import dataclass, field
from datetime import date
from threading import RLock

from .schemas import DailyInteractionView


@dataclass
class ConversationRecord:
    active_story_id: str | None = None
    active_event_id: str | None = None
    history: list[tuple[str, str]] = field(default_factory=list)


class ConversationStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, ConversationRecord] = {}

    def get(self, conversation_id: str) -> ConversationRecord:
        with self._lock:
            record = self._records.setdefault(conversation_id, ConversationRecord())
            return ConversationRecord(
                active_story_id=record.active_story_id,
                active_event_id=record.active_event_id,
                history=list(record.history),
            )

    def update_context(
        self, conversation_id: str, *, story_id: str | None, event_id: str | None
    ) -> ConversationRecord:
        with self._lock:
            record = self._records.setdefault(conversation_id, ConversationRecord())
            if story_id:
                record.active_story_id, record.active_event_id = story_id, None
            elif event_id:
                record.active_event_id, record.active_story_id = event_id, None
            return self.get(conversation_id)

    def append(self, conversation_id: str, role: str, text: str) -> None:
        with self._lock:
            record = self._records.setdefault(conversation_id, ConversationRecord())
            record.history.append((role, text))
            record.history[:] = record.history[-12:]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


class DailyInteractionStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._days: dict[str, DailyInteractionView] = {}

    def _day(self, trading_date: date) -> DailyInteractionView:
        return self._days.setdefault(
            trading_date.isoformat(), DailyInteractionView(trading_date=trading_date)
        )

    def save_story(self, story_id: str, trading_date: date | None = None) -> DailyInteractionView:
        with self._lock:
            day = self._day(trading_date or date.today())
            if story_id not in day.saved_story_ids:
                day.saved_story_ids.append(story_id)
            return day.model_copy(deep=True)

    def save_event(self, event_id: str, trading_date: date | None = None) -> DailyInteractionView:
        with self._lock:
            day = self._day(trading_date or date.today())
            if event_id not in day.saved_event_ids:
                day.saved_event_ids.append(event_id)
            return day.model_copy(deep=True)

    def record_feedback(
        self, target_type: str, target_id: str, value: str, trading_date: date | None = None
    ) -> DailyInteractionView:
        with self._lock:
            day = self._day(trading_date or date.today())
            day.feedback[f"{target_type}:{target_id}"] = value
            return day.model_copy(deep=True)

    def get(self, trading_date: date | None = None) -> DailyInteractionView:
        with self._lock:
            return self._day(trading_date or date.today()).model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._days.clear()


conversation_store = ConversationStore()
daily_interaction_store = DailyInteractionStore()

