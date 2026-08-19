"""Thin presentation specialist for deterministic scripts and Gemini TTS."""

from typing import Any

from google.adk.agents import Agent
from google.genai import types

from ..config import get_settings
from ..media.schemas import AudioBriefType
from ..media.service import media_service


settings = get_settings()


async def create_morning_script() -> dict[str, Any]:
    """Build today's Morning Pulse from retained dashboard intelligence."""

    brief = await media_service.prepare(AudioBriefType.MORNING)
    return {"status": "ok", "data": brief.model_dump(mode="json")}


async def create_evening_script() -> dict[str, Any]:
    """Build today's Evening Wrap, including saved-for-evening state."""

    brief = await media_service.prepare(AudioBriefType.EVENING)
    return {"status": "ok", "data": brief.model_dump(mode="json")}


async def generate_audio(brief_type: str) -> dict[str, Any]:
    """Queue cached single-speaker audio for morning or evening."""

    result = await media_service.start(AudioBriefType(brief_type.lower()))
    return {"status": "accepted" if result.accepted else "cached", "data": result.model_dump(mode="json")}


def get_audio_status(brief_id: str) -> dict[str, Any]:
    """Return generation status and text fallback for an audio brief."""

    brief = media_service.get(brief_id)
    if brief is None:
        return {"status": "error", "error": "Unknown audio brief"}
    return {"status": "ok", "data": brief.model_dump(mode="json")}


media_agent = Agent(
    name="media_agent",
    model=settings.adk_model,
    description="Creates morning/evening scripts and cached audio from existing Wealth Copilot intelligence.",
    instruction=(
        "You are Wealth Copilot's Media Agent. You are a presentation specialist, not a financial reasoning "
        "agent. For a Morning Pulse call create_morning_script. For an Evening Wealth Wrap call "
        "create_evening_script. Only call generate_audio when the user explicitly asks to create or listen to "
        "audio. Use get_audio_status for status checks. Return tool data faithfully. Never add conclusions, "
        "change rankings, invent market facts, or give investment instructions."
    ),
    tools=[
        create_morning_script,
        create_evening_script,
        generate_audio,
        get_audio_status,
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0),
)

