"""Crash-safe JSON persistence for FinancialDayState."""

from collections.abc import Callable
from datetime import date, datetime, timezone
import json
from pathlib import Path
from threading import RLock
from time import sleep
from uuid import uuid4

from ..config import application_today, get_settings
from .schemas import FinancialDayState, StepStatus, default_timeline


class FinancialDayStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(get_settings().day_state_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, trading_date: date) -> Path:
        return self.root / f"{trading_date.isoformat()}.json"

    def get(self, trading_date: date | None = None) -> FinancialDayState:
        selected = trading_date or application_today()
        path = self._path(selected)
        with self._lock:
            if not path.exists():
                return FinancialDayState(trading_date=selected)
            try:
                state = FinancialDayState.model_validate_json(path.read_text(encoding="utf-8"))
                existing = {item.step_id for item in state.timeline}
                for step in default_timeline():
                    if step.step_id not in existing:
                        state.timeline.append(step)
                story_step = next(
                    (item for item in state.timeline if item.step_id == "story"), None
                )
                if story_step and state.daily_story and story_step.status != StepStatus.COMPLETE:
                    story_step.status = StepStatus.COMPLETE
                    story_step.detail = (
                        f"{len(state.daily_story.scenes)} moments · "
                        f"{state.daily_story.duration_seconds} sec recap ready."
                    )
                    story_step.linked_ids = [state.daily_story.story_id]
                return state
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                # Preserve the unreadable file for diagnosis; never overwrite it here.
                state = FinancialDayState(trading_date=selected)
                state.last_error = f"Saved day state could not be read ({type(exc).__name__})."
                return state

    def save(self, state: FinancialDayState) -> FinancialDayState:
        state.updated_at = datetime.now(timezone.utc)
        path = self._path(state.trading_date)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        payload = state.model_dump_json(indent=2)
        with self._lock:
            temporary.write_text(payload, encoding="utf-8")
            for attempt in range(20):
                try:
                    temporary.replace(path)
                    break
                except PermissionError:
                    if attempt == 19:
                        raise
                    # Cloud-synced Windows workspaces can briefly lock the old file.
                    sleep(0.01 * (attempt + 1))
        return state.model_copy(deep=True)

    def update(
        self,
        mutator: Callable[[FinancialDayState], None],
        trading_date: date | None = None,
    ) -> FinancialDayState:
        selected = trading_date or application_today()
        with self._lock:
            state = self.get(selected)
            mutator(state)
            return self.save(state)

    def clear(self, trading_date: date | None = None) -> None:
        selected = trading_date or application_today()
        path = self._path(selected)
        with self._lock:
            if path.exists():
                path.unlink()


financial_day_store = FinancialDayStore()
