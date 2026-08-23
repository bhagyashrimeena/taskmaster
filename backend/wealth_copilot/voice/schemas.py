"""Credential-safe contracts for starting a Copilot voice room."""

from pydantic import BaseModel, ConfigDict


class VoiceModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class VoiceSessionRequest(VoiceModel):
    conversation_id: str | None = None
    current_case_id: str | None = None


class VoiceSessionResponse(VoiceModel):
    enabled: bool
    reason: str | None = None
    livekit_url: str | None = None
    token: str | None = None
    room_name: str | None = None
    participant_name: str | None = None
    conversation_id: str | None = None
