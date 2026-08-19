"""In-process event memory for one coherent financial day."""

from threading import RLock

from .schemas import DailyEventState, EventAssessment, StoredEvent


class DailyEventStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._days: dict[str, DailyEventState] = {}

    def save(self, assessment: EventAssessment) -> StoredEvent:
        key = assessment.event.timestamp.date().isoformat()
        with self._lock:
            day = self._days.setdefault(
                key, DailyEventState(trading_date=assessment.event.timestamp.date())
            )
            existing = next(
                (
                    item
                    for item in day.events
                    if item.assessment.event.event_id == assessment.event.event_id
                ),
                None,
            )
            record = StoredEvent(assessment=assessment)
            if existing is None:
                day.events.append(record)
            else:
                record.notification_status = existing.notification_status
                record.user_action = existing.user_action
                day.events[day.events.index(existing)] = record
            return record.model_copy(deep=True)

    def get_day(self, trading_date) -> DailyEventState:
        key = trading_date.isoformat()
        with self._lock:
            day = self._days.get(key, DailyEventState(trading_date=trading_date))
            return day.model_copy(deep=True)

    def record_user_action(self, event_id: str, action: str) -> bool:
        with self._lock:
            for day in self._days.values():
                for item in day.events:
                    if item.assessment.event.event_id == event_id:
                        item.user_action = action
                        return True
        return False

    def clear(self) -> None:
        with self._lock:
            self._days.clear()


daily_event_store = DailyEventStore()

