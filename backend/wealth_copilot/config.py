"""Environment-backed application configuration."""

from functools import lru_cache
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env", override=False)


class Settings(BaseSettings):
    """Wealth Copilot settings. Credentials are read but never logged."""

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    portfolio_provider: Literal["simulated", "zerodha"] = "simulated"
    market_data_provider: Literal["demo"] = "demo"
    news_provider: Literal["simulated", "google_search"] = "google_search"
    simulation_mode: Literal["normal", "judge"] = "normal"
    simulation_scenario_id: str = "hdfc-company-shock"
    news_candidate_count: int = Field(default=20, ge=10, le=20)
    news_cache_ttl_seconds: int = Field(default=900, ge=0, le=86400)
    market_snapshot_file: str = str(_BACKEND_DIR / ".cache" / "market" / "latest.json")
    zerodha_mcp_url: str = "https://mcp.kite.trade/mcp"
    zerodha_mcp_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    adk_model: str = "gemini-3.5-flash"
    interaction_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    portfolio_interaction_timeout_seconds: float = Field(default=45.0, gt=0, le=180)
    research_timeout_seconds: float = Field(default=90.0, gt=0, le=300)
    tts_model: str = "gemini-3.1-flash-tts-preview"
    tts_voice: str = "Kore"
    tts_language_code: str = "en-IN"
    audio_cache_dir: str = str(_BACKEND_DIR / ".cache" / "audio")
    day_state_dir: str = str(_BACKEND_DIR / ".cache" / "days")
    day_schedule_mode: Literal["disabled", "real", "demo"] = "real"
    day_schedule_timezone: str = "Asia/Kolkata"
    market_watch_interval_minutes: int = Field(default=15, ge=5, le=60)
    demo_day_duration_seconds: int = Field(default=72, ge=60, le=90)
    demo_step_timeout_seconds: float = Field(default=45, ge=5, le=120)
    advisor_provider: Literal["demo", "gmail"] = "demo"
    advisor_name: str = "Ananya Rao"
    advisor_email: str = "advisor@example.com"
    advisor_firm: str = "Independent Wealth Advisor"
    advisor_sender_email: str | None = None
    advisor_demo_reply_delay_seconds: float = Field(default=5, ge=0, le=60)
    advisor_send_timeout_seconds: float = Field(default=15, gt=0, le=60)
    log_level: str = "INFO"
    gemini_api_key: str | None = None
    google_api_key: str | None = None
    google_genai_use_vertexai: bool = False
    google_genai_use_enterprise: bool = False
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    livekit_agent_name: str = "wealth-copilot"
    livekit_stt_model: str = "deepgram/nova-3"
    livekit_stt_language: str = "en-IN"
    livekit_tts_model: str = "inworld/inworld-tts-2"
    livekit_tts_voice: str = "Ashley"

    @property
    def vertex_ai_enabled(self) -> bool:
        """Normalize the canonical Vertex flag and the SDK compatibility alias."""

        return self.google_genai_use_vertexai or self.google_genai_use_enterprise

    @field_validator("portfolio_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return "simulated" if normalized == "demo" else normalized
        return value

    @field_validator("news_provider", mode="before")
    @classmethod
    def normalize_news_provider(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return "simulated" if normalized == "demo" else normalized
        return value

    @field_validator("market_data_provider", mode="before")
    @classmethod
    def normalize_market_data_provider(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return "demo" if normalized == "simulated" else normalized
        return value

    @field_validator("simulation_mode", mode="before")
    @classmethod
    def normalize_simulation_mode(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("advisor_provider", mode="before")
    @classmethod
    def normalize_advisor_provider(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()


def application_now() -> datetime:
    """Return the application clock in the configured financial timezone."""

    settings = get_settings()
    return datetime.now(ZoneInfo(settings.day_schedule_timezone))


def application_today() -> date:
    """Key normal financial-day state from the configured wall clock.

    Demo scenarios may contain historical market timestamps, but they do not
    own the normal product clock. Explicit demo/presentation operations pass
    their selected trading date through the orchestrator.
    """

    return application_now().date()
