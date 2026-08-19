"""Small configurable clock scheduler for real financial-day checkpoints."""

import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..config import get_settings
from .orchestrator import DayOrchestrator, day_orchestrator


class DayScheduler:
    schedule = {
        "07:00": "run_morning_pulse",
        "08:00": "run_portfolio_health",
        "15:30": "run_market_close",
        "20:00": "run_evening_wrap",
        "21:00": "prepare_tomorrow",
        "21:01": "generate_daily_story",
    }

    def __init__(self, orchestrator: DayOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or day_orchestrator
        self._completed: set[tuple[date, str]] = set()
        self._task: asyncio.Task | None = None

    async def run_due(self, now: datetime) -> list[str]:
        local = now.astimezone(ZoneInfo(get_settings().day_schedule_timezone))
        current = local.strftime("%H:%M")
        ran: list[str] = []
        for scheduled, operation_name in self.schedule.items():
            key = (local.date(), operation_name)
            if scheduled <= current and key not in self._completed:
                await getattr(self.orchestrator, operation_name)(trading_date=local.date())
                self._completed.add(key)
                ran.append(operation_name)
        return ran

    async def _loop(self) -> None:
        zone = ZoneInfo(get_settings().day_schedule_timezone)
        while True:
            await self.run_due(datetime.now(zone))
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
