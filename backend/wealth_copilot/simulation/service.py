"""Thread-safe controller for a repeatable simulated financial day."""

from threading import RLock

from ..config import get_settings
from .scenarios import SCENARIOS
from .schemas import SimulationScenario, SimulationSnapshot, SimulationState


class SimulationService:
    def __init__(self) -> None:
        settings = get_settings()
        self._lock = RLock()
        self._scenario_id = settings.simulation_scenario_id
        self._checkpoint = "08:00"

    def load_scenario(self, scenario_id: str) -> SimulationState:
        if scenario_id not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario_id}'. Available: {', '.join(SCENARIOS)}"
            )
        with self._lock:
            self._scenario_id = scenario_id
            self._checkpoint = "12:17"
            return self.state()

    def reset_scenario(self) -> SimulationState:
        with self._lock:
            self._checkpoint = "07:00"
            return self.state()

    def advance_to(self, checkpoint: str) -> SimulationState:
        scenario = self.scenario()
        available = [snapshot.checkpoint for snapshot in scenario.snapshots]
        if checkpoint not in available:
            raise ValueError(
                f"Unknown checkpoint '{checkpoint}'. Available: {', '.join(available)}"
            )
        with self._lock:
            self._checkpoint = checkpoint
            return self.state()

    def scenario(self) -> SimulationScenario:
        with self._lock:
            return SCENARIOS[self._scenario_id].model_copy(deep=True)

    def snapshot(self) -> SimulationSnapshot:
        scenario = self.scenario()
        return next(
            snapshot.model_copy(deep=True)
            for snapshot in scenario.snapshots
            if snapshot.checkpoint == self._checkpoint
        )

    def get_current_snapshot(self) -> SimulationSnapshot:
        return self.snapshot()

    def get_market_event(self):
        return self.scenario().event

    def get_close_snapshot(self) -> SimulationSnapshot:
        return next(
            snapshot.model_copy(deep=True)
            for snapshot in self.scenario().snapshots
            if snapshot.checkpoint == "15:30"
        )

    def state(self) -> SimulationState:
        scenario = self.scenario()
        snapshot = self.snapshot()
        return SimulationState(
            mode=get_settings().simulation_mode,
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            checkpoint=snapshot.checkpoint,
            as_of=snapshot.as_of,
            available_scenarios=list(SCENARIOS),
            has_market_event=scenario.event is not None,
        )


simulation_service = SimulationService()
