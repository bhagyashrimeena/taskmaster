import asyncio
from io import BytesIO
from pathlib import Path
import re
from types import SimpleNamespace
import wave

import pytest
from fastapi.testclient import TestClient
from google.adk.tools.agent_tool import AgentTool

from wealth_copilot.agents.media_agent import media_agent
from wealth_copilot.agents.taskmaster import root_agent
from wealth_copilot.api import app
from wealth_copilot.interaction.memory import daily_interaction_store
from wealth_copilot.media.provider import pcm_to_wav
from wealth_copilot.media import provider as media_provider
from wealth_copilot.media.schemas import AudioBriefType, AudioStatus
from wealth_copilot.media.script_builder import audio_script_builder
from wealth_copilot.media.service import MediaService
from wealth_copilot.dashboard.service import dashboard_service
from wealth_copilot.day.schemas import DayRunMode
from wealth_copilot.day.store import financial_day_store
from wealth_copilot.market.cache import news_candidate_cache
from wealth_copilot.interaction.schemas import ConversationRequest
from wealth_copilot.interaction.service import InteractionService


class FakeAudioProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def synthesize(self, script: str) -> bytes:
        self.calls += 1
        assert len(script.split()) >= 105
        if self.fail:
            raise RuntimeError("tts unavailable")
        # Two seconds of quiet 24 kHz mono PCM is sufficient to validate WAV handling.
        return pcm_to_wav(b"\x00\x00" * 48000)


def test_gemini_tts_prefers_developer_api_key(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(media_provider.genai, "Client", lambda **kwargs: captured.update(kwargs) or object())

    media_provider._create_client(SimpleNamespace(
        google_api_key="test-key",
        google_genai_use_enterprise=False,
        google_cloud_project=None,
        google_cloud_location="global",
    ))

    assert captured == {"api_key": "test-key"}


def test_gemini_tts_prefers_gemini_key_alias(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(media_provider.genai, "Client", lambda **kwargs: captured.update(kwargs) or object())

    media_provider._create_client(SimpleNamespace(
        gemini_api_key="gemini-key",
        google_api_key="legacy-key",
        google_genai_use_enterprise=False,
        google_cloud_project=None,
        google_cloud_location="global",
    ))

    assert captured == {"api_key": "gemini-key"}


def test_gemini_tts_vertex_mode_requires_project() -> None:
    with pytest.raises(media_provider.GeminiTtsConfigurationError, match="GOOGLE_CLOUD_PROJECT"):
        media_provider._create_client(SimpleNamespace(
            google_api_key=None,
            google_genai_use_enterprise=True,
            google_cloud_project=None,
            google_cloud_location="global",
        ))


def test_gemini_tts_uses_vertex_only_when_configured(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(media_provider.genai, "Client", lambda **kwargs: captured.update(kwargs) or object())

    media_provider._create_client(SimpleNamespace(
        google_api_key=None,
        google_genai_use_enterprise=True,
        google_cloud_project="wealth-project",
        google_cloud_location="asia-south1",
    ))

    assert captured == {
        "vertexai": True,
        "project": "wealth-project",
        "location": "asia-south1",
    }


def test_gemini_tts_vertex_flag_alias_uses_adc_path(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(media_provider.genai, "Client", lambda **kwargs: captured.update(kwargs) or object())

    media_provider._create_client(SimpleNamespace(
        google_api_key="optional-fallback-key",
        google_genai_use_vertexai=True,
        google_genai_use_enterprise=False,
        google_cloud_project="wealth-project",
        google_cloud_location="global",
    ))

    assert captured == {
        "vertexai": True,
        "project": "wealth-project",
        "location": "global",
    }


def test_media_ids_cannot_escape_audio_cache(tmp_path: Path) -> None:
    service = MediaService(cache_dir=tmp_path)

    assert service.get("..\\outside") is None
    assert service.audio_path("..\\outside") is None


async def _finish(service: MediaService, brief_id: str) -> None:
    for _ in range(100):
        current = service.get(brief_id)
        if current and current.status in {AudioStatus.READY, AudioStatus.FALLBACK}:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("audio generation did not finish")


async def test_morning_script_uses_existing_intelligence_and_is_safe(tmp_path: Path) -> None:
    financial_day_store.update(
        lambda state: setattr(state, "run_mode", DayRunMode.DEMO)
    )
    from wealth_copilot.simulation import simulation_service
    simulation_service.advance_to("12:17")
    brief = await MediaService(FakeAudioProvider(), tmp_path).prepare(AudioBriefType.MORNING)

    assert 60 <= brief.estimated_duration_seconds <= 90
    assert len(brief.used_stories) == 3
    assert brief.used_events == ["hdfc-bank-sudden-fall"]
    assert brief.source_snapshot_at
    assert brief.fallback_text == brief.script
    assert re.search(r"\b(buy|sell|hold|rebalance)\b", brief.script, re.I) is None


async def test_evening_script_includes_saved_story_state(tmp_path: Path) -> None:
    daily_interaction_store.clear()
    for story_id in ("hdfc-rbi", "infy-results", "reliance-action", "itc-tax", "tcs-deal"):
        daily_interaction_store.save_story(story_id)

    brief = await MediaService(FakeAudioProvider(), tmp_path).prepare(AudioBriefType.EVENING)

    assert "hdfc-rbi" in brief.used_stories
    assert len(brief.used_stories) == 2
    assert "You saved 5 items" in brief.script
    assert len(brief.script.split()) <= 190
    assert 60 <= brief.estimated_duration_seconds <= 90


async def test_audio_generation_is_cached_and_not_duplicated(tmp_path: Path) -> None:
    provider = FakeAudioProvider()
    service = MediaService(provider, tmp_path)

    first = await service.start(AudioBriefType.MORNING)
    duplicate = await service.start(AudioBriefType.MORNING)
    await _finish(service, first.brief.brief_id)
    ready = service.get(first.brief.brief_id)
    cached = await service.start(AudioBriefType.MORNING)

    assert first.accepted is True
    assert duplicate.accepted is False
    assert cached.accepted is False
    assert provider.calls == 1
    assert ready is not None and ready.status == AudioStatus.READY
    assert ready.cached is True
    assert ready.actual_duration_seconds == 2.0
    assert service.audio_path(ready.brief_id).exists()


async def test_unchanged_intelligence_reuses_audio_across_freshness_timestamp(tmp_path: Path) -> None:
    service = MediaService(FakeAudioProvider(), tmp_path)
    news_candidate_cache.clear()
    first = await service.prepare(AudioBriefType.MORNING)
    news_candidate_cache.clear()
    second = await service.prepare(AudioBriefType.MORNING)

    assert second.brief_id == first.brief_id


async def test_tts_failure_keeps_complete_text_fallback(tmp_path: Path) -> None:
    service = MediaService(FakeAudioProvider(fail=True), tmp_path)
    started = await service.start(AudioBriefType.MORNING)
    await _finish(service, started.brief.brief_id)
    failed = service.get(started.brief.brief_id)

    assert failed is not None and failed.status == AudioStatus.FALLBACK
    assert failed.audio_url is None
    assert failed.fallback_text == failed.script


async def test_interrupted_generation_recovers_to_text_ready(tmp_path: Path) -> None:
    first_service = MediaService(FakeAudioProvider(), tmp_path)
    brief = await first_service.prepare(AudioBriefType.MORNING)
    brief.status = AudioStatus.GENERATING
    metadata = tmp_path / f"{brief.brief_id}.json"
    metadata.write_text(brief.model_dump_json(), encoding="utf-8")

    recovered = await MediaService(FakeAudioProvider(), tmp_path).prepare(
        AudioBriefType.MORNING
    )
    assert recovered.status == AudioStatus.TEXT_READY
    assert recovered.audio_url is None


def test_pcm_wrapper_produces_browser_playable_wav() -> None:
    payload = pcm_to_wav(b"\x00\x00" * 24000)
    with wave.open(BytesIO(payload), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 24000
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == 24000


def test_media_agent_is_a_taskmaster_specialist() -> None:
    specialists = {
        tool.agent.name for tool in root_agent.tools if isinstance(tool, AgentTool)
    }
    assert media_agent.name in specialists


async def test_audio_conversation_routes_to_media_agent() -> None:
    async def fake_taskmaster(prompt: str, timeout: float):
        assert "EXPECTED_ROUTE: media_agent" in prompt
        assert timeout >= 45
        return "Your Morning Pulse script is ready.", ["TaskMaster completed"]

    result = await InteractionService(fake_taskmaster).respond(
        ConversationRequest(message="Create my Morning Pulse")
    )
    assert result.route == "media_agent"


def test_audio_text_endpoint_does_not_generate_tts() -> None:
    response = TestClient(app).get("/api/v1/audio/morning")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "morning"
    assert payload["status"] in {"text_ready", "ready"}
    assert payload["fallback_text"]


async def test_audio_scripts_support_a_quiet_day_without_an_alert() -> None:
    dashboard = (await dashboard_service.get_dashboard()).model_copy(
        update={"important_event": None}
    )

    morning_sections, morning_script, _, morning_events = audio_script_builder.morning(
        dashboard
    )
    evening_sections, evening_script, _, evening_events = audio_script_builder.evening(
        dashboard,
        daily_interaction_store.get(),
    )

    assert morning_sections and evening_sections
    assert "No material event currently needs your attention" in morning_script
    assert "No material event currently needs your attention" in evening_script
    assert morning_events == []
    assert evening_events == []
