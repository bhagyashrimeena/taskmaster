from wealth_copilot.onboarding.schemas import OnboardingInferenceRequest, OnboardingSaveRequest
from wealth_copilot.onboarding.service import OnboardingService


def test_onboarding_inference_produces_editable_suggested_defaults(tmp_path):
    service = OnboardingService(root=tmp_path)
    request = OnboardingInferenceRequest(
        age_range="22-25",
        income_range="10L-20L",
        employment_type="salaried",
        investment_experience="beginner",
        existing_investments=["equity", "mutual_funds"],
        primary_goals=["wealth_building", "emergency_fund"],
        time_horizon="5_plus_years",
        dependents="none",
        emergency_fund_status="partial",
        market_interest_level="moderate",
        preferred_explanation_style="simple",
    )

    suggested = service.infer(request)

    assert suggested.financial_profile_suggestions.life_stage.value == "early_career"
    assert suggested.risk_profile_suggestions.risk_profile.value == "moderate"
    assert suggested.agent_preferences.alert_sensitivity == "balanced"
    assert suggested.agent_preferences.voice_preferences.voice_style == "simple_advisor"
    assert "change anything" in suggested.disclaimer.lower()


def test_onboarding_save_tracks_user_overrides_and_final_profile(tmp_path):
    service = OnboardingService(root=tmp_path)
    raw = OnboardingInferenceRequest(investment_experience="beginner", time_horizon="5_plus_years")
    suggested = service.infer(raw)
    final_profile = service.default_final_profile(suggested)
    final_profile["risk_profile"] = "moderately_aggressive"

    session = service.save(OnboardingSaveRequest(raw_inputs=raw, suggested_profile=suggested, final_profile=final_profile))
    loaded = service.get("demo_user")

    assert loaded is not None
    assert loaded.final_profile["risk_profile"] == "moderately_aggressive"
    assert session.overrides[0].field == "risk_profile"
    assert session.overrides[0].suggested == suggested.risk_profile_suggestions.risk_profile.value


def test_missing_inputs_lower_risk_capacity_confidence(tmp_path):
    service = OnboardingService(root=tmp_path)
    suggested = service.infer(OnboardingInferenceRequest())

    assert suggested.risk_profile_suggestions.risk_capacity.confidence == "low"
    assert "monthly_expenses" in suggested.missing_inputs
    assert "liabilities" in suggested.missing_inputs


def test_active_investor_gets_more_checkpoints(tmp_path):
    service = OnboardingService(root=tmp_path)
    suggested = service.infer(
        OnboardingInferenceRequest(
            investment_experience="advanced",
            time_horizon="10_plus_years",
            emergency_fund_status="complete",
            market_interest_level="active",
        )
    )

    checkpoints = suggested.agent_preferences.checkpoint_preferences
    assert checkpoints.market_open is True
    assert checkpoints.midday_check is True
    assert suggested.agent_preferences.minimum_attention_outcome == "MONITOR"


def test_quiet_user_gets_fewer_immediate_alerts(tmp_path):
    service = OnboardingService(root=tmp_path)
    suggested = service.infer(OnboardingInferenceRequest(quiet_mode=True, market_interest_level="low"))

    assert suggested.agent_preferences.alert_sensitivity == "quiet"
    assert suggested.agent_preferences.minimum_attention_outcome == "ALERT"
    assert suggested.agent_preferences.checkpoint_preferences.market_open is False
    assert suggested.agent_preferences.checkpoint_preferences.midday_check is False


def test_emergency_fund_incomplete_affects_goal_priority(tmp_path):
    service = OnboardingService(root=tmp_path)
    suggested = service.infer(
        OnboardingInferenceRequest(primary_goals=["wealth_building"], emergency_fund_status="partial")
    )

    assert suggested.goal_suggestions.primary_goal == "emergency_fund"
    assert suggested.financial_profile_suggestions.emergency_fund_focus.value == "complete_first"


def test_onboarding_does_not_generate_investment_advice_or_specific_recommendations(tmp_path):
    service = OnboardingService(root=tmp_path)
    suggested = service.infer(OnboardingInferenceRequest(primary_goals=["wealth_building"]))
    payload = suggested.model_dump_json().lower()

    for blocked in ["buy ", "sell ", "hold ", "target price", "invest in reliance", "invest in hdfc"]:
        assert blocked not in payload
