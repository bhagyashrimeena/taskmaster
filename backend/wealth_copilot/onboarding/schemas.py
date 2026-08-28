"""Contracts for suggested, editable onboarding defaults."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Confidence = Literal["low", "medium", "high"]


class OnboardingModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class OnboardingInferenceRequest(OnboardingModel):
    user_id: str = "demo_user"
    age_range: str | None = None
    income_range: str | None = None
    employment_type: str | None = None
    investment_experience: str | None = None
    existing_investments: list[str] = Field(default_factory=list)
    primary_goals: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    dependents: str | None = None
    emergency_fund_status: str | None = None
    market_interest_level: str | None = None
    preferred_explanation_style: str | None = None
    quiet_mode: bool = False


class SuggestedValue(OnboardingModel):
    value: Any
    confidence: Confidence
    reason: str


class FinancialProfileSuggestions(OnboardingModel):
    life_stage: SuggestedValue
    cashflow_profile: SuggestedValue
    emergency_fund_focus: SuggestedValue


class RiskProfileSuggestions(OnboardingModel):
    risk_profile: SuggestedValue
    risk_capacity: SuggestedValue
    risk_comfort: SuggestedValue


class GoalSuggestions(OnboardingModel):
    primary_goal: str
    secondary_goals: list[str] = Field(default_factory=list)
    suggested_order: list[str] = Field(default_factory=list)


class CheckpointPreferences(OnboardingModel):
    morning_pulse: bool = True
    market_open: bool = False
    midday_check: bool = False
    market_close_review: bool = True
    evening_wrap: bool = True
    tomorrow_prep: bool = True


class VoicePreferences(OnboardingModel):
    voice_briefings: bool = True
    live_agent_call: bool = True
    voice_style: str = "simple_advisor"
    answer_length: str = "short"


class AgentPreferences(OnboardingModel):
    alert_sensitivity: str = "balanced"
    minimum_attention_outcome: str = "INVESTIGATE"
    focus_areas: list[str] = Field(default_factory=list)
    checkpoint_preferences: CheckpointPreferences = Field(default_factory=CheckpointPreferences)
    voice_preferences: VoicePreferences = Field(default_factory=VoicePreferences)
    learning_preference: str = "simple_explanations"
    safety_preferences: list[str] = Field(default_factory=list)


class SuggestedProfile(OnboardingModel):
    financial_profile_suggestions: FinancialProfileSuggestions
    risk_profile_suggestions: RiskProfileSuggestions
    goal_suggestions: GoalSuggestions
    agent_preferences: AgentPreferences
    missing_inputs: list[str] = Field(default_factory=list)
    disclaimer: str = "These are suggested defaults based on what you shared. You can change anything."


class ProfileOverride(OnboardingModel):
    field: str
    suggested: Any
    selected: Any
    updated_at: datetime


class OnboardingSession(OnboardingModel):
    user_id: str = "demo_user"
    raw_inputs: OnboardingInferenceRequest
    suggested_profile: SuggestedProfile
    final_profile: dict[str, Any]
    overrides: list[ProfileOverride] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class OnboardingSaveRequest(OnboardingModel):
    user_id: str = "demo_user"
    raw_inputs: OnboardingInferenceRequest
    suggested_profile: SuggestedProfile
    final_profile: dict[str, Any]


class OnboardingProfileResponse(OnboardingModel):
    session: OnboardingSession | None = None
