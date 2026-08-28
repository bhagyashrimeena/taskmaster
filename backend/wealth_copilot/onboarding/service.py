"""Deterministic onboarding auto-fill for editable profile defaults."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from typing import Any

from ..config import get_settings
from ..persistence import firestore_persistence
from .schemas import (
    AgentPreferences,
    CheckpointPreferences,
    FinancialProfileSuggestions,
    GoalSuggestions,
    OnboardingInferenceRequest,
    OnboardingSaveRequest,
    OnboardingSession,
    ProfileOverride,
    RiskProfileSuggestions,
    SuggestedProfile,
    SuggestedValue,
    VoicePreferences,
)


class OnboardingService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(get_settings().day_state_dir).parent / "onboarding"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, user_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in user_id)
        return self.root / f"{safe or 'demo_user'}.json"

    @staticmethod
    def _has_any(request: OnboardingInferenceRequest, values: set[str]) -> bool:
        return bool(set(request.primary_goals) & values)

    @staticmethod
    def _suggest(value: Any, confidence: str, reason: str) -> SuggestedValue:
        return SuggestedValue(value=value, confidence=confidence, reason=f"Suggested because {reason}")

    def infer(self, request: OnboardingInferenceRequest) -> SuggestedProfile:
        beginner = request.investment_experience == "beginner"
        advanced = request.investment_experience == "advanced"
        active = request.market_interest_level in {"active", "high"}
        quiet = request.quiet_mode or request.market_interest_level == "low"
        long_horizon = request.time_horizon in {"5_plus_years", "10_plus_years", "long_term"}
        short_horizon = request.time_horizon in {"under_1_year", "1_3_years", "short_term"}
        emergency_incomplete = request.emergency_fund_status in {"none", "partial", "incomplete"}
        salaried = request.employment_type == "salaried"
        dependents = request.dependents not in {None, "", "none"}

        if request.age_range in {"18-21", "22-25", "26-30"}:
            life_stage = "early_career"
            life_reason = f"you selected {request.age_range} and are still setting your financial rhythm."
        elif dependents:
            life_stage = "family_builder"
            life_reason = "you mentioned dependents, so household resilience may matter more."
        else:
            life_stage = "established_earner"
            life_reason = "your answers suggest a more established planning stage."

        cashflow_profile = "stable_income" if salaried else "variable_income"
        if request.income_range in {"10L-20L", "20L-50L", "50L_plus"} and salaried:
            cashflow_profile = "growing_income"

        if short_horizon or dependents:
            risk_profile = "conservative"
        elif advanced and active and long_horizon and not emergency_incomplete:
            risk_profile = "moderately_aggressive"
        elif long_horizon:
            risk_profile = "moderate"
        else:
            risk_profile = "balanced"

        risk_capacity = "low" if dependents or emergency_incomplete else "medium"
        if request.income_range in {"20L-50L", "50L_plus"} and long_horizon and not dependents:
            risk_capacity = "medium_high"

        if beginner:
            risk_comfort = "cautious"
        elif active:
            risk_comfort = "market_aware"
        else:
            risk_comfort = "balanced"

        goals = list(dict.fromkeys(request.primary_goals))
        if emergency_incomplete and "emergency_fund" not in goals:
            goals.insert(0, "emergency_fund")
        if not goals:
            goals = ["wealth_building"]
        if "tax_planning" not in goals and request.income_range in {"10L-20L", "20L-50L", "50L_plus"}:
            goals.append("tax_planning")

        order: list[str] = []
        if "emergency_fund" in goals:
            order.append("Build or complete emergency fund")
        if "wealth_building" in goals:
            order.append("Track long-term investments")
        if "retirement" in goals:
            order.append("Review retirement progress")
        order.extend(["Understand portfolio risk", "Review tax planning"])
        order = list(dict.fromkeys(order))

        checkpoints = CheckpointPreferences(
            morning_pulse=True,
            market_open=active and not quiet,
            midday_check=active and not quiet,
            market_close_review=True,
            evening_wrap=True,
            tomorrow_prep=not quiet,
        )
        alert_sensitivity = "quiet" if quiet else "active" if active else "balanced"
        minimum_outcome = "ALERT" if quiet else "MONITOR" if active else "INVESTIGATE"
        voice_style = "simple_advisor" if beginner or request.preferred_explanation_style == "simple" else "market_briefing"
        answer_length = "short" if beginner or quiet else "medium"

        focus_areas = []
        if emergency_incomplete:
            focus_areas.append("emergency_fund")
        if long_horizon:
            focus_areas.extend(["concentration", "sector_exposure", "long_term_changes"])
        if short_horizon:
            focus_areas.extend(["liquidity", "volatility", "capital_preservation"])
        if beginner:
            focus_areas.append("learning")
        if active:
            focus_areas.append("market_updates")
        focus_areas = list(dict.fromkeys(focus_areas or ["portfolio_health"]))

        missing = []
        if request.emergency_fund_status in {None, ""}:
            missing.append("emergency_fund_months")
        if request.dependents in {None, ""}:
            missing.append("dependents")
        missing.extend(["monthly_expenses", "liabilities", "investment_time_horizon_by_goal"])

        return SuggestedProfile(
            financial_profile_suggestions=FinancialProfileSuggestions(
                life_stage=self._suggest(life_stage, "medium" if request.age_range else "low", life_reason),
                cashflow_profile=self._suggest(cashflow_profile, "medium" if request.income_range and request.employment_type else "low", "income stability and range are known, but expenses are not."),
                emergency_fund_focus=self._suggest("complete_first" if emergency_incomplete else "maintain", "medium" if request.emergency_fund_status else "low", "emergency fund status affects how many active market interruptions are useful."),
            ),
            risk_profile_suggestions=RiskProfileSuggestions(
                risk_profile=self._suggest(risk_profile, "medium", "experience, time horizon, emergency fund status, and market interest support this editable default."),
                risk_capacity=self._suggest(risk_capacity, "low" if missing else "medium", "capacity depends on income stability, dependents, liabilities, expenses, and horizon."),
                risk_comfort=self._suggest(risk_comfort, "medium" if request.investment_experience else "low", "your experience level and market interest shape how much volatility context may feel comfortable."),
            ),
            goal_suggestions=GoalSuggestions(
                primary_goal=goals[0],
                secondary_goals=goals[1:],
                suggested_order=order,
            ),
            agent_preferences=AgentPreferences(
                alert_sensitivity=alert_sensitivity,
                minimum_attention_outcome=minimum_outcome,
                focus_areas=focus_areas,
                checkpoint_preferences=checkpoints,
                voice_preferences=VoicePreferences(
                    voice_briefings=True,
                    live_agent_call=True,
                    voice_style=voice_style,
                    answer_length=answer_length,
                ),
                learning_preference="simple_explanations" if beginner else "concise_market_context",
                safety_preferences=[
                    "no_buy_sell_hold_recommendations",
                    "explain_risk_before_actions",
                    "clearly_label_suggestions",
                ],
            ),
            missing_inputs=list(dict.fromkeys(missing)),
        )

    @staticmethod
    def default_final_profile(suggested: SuggestedProfile) -> dict[str, Any]:
        return {
            "life_stage": suggested.financial_profile_suggestions.life_stage.value,
            "cashflow_profile": suggested.financial_profile_suggestions.cashflow_profile.value,
            "emergency_fund_focus": suggested.financial_profile_suggestions.emergency_fund_focus.value,
            "risk_profile": suggested.risk_profile_suggestions.risk_profile.value,
            "risk_capacity": suggested.risk_profile_suggestions.risk_capacity.value,
            "risk_comfort": suggested.risk_profile_suggestions.risk_comfort.value,
            "primary_goal": suggested.goal_suggestions.primary_goal,
            "secondary_goals": suggested.goal_suggestions.secondary_goals,
            "goal_order": suggested.goal_suggestions.suggested_order,
            "agent_preferences": suggested.agent_preferences.model_dump(mode="json"),
        }

    @staticmethod
    def _flatten_suggested(suggested: SuggestedProfile) -> dict[str, Any]:
        return OnboardingService.default_final_profile(suggested)

    def save(self, request: OnboardingSaveRequest) -> OnboardingSession:
        now = datetime.now(timezone.utc)
        existing = self.get(request.user_id)
        created = existing.created_at if existing else now
        suggested_values = self._flatten_suggested(request.suggested_profile)
        overrides = [
            ProfileOverride(field=field, suggested=suggested, selected=request.final_profile[field], updated_at=now)
            for field, suggested in suggested_values.items()
            if field in request.final_profile and request.final_profile[field] != suggested
        ]
        session = OnboardingSession(
            user_id=request.user_id,
            raw_inputs=request.raw_inputs,
            suggested_profile=request.suggested_profile,
            final_profile=request.final_profile,
            overrides=overrides,
            created_at=created,
            updated_at=now,
        )
        payload = session.model_dump(mode="json")
        with self._lock:
            self._path(request.user_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        firestore_persistence.persist_onboarding_session(session)
        return session

    def get(self, user_id: str = "demo_user") -> OnboardingSession | None:
        path = self._path(user_id)
        if not path.exists():
            return None
        try:
            return OnboardingSession.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None


onboarding_service = OnboardingService()
