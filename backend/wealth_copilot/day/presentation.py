"""Accelerated financial-day clock backed by the canonical day orchestrator."""

import asyncio
from datetime import date
from enum import StrEnum
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field

from ..config import application_today
from .orchestrator import DayOrchestrator, day_orchestrator
from .schemas import StepStatus


DAY_START_MINUTE = 7 * 60
DAY_END_MINUTE = 21 * 60 + 1
DEFAULT_SPEED = 600


def _as_minute(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def _as_clock(minute: int) -> str:
    bounded = max(DAY_START_MINUTE, min(DAY_END_MINUTE, minute))
    return f"{bounded // 60:02d}:{bounded % 60:02d}"


class FinancialDayClockModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FinancialDayClockStatus(StrEnum):
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class FinancialDayClockState(FinancialDayClockModel):
    trading_date: date
    current_time: str
    speed: int
    status: FinancialDayClockStatus
    active_checkpoint: str | None = None
    next_checkpoint: str | None = None
    completed_checkpoint_ids: list[str] = Field(default_factory=list)
    message: str


class FinancialDayAdvanceRequest(FinancialDayClockModel):
    minutes: int = Field(default=60, ge=1, le=840)


class FinancialDayClockService:
    """Runs every scheduled checkpoint through the existing DayOrchestrator."""

    operations = {
        "morning": "run_morning_pulse",
        "health": "run_portfolio_health",
        "open": "run_market_open_monitor",
        "watch": "run_adaptive_market_watch",
        "sector": "run_sector_deep_dive",
        "event": "handle_market_event",
        "learning": "run_contextual_learning",
        "close": "run_market_close",
        "intelligence": "run_portfolio_intelligence",
        "actions": "run_action_queue",
        "evening": "run_evening_wrap",
        "tomorrow": "prepare_tomorrow",
        "story": "generate_daily_story",
    }

    def __init__(
        self,
        orchestrator: DayOrchestrator | None = None,
        *,
        speed: int = DEFAULT_SPEED,
        tick_seconds: float = 0.25,
    ) -> None:
        self.orchestrator = orchestrator or day_orchestrator
        self.speed = speed
        self.tick_seconds = tick_seconds
        self._minute = float(DAY_START_MINUTE)
        self._status = FinancialDayClockStatus.PAUSED
        self._active_checkpoint: str | None = None
        self._message = "Ready at the first financial-day checkpoint."
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._play_requested = False
        self._initialized_date: date | None = None

    def _day(self, selected: date | None = None):
        return self.orchestrator.store.get(selected or application_today())

    def _schedule(self, selected: date) -> list[tuple[str, str, str]]:
        day = self._day(selected)
        scheduled = [
            (step.step_id, step.scheduled_time, self.operations[step.step_id])
            for step in day.timeline
            if step.step_id in self.operations
        ]
        return sorted(scheduled, key=lambda item: (_as_minute(item[1]), item[0]))

    def _restore_persisted(self, selected: date) -> None:
        day = self._day(selected)
        if self._initialized_date == selected and day.run_mode == "presentation":
            return
        if day.run_mode != "presentation":
            self._initialized_date = None
            self._minute = float(DAY_START_MINUTE)
            self._status = FinancialDayClockStatus.PAUSED
            self._active_checkpoint = None
            self._message = "Ready at the first financial-day checkpoint."
            return
        self._initialized_date = selected
        self._minute = float(day.presentation_minute or DAY_START_MINUTE)
        try:
            self._status = FinancialDayClockStatus(day.presentation_status or "paused")
        except ValueError:
            self._status = FinancialDayClockStatus.PAUSED
        self._active_checkpoint = day.presentation_active_checkpoint
        self._message = day.presentation_message or f"Ready at {_as_clock(round(self._minute))}."

    def _persist(self, selected: date) -> None:
        minute = self._minute
        status = self._status.value
        active_checkpoint = self._active_checkpoint
        message = self._message

        def mutate(state) -> None:
            # Persisted field names stay unchanged for backwards compatibility.
            state.presentation_minute = minute
            state.presentation_status = status
            state.presentation_active_checkpoint = active_checkpoint
            state.presentation_message = message

        self.orchestrator.store.update(mutate, selected)

    def state(self, trading_date: date | None = None) -> FinancialDayClockState:
        selected = trading_date or application_today()
        self._restore_persisted(selected)
        day = self._day(selected)
        completed = [
            step.step_id for step in day.timeline if step.status == StepStatus.COMPLETE
        ]
        next_checkpoint = next(
            (
                scheduled
                for step_id, scheduled, _ in self._schedule(selected)
                if step_id not in completed
            ),
            None,
        )
        status = self._status
        if len(completed) == len(day.timeline) and day.timeline:
            status = FinancialDayClockStatus.COMPLETE
        return FinancialDayClockState(
            trading_date=selected,
            current_time=_as_clock(round(self._minute)),
            speed=self.speed,
            status=status,
            active_checkpoint=self._active_checkpoint,
            next_checkpoint=next_checkpoint,
            completed_checkpoint_ids=completed,
            message=self._message,
        )

    async def _ensure_initialized(self, selected: date) -> None:
        day = self._day(selected)
        if self._initialized_date == selected and day.run_mode == "presentation":
            return
        await self.orchestrator.initialize_presentation_day(selected)
        self._initialized_date = selected
        self._minute = float(DAY_START_MINUTE)
        self._status = FinancialDayClockStatus.PAUSED
        self._active_checkpoint = None
        self._message = "Ready at the first financial-day checkpoint."
        self._persist(selected)

    async def restart(self, trading_date: date | None = None) -> FinancialDayClockState:
        selected = trading_date or application_today()
        task = self._task
        self._play_requested = False
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            await self.orchestrator.initialize_presentation_day(selected)
            self._initialized_date = selected
            self._minute = float(DAY_START_MINUTE)
            self._status = FinancialDayClockStatus.PAUSED
            self._active_checkpoint = None
            self._message = "Financial day restarted at 07:00."
            self._task = None
            self._persist(selected)
            return self.state(selected)

    async def restart_and_play(
        self, trading_date: date | None = None
    ) -> FinancialDayClockState:
        selected = trading_date or application_today()
        await self.restart(selected)
        return await self.play(selected)

    async def play(self, trading_date: date | None = None) -> FinancialDayClockState:
        selected = trading_date or application_today()
        async with self._lock:
            await self._ensure_initialized(selected)
            if self._status == FinancialDayClockStatus.COMPLETE:
                return self.state(selected)
            self._play_requested = True
            self._status = FinancialDayClockStatus.RUNNING
            self._message = f"Financial day is moving at {self.speed}x."
            self._persist(selected)
            if not self._task or self._task.done():
                self._task = asyncio.create_task(self._play_loop(selected))
            return self.state(selected)

    async def pause(self, trading_date: date | None = None) -> FinancialDayClockState:
        self._play_requested = False
        if self._status not in {
            FinancialDayClockStatus.COMPLETE,
            FinancialDayClockStatus.FAILED,
        }:
            self._status = FinancialDayClockStatus.PAUSED
            self._message = f"Paused at {_as_clock(round(self._minute))}."
            self._persist(trading_date or application_today())
        return self.state(trading_date)

    async def advance(
        self, minutes: int, trading_date: date | None = None
    ) -> FinancialDayClockState:
        selected = trading_date or application_today()
        async with self._lock:
            await self._ensure_initialized(selected)
            if self._task and not self._task.done():
                return self.state(selected)
            target = min(DAY_END_MINUTE, round(self._minute) + minutes)
            self._play_requested = False
            self._status = FinancialDayClockStatus.RUNNING
            self._message = f"Advancing to {_as_clock(target)}."
            self._persist(selected)
            self._task = asyncio.create_task(self._advance_to(selected, target))
            return self.state(selected)

    async def advance_to_next(
        self, trading_date: date | None = None
    ) -> FinancialDayClockState:
        selected = trading_date or application_today()
        state = self.state(selected)
        if state.next_checkpoint is None:
            return state
        delta = max(1, _as_minute(state.next_checkpoint) - round(self._minute))
        return await self.advance(delta, selected)

    async def _run_due(self, selected: date, target_minute: int) -> None:
        for step_id, scheduled, operation_name in self._schedule(selected):
            scheduled_minute = _as_minute(scheduled)
            if scheduled_minute > target_minute:
                break
            day = self._day(selected)
            step = next(item for item in day.timeline if item.step_id == step_id)
            if step.status == StepStatus.COMPLETE:
                continue
            self._minute = float(scheduled_minute)
            self._active_checkpoint = step_id
            self._message = f"{step.label} is running automatically."
            self._persist(selected)
            self.orchestrator._advance_developer_clock(selected, scheduled)
            operation = getattr(self.orchestrator, operation_name)
            await operation(trading_date=selected)
            self._active_checkpoint = None
            self._message = f"{step.label} completed."
            self._persist(selected)

    def _complete(self, selected: date) -> None:
        day = self._day(selected)
        if all(step.status == StepStatus.COMPLETE for step in day.timeline):
            self.orchestrator.complete_presentation_day(selected)
            self._status = FinancialDayClockStatus.COMPLETE
            self._message = "The financial day and visual recap are complete."

    async def _advance_to(self, selected: date, target_minute: int) -> None:
        try:
            await self._run_due(selected, target_minute)
            self._minute = float(target_minute)
            if target_minute >= DAY_END_MINUTE:
                self._complete(selected)
            else:
                self._status = FinancialDayClockStatus.PAUSED
                self._message = f"Paused at {_as_clock(target_minute)}."
            self._persist(selected)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status = FinancialDayClockStatus.FAILED
            self._message = f"Playback paused safely ({type(exc).__name__})."
            self._persist(selected)
        finally:
            self._active_checkpoint = None

    async def _play_loop(self, selected: date) -> None:
        try:
            await self._run_due(selected, round(self._minute))
            previous = monotonic()
            while self._play_requested and self._minute < DAY_END_MINUTE:
                await asyncio.sleep(self.tick_seconds)
                now = monotonic()
                elapsed = now - previous
                previous = now
                target = min(
                    DAY_END_MINUTE,
                    round(self._minute + (elapsed * self.speed / 60)),
                )
                upcoming = next(
                    (
                        _as_minute(scheduled)
                        for step_id, scheduled, _ in self._schedule(selected)
                        if _as_minute(scheduled) > self._minute
                        and next(
                            step
                            for step in self._day(selected).timeline
                            if step.step_id == step_id
                        ).status
                        != StepStatus.COMPLETE
                    ),
                    None,
                )
                if upcoming is not None and target >= upcoming:
                    target = upcoming
                await self._run_due(selected, target)
                self._minute = float(target)
                self._persist(selected)

            if self._minute >= DAY_END_MINUTE:
                self._complete(selected)
            elif self._status != FinancialDayClockStatus.FAILED:
                self._status = FinancialDayClockStatus.PAUSED
                self._message = f"Paused at {_as_clock(round(self._minute))}."
            self._persist(selected)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status = FinancialDayClockStatus.FAILED
            self._message = f"Playback paused safely ({type(exc).__name__})."
            self._persist(selected)
        finally:
            self._active_checkpoint = None

    async def recover(self, trading_date: date | None = None) -> FinancialDayClockState:
        selected = trading_date or application_today()
        state = self.state(selected)
        if state.status == FinancialDayClockStatus.RUNNING:
            return await self.play(selected)
        return state

    async def stop(self) -> None:
        self._play_requested = False
        task = self._task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None


financial_day_clock = FinancialDayClockService()

# Compatibility names remain available for existing integrations.
PresentationAdvanceRequest = FinancialDayAdvanceRequest
PresentationClockService = FinancialDayClockService
PresentationClockState = FinancialDayClockState
PresentationClockStatus = FinancialDayClockStatus
presentation_clock = financial_day_clock


__all__ = [
    "FinancialDayAdvanceRequest",
    "FinancialDayClockService",
    "FinancialDayClockState",
    "FinancialDayClockStatus",
    "PresentationAdvanceRequest",
    "PresentationClockService",
    "PresentationClockState",
    "PresentationClockStatus",
    "financial_day_clock",
    "presentation_clock",
]
