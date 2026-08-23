"""Voice calling stays config-gated and shares the canonical Copilot context."""

import jwt
from fastapi.testclient import TestClient

from wealth_copilot.api import app
from wealth_copilot.config import get_settings
from wealth_copilot.voice import VoiceSessionRequest, voice_session_service


def _clear_livekit(monkeypatch) -> None:
    for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()


def test_voice_session_endpoint_is_truthfully_disabled_without_livekit(monkeypatch) -> None:
    _clear_livekit(monkeypatch)

    response = TestClient(app).post(
        "/api/v1/copilot/voice/session",
        json={"conversation_id": "conversation-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "reason": "Live call is not configured yet.",
        "livekit_url": None,
        "token": None,
        "room_name": None,
        "participant_name": None,
        "conversation_id": "conversation-1",
    }
    get_settings.cache_clear()


def test_configured_voice_session_returns_short_lived_token_without_secret(
    monkeypatch,
) -> None:
    secret = "server-only-secret-that-must-never-reach-the-browser"
    monkeypatch.setenv("LIVEKIT_URL", "wss://wealth-copilot.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "wealth-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", secret)
    monkeypatch.setenv("LIVEKIT_AGENT_NAME", "wealth-copilot")
    get_settings.cache_clear()

    session = voice_session_service.create(
        VoiceSessionRequest(conversation_id="conversation-2", current_case_id="case-1")
    )
    payload = jwt.decode(session.token, options={"verify_signature": False})
    serialized = session.model_dump_json()

    assert session.enabled is True
    assert session.conversation_id == "conversation-2"
    assert session.livekit_url == "wss://wealth-copilot.livekit.cloud"
    assert session.room_name in payload["video"]["room"]
    assert payload["sub"] == session.participant_name
    assert secret not in serialized
    assert "LIVEKIT_API_SECRET" not in serialized
    get_settings.cache_clear()


def test_configured_voice_session_creates_conversation_for_a_new_call(monkeypatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://wealth-copilot.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "wealth-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "server-only-secret")
    get_settings.cache_clear()

    session = voice_session_service.create(VoiceSessionRequest())

    assert session.enabled is True
    assert session.conversation_id
    get_settings.cache_clear()
