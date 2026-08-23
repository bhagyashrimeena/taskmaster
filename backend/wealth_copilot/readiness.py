"""Credential-safe Google/Vertex configuration readiness diagnostics."""

import logging
from typing import Literal

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from pydantic import BaseModel

from .config import Settings, get_settings


# Uvicorn configures this logger in both development and production launches,
# so the startup diagnostic is visible without changing global logging policy.
logger = logging.getLogger("uvicorn.error")
ReadinessStatus = Literal["ready", "not_ready"]


class ReadinessComponent(BaseModel):
    status: ReadinessStatus
    detail: str


class GoogleReadinessReport(BaseModel):
    google_cloud_project: str | None
    auth_path: Literal["vertex_adc", "developer_api", "unconfigured"]
    adc: ReadinessComponent
    gemini_adk: ReadinessComponent
    google_search_grounding: ReadinessComponent
    gemini_tts: ReadinessComponent
    diagnostic_scope: Literal["configuration"] = "configuration"


def _component(ready: bool, ready_detail: str, missing_detail: str) -> ReadinessComponent:
    return ReadinessComponent(
        status="ready" if ready else "not_ready",
        detail=ready_detail if ready else missing_detail,
    )


def google_readiness(settings: Settings | None = None) -> GoogleReadinessReport:
    """Report usable auth configuration without exposing or sending credentials."""

    config = settings or get_settings()
    try:
        google.auth.default()
        adc_ready = True
    except DefaultCredentialsError:
        adc_ready = False

    api_key_ready = bool(config.google_api_key or config.gemini_api_key)
    if config.vertex_ai_enabled:
        auth_path = "vertex_adc"
        auth_ready = bool(config.google_cloud_project) and adc_ready
        missing = (
            "Set GOOGLE_CLOUD_PROJECT."
            if not config.google_cloud_project
            else "Application Default Credentials were not found."
        )
        ready_detail = "Vertex AI is configured to use Application Default Credentials."
    elif api_key_ready:
        auth_path = "developer_api"
        auth_ready = True
        missing = ""
        ready_detail = "Gemini Developer API authentication is configured."
    else:
        auth_path = "unconfigured"
        auth_ready = False
        missing = "Enable Vertex AI with a project and ADC, or configure an optional API key."
        ready_detail = ""

    adc = _component(
        adc_ready,
        "Application Default Credentials were discovered.",
        "Application Default Credentials were not found.",
    )
    gemini_adk = _component(auth_ready, ready_detail, missing)
    search_enabled = config.news_provider == "google_search"
    search_ready = auth_ready if search_enabled else True
    search_ready_detail = (
        f"Google Search grounding is configured through {auth_path}."
        if search_enabled
        else "Google Search grounding is disabled by NEWS_PROVIDER."
    )
    google_search = _component(search_ready, search_ready_detail, missing)
    tts = _component(
        auth_ready,
        f"Gemini TTS is configured through {auth_path} using {config.tts_model}.",
        missing,
    )
    return GoogleReadinessReport(
        google_cloud_project=config.google_cloud_project,
        auth_path=auth_path,
        adc=adc,
        gemini_adk=gemini_adk,
        google_search_grounding=google_search,
        gemini_tts=tts,
    )


def log_google_readiness() -> GoogleReadinessReport:
    """Log only readiness state, project, and auth path; never credential values."""

    report = google_readiness()
    logger.info(
        "Google readiness project=%s auth=%s adc=%s adk=%s search=%s tts=%s",
        report.google_cloud_project or "missing",
        report.auth_path,
        report.adc.status,
        report.gemini_adk.status,
        report.google_search_grounding.status,
        report.gemini_tts.status,
    )
    return report
