"""Read-only ADK tool projections for the deterministic operator."""


def get_taskmaster_operator_state() -> dict[str, object]:
    """Return retained cases, attention usage, and recent operator decisions."""

    from ..day.orchestrator import day_orchestrator

    state = day_orchestrator.current_state()
    return {
        "status": "ok",
        "day_id": state.day_id,
        "run_id": state.run_id,
        "attention_budget": state.attention_budget.model_dump(mode="json"),
        "open_cases": [
            item.model_dump(mode="json")
            for item in state.financial_cases
            if item.case_id in state.open_case_ids
        ],
        "recent_decisions": [
            item.model_dump(mode="json") for item in state.operator_cycles[-5:]
        ],
    }
