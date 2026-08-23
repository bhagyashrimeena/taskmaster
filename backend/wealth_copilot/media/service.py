"""Cached, non-blocking audio briefing orchestration."""

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
from threading import RLock
from typing import Protocol
import wave
from io import BytesIO

from ..config import get_settings
from ..interaction.memory import daily_interaction_store
from .provider import GeminiTtsConfigurationError, gemini_tts_provider
from .schemas import (
    AudioBrief,
    AudioBriefType,
    AudioGenerationResponse,
    AudioStatus,
)
from .script_builder import audio_script_builder, validate_script, validate_story_script
from ..day.active import ArtifactProvenance


settings = get_settings()
logger = logging.getLogger(__name__)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class AudioProvider(Protocol):
    async def synthesize(self, script: str) -> bytes: ...


class MediaService:
    """Builds approved scripts immediately and synthesizes WAV in the background."""

    def __init__(
        self, provider: AudioProvider | None = None, cache_dir: Path | None = None
    ) -> None:
        self._provider = provider or gemini_tts_provider
        self._cache_dir = cache_dir or Path(settings.audio_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._briefs: dict[str, AudioBrief] = {}
        self._latest: dict[AudioBriefType, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _paths(self, brief_id: str) -> tuple[Path, Path]:
        if not _SAFE_ID.fullmatch(brief_id) or brief_id in {".", ".."}:
            raise ValueError("Invalid audio brief identifier")
        return (
            self._cache_dir / f"{brief_id}.json",
            self._cache_dir / f"{brief_id}.wav",
        )

    def _persist_metadata(self, brief: AudioBrief) -> None:
        metadata_path, _ = self._paths(brief.brief_id)
        temporary = metadata_path.with_suffix(".json.tmp")
        temporary.write_text(brief.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(metadata_path)

    def _load_cached(self, brief_id: str) -> AudioBrief | None:
        metadata_path, audio_path = self._paths(brief_id)
        if not metadata_path.exists():
            return None
        try:
            brief = AudioBrief.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if audio_path.exists():
            brief.status = AudioStatus.READY
            brief.audio_url = f"/api/v1/audio/{brief_id}/file"
            brief.cached = True
            brief.message = "Audio is ready."
        elif brief.status in {
            AudioStatus.READY,
            AudioStatus.QUEUED,
            AudioStatus.GENERATING,
        }:
            brief.status = AudioStatus.TEXT_READY
            brief.audio_url = None
            brief.cached = False
        return brief

    async def prepare(self, brief_type: AudioBriefType, financial_day=None) -> AudioBrief:
        from ..day.store import financial_day_store

        supplied_financial_day = financial_day
        financial_day = supplied_financial_day or financial_day_store.get()
        if brief_type == AudioBriefType.MORNING and financial_day.morning_brief_id:
            existing = self.get(financial_day.morning_brief_id)
            if existing and existing.run_id == financial_day.run_id:
                return existing
        if brief_type == AudioBriefType.STORY:
            sections, script, stories, events = audio_script_builder.story(financial_day)
            title, duration = "Your Financial Day", 24
            source_snapshot_at = financial_day.updated_at
            data_freshness = "financial_day"
            validate_story_script(script)
        else:
            # Lazy import keeps short story generation independent of dashboard/Search.
            from ..dashboard.service import dashboard_service

            dashboard = await dashboard_service.get_dashboard()
            daily_state = daily_interaction_store.get()
            source_snapshot_at = dashboard.daily_brief.freshness.fetched_at
            data_freshness = dashboard.daily_brief.freshness.status.value
        if brief_type == AudioBriefType.MORNING:
            sections, script, stories, events = audio_script_builder.morning(dashboard)
            title, duration = "Morning Pulse", 75
            validate_script(script)
        elif brief_type == AudioBriefType.EVENING:
            sections, script, stories, events = audio_script_builder.evening(
                dashboard, daily_state, financial_day
            )
            title, duration = "Evening Wealth Wrap", 90
            validate_script(script)
        identity = json.dumps(
            {
                "type": brief_type.value,
                "day_id": financial_day.day_id,
                "run_id": financial_day.run_id,
                "stories": stories,
                "events": events,
                "script": script,
            },
            sort_keys=True,
        )
        brief_id = f"{brief_type.value}-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"
        with self._lock:
            existing = self._briefs.get(brief_id) or self._load_cached(brief_id)
            if existing:
                self._briefs[brief_id] = existing
                self._latest[brief_type] = brief_id
                return existing.model_copy(deep=True)
            words = len(script.split())
            brief = AudioBrief(
                brief_id=brief_id,
                day_id=financial_day.day_id,
                run_id=financial_day.run_id,
                type=brief_type,
                title=title,
                generated_at=datetime.now(timezone.utc),
                source_snapshot_at=source_snapshot_at,
                sections=sections,
                script=script,
                duration_target_seconds=duration,
                estimated_duration_seconds=round(words / 2.3),
                voice=settings.tts_voice,
                model=settings.tts_model,
                status=AudioStatus.TEXT_READY,
                fallback_text=script,
                data_freshness=data_freshness,
                used_stories=stories,
                used_events=events,
                cached=False,
                message="Text brief is ready. Audio can be generated in the background.",
                provenance=ArtifactProvenance(
                    day_id=financial_day.day_id,
                    run_id=financial_day.run_id,
                    source_checkpoint="07:00" if brief_type == AudioBriefType.MORNING else "20:00" if brief_type == AudioBriefType.EVENING else "21:01",
                    source_snapshot_id=(
                        financial_day.morning_brief_id
                        if brief_type == AudioBriefType.MORNING and financial_day.morning_brief_id
                        else f"{financial_day.run_id}:{brief_type.value}:{source_snapshot_at.isoformat()}"
                    ),
                    generated_at=datetime.now(timezone.utc),
                ),
            )
            self._briefs[brief_id] = brief
            self._latest[brief_type] = brief_id
            self._persist_metadata(brief)
            field = {
                AudioBriefType.MORNING: "morning_brief_id",
                AudioBriefType.EVENING: "evening_brief_id",
                AudioBriefType.STORY: "story_audio_brief_id",
            }[brief_type]
            if supplied_financial_day is None:
                financial_day_store.update(lambda state: setattr(state, field, brief.brief_id))
            return brief.model_copy(deep=True)

    async def start(self, brief_type: AudioBriefType) -> AudioGenerationResponse:
        brief = await self.prepare(brief_type)
        with self._lock:
            current = self._briefs[brief.brief_id]
            running = self._tasks.get(brief.brief_id)
            if current.status == AudioStatus.READY:
                return AudioGenerationResponse(
                    brief=current.model_copy(deep=True), accepted=False
                )
            if running and not running.done():
                return AudioGenerationResponse(
                    brief=current.model_copy(deep=True), accepted=False
                )
            current.status = AudioStatus.QUEUED
            current.message = "Gemini TTS is preparing your audio brief."
            self._persist_metadata(current)
            task = asyncio.create_task(self._generate(current.brief_id))
            self._tasks[current.brief_id] = task
            return AudioGenerationResponse(
                brief=current.model_copy(deep=True), accepted=True
            )

    async def clear(self) -> None:
        """Cancel in-flight synthesis and discard the process-local index."""

        with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
            self._briefs.clear()
            self._latest.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _generate(self, brief_id: str) -> None:
        with self._lock:
            brief = self._briefs[brief_id]
            brief.status = AudioStatus.GENERATING
            brief.message = "Generating a calm single-speaker briefing."
            self._persist_metadata(brief)
            script = brief.script
        try:
            wav_bytes = await self._provider.synthesize(script)
            with wave.open(BytesIO(wav_bytes), "rb") as audio:
                if audio.getnchannels() != 1 or audio.getframerate() != 24000:
                    raise ValueError("Unexpected audio format")
                duration = audio.getnframes() / audio.getframerate()
            _, audio_path = self._paths(brief_id)
            temporary = audio_path.with_suffix(".tmp")
            temporary.write_bytes(wav_bytes)
            temporary.replace(audio_path)
            with self._lock:
                brief = self._briefs[brief_id]
                brief.status = AudioStatus.READY
                brief.actual_duration_seconds = round(duration, 2)
                brief.audio_url = f"/api/v1/audio/{brief_id}/file"
                brief.cached = True
                brief.message = "Audio brief is ready."
                self._persist_metadata(brief)
        except Exception as exc:
            logger.exception("Audio synthesis failed for %s", brief_id)
            with self._lock:
                brief = self._briefs[brief_id]
                brief.status = AudioStatus.FALLBACK
                brief.audio_url = None
                brief.cached = False
                brief.message = (
                    "Gemini TTS is not configured. Add GEMINI_API_KEY or configure Vertex AI, then retry."
                    if isinstance(exc, GeminiTtsConfigurationError)
                    else "Gemini TTS could not generate this audio. Check the backend logs, then retry."
                )
                self._persist_metadata(brief)

    def get(self, brief_id: str) -> AudioBrief | None:
        if not _SAFE_ID.fullmatch(brief_id) or brief_id in {".", ".."}:
            return None
        with self._lock:
            brief = self._briefs.get(brief_id) or self._load_cached(brief_id)
            if brief:
                self._briefs[brief_id] = brief
            return brief.model_copy(deep=True) if brief else None

    def audio_path(self, brief_id: str) -> Path | None:
        brief = self.get(brief_id)
        if not brief or brief.status != AudioStatus.READY:
            return None
        _, path = self._paths(brief_id)
        return path if path.exists() else None


media_service = MediaService()
