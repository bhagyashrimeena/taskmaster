"""Deterministic financial-day simulation contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..events.schemas import MarketEvent


class SimulationModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SimulationMode(StrEnum):
    NORMAL = "normal"
    JUDGE = "judge"


class SimulationSnapshot(SimulationModel):
    checkpoint: str
    as_of: datetime
    holding_returns_pct: dict[str, float]
    sector_moves_pct: dict[str, float] = Field(default_factory=dict)


class SimulationScenario(SimulationModel):
    scenario_id: str
    name: str
    description: str
    snapshots: list[SimulationSnapshot]
    event: MarketEvent | None = None


class SimulationState(SimulationModel):
    provider: str = "simulated"
    mode: SimulationMode
    scenario_id: str
    scenario_name: str
    checkpoint: str
    as_of: datetime
    available_scenarios: list[str]
    has_market_event: bool


class AdvanceSimulationRequest(SimulationModel):
    checkpoint: str = Field(min_length=4, max_length=5)
