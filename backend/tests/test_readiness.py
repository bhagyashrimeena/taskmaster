from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError
from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.config import Settings, get_settings
from wealth_copilot import readiness


def test_vertex_flags_normalize_to_one_setting() -> None:
    canonical = Settings(
        google_genai_use_vertexai=True,
        google_genai_use_enterprise=False,
    )
    compatibility = Settings(
        google_genai_use_vertexai=False,
        google_genai_use_enterprise=True,
    )

    assert canonical.vertex_ai_enabled is True
    assert compatibility.vertex_ai_enabled is True


def test_vertex_readiness_never_returns_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness.google.auth,
        "default",
        lambda: (AnonymousCredentials(), "wealth-project"),
    )
    report = readiness.google_readiness(Settings(
        google_genai_use_vertexai=True,
        google_genai_use_enterprise=False,
        google_cloud_project="wealth-project",
        google_cloud_location="global",
        gemini_api_key="must-not-leak",
        google_api_key=None,
        news_provider="google_search",
    ))

    payload = report.model_dump_json()
    assert report.auth_path == "vertex_adc"
    assert report.adc.status == "ready"
    assert report.gemini_adk.status == "ready"
    assert report.google_search_grounding.status == "ready"
    assert report.gemini_tts.status == "ready"
    assert "must-not-leak" not in payload


def test_missing_adc_is_reported_without_crashing(monkeypatch) -> None:
    def missing_credentials():
        raise DefaultCredentialsError("missing")

    monkeypatch.setattr(readiness.google.auth, "default", missing_credentials)
    report = readiness.google_readiness(Settings(
        google_genai_use_vertexai=True,
        google_cloud_project="wealth-project",
    ))

    assert report.adc.status == "not_ready"
    assert report.gemini_adk.status == "not_ready"
    assert report.gemini_tts.status == "not_ready"


def test_readiness_endpoint_is_credential_safe() -> None:
    response = TestClient(app).get("/api/v1/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["google_cloud_project"] == get_settings().google_cloud_project
    assert "gemini_api_key" not in response.text.lower()
    assert "google_api_key" not in response.text.lower()
