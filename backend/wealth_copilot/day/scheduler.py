"""Small configurable clock scheduler for real financial-day checkpoints."""

import asyncio
from datetime import date, datetime
import logging
from zoneinfo import ZoneInfo

from ..config import get_settings
from .orchestrator import DayOrchestrator, day_orchestrator
from .schemas import StepStatus


logger = logging.getLogger(__name__)


class DayScheduler:
    schedule = {
        "07:00": "run_morning_pulse",
        "08:00": "run_portfolio_health",
        "09:15": "run_market_open_monitor",
        "09:16": "handle_market_event",
        "10:00": "run_adaptive_market_watch",
        "11:30": "run_sector_deep_dive",
        "13:00": "run_contextual_learning",
        "15:30": "run_market_close",
        "17:00": "run_portfolio_intelligence",
        "18:30": "run_action_queue",
        "20:00": "run_evening_wrap",
        "21:00": "prepare_tomorrow",
        "21:01": "generate_daily_story",
    }
    operation_steps = {
        "run_morning_pulse": "morning",
        "run_portfolio_health": "health",
        "run_market_open_monitor": "open",
        "handle_market_event": "event",
        "run_adaptive_market_watch": "watch",
        "run_sector_deep_dive": "sector",
        "run_contextual_learning": "learning",
        "run_market_close": "close",
        "run_portfolio_intelligence": "intelligence",
        "run_action_queue": "actions",
        "run_evening_wrap": "evening",
        "prepare_tomorrow": "tomorrow",
        "generate_daily_story": "story",
    }

    def __init__(self, orchestrator: DayOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or day_orchestrator
        self._completed: set[tuple[date, str]] = set()
        self._task: asyncio.Task | None = None

    def _was_persisted(self, trading_date: date, operation_name: str) -> bool:
        """Recover scheduler completion from the crash-safe financial-day store."""

        store = getattr(self.orchestrator, "store", None)
        step_id = self.operation_steps.get(operation_name)
        if store is None or step_id is None:
            return False
        state = store.get(trading_date)
        return any(
            step.step_id == step_id and step.status == StepStatus.COMPLETE
            for step in state.timeline
        )

    async def run_due(self, now: datetime) -> list[str]:
        local = now.astimezone(ZoneInfo(get_settings().day_schedule_timezone))
        current = local.strftime("%H:%M")
        ran: list[str] = []
        for scheduled, operation_name in self.schedule.items():
            key = (local.date(), operation_name)
            if (
                scheduled <= current
                and key not in self._completed
                and not self._was_persisted(local.date(), operation_name)
            ):
                try:
                    await getattr(self.orchestrator, operation_name)(trading_date=local.date())
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Financial-day checkpoint failed: %s", operation_name)
                    continue
                self._completed.add(key)
                ran.append(operation_name)
        start_minute = 10 * 60
        end_minute = 11 * 60 + 30
        current_minute = local.hour * 60 + local.minute
        if start_minute <= current_minute < end_minute:
            interval = get_settings().market_watch_interval_minutes
            slot_minute = start_minute + (
                (current_minute - start_minute) // interval
            ) * interval
            slot = f"{slot_minute // 60:02d}:{slot_minute % 60:02d}"
            operation_name = "run_adaptive_market_watch"
            key = (local.date(), f"{operation_name}:{slot}")
            if operation_name in ran:
                self._completed.add(key)
            elif key not in self._completed:
                try:
                    await getattr(self.orchestrator, operation_name)(
                        trading_date=local.date()
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Financial-day recurring checkpoint failed: %s at %s",
                        operation_name,
                        slot,
                    )
                else:
                    self._completed.add(key)
                    ran.append(operation_name)
        return ran

    async def _loop(self) -> None:
        zone = ZoneInfo(get_settings().day_schedule_timezone)
        while True:
            try:
                await self.run_due(datetime.now(zone))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Financial-day scheduler iteration failed")
            await asyncio.sleep(30)

    def start(self) -> None:
        if get_settings().day_schedule_mode == "real" and not (
            self._task and not self._task.done()
        ):
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


day_scheduler = DayScheduler()
