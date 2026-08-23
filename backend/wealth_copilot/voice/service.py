"""LiveKit token creation for the same TaskMaster-backed Copilot context."""

from datetime import timedelta
import json
from uuid import uuid4

from livekit import api

from ..config import get_settings
from ..day.store import financial_day_store
from .schemas import VoiceSessionRequest, VoiceSessionResponse


class VoiceSessionService:
    @staticmethod
    def configured() -> bool:
        settings = get_settings()
        return all(
            (settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
        )

    def create(self, request: VoiceSessionRequest) -> VoiceSessionResponse:
        settings = get_settings()
        conversation_id = request.conversation_id or uuid4().hex
        if not self.configured():
            return VoiceSessionResponse(
                enabled=False,
                reason="Live call is not configured yet.",
                conversation_id=request.conversation_id,
            )

        day = financial_day_store.get()
        suffix = uuid4().hex[:10]
        room_name = f"wealth-copilot-{day.trading_date.isoformat()}-{suffix}"
        participant_name = f"wealth-user-{suffix}"
        metadata = json.dumps(
            {
                "conversation_id": conversation_id,
                "day_id": day.day_id,
                "run_id": day.run_id,
                "current_case_id": request.current_case_id,
                "copilot_path": "/api/v1/copilot",
            },
            separators=(",", ":"),
        )
        room_config = api.RoomConfiguration(
            agents=[
                api.RoomAgentDispatch(
                    agent_name=settings.livekit_agent_name,
                    metadata=metadata,
                )
            ]
        )
        token = (
            api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(participant_name)
            .with_name("Wealth Copilot user")
            .with_metadata(metadata)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .with_room_config(room_config)
            .with_ttl(timedelta(minutes=15))
            .to_jwt()
        )
        return VoiceSessionResponse(
            enabled=True,
            livekit_url=settings.livekit_url,
            token=token,
            room_name=room_name,
            participant_name=participant_name,
            conversation_id=conversation_id,
        )


voice_session_service = VoiceSessionService()
