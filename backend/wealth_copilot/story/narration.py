"""Per-scene Gemini TTS so visuals advance on real audio boundaries."""

import asyncio
from io import BytesIO
import json
import logging
from pathlib import Path
import re
from threading import RLock
import wave

from ..config import get_settings
from ..media.provider import gemini_tts_provider
from .schemas import (
    DailyWealthStory,
    StoryNarration,
    StoryNarrationStatus,
    StoryScene,
    StorySceneNarration,
)


logger = logging.getLogger(__name__)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def _scene_text(scene: StoryScene) -> str:
    values = [scene.eyebrow, scene.title, scene.primary_value, scene.secondary_text, scene.detail]
    return ". ".join(value.strip().rstrip(".") for value in values if value and value.strip()) + "."


class StoryNarrationService:
    def __init__(self, provider=None, root: Path | None = None) -> None:
        self._provider = provider or gemini_tts_provider
        self._root = root or Path(get_settings().audio_cache_dir) / "story-scenes"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._items: dict[str, StoryNarration] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _directory(self, story_id: str) -> Path:
        if not _SAFE_ID.fullmatch(story_id) or story_id in {".", ".."}:
            raise ValueError("Invalid story identifier")
        return self._root / story_id

    def _metadata(self, story_id: str) -> Path:
        return self._directory(story_id) / "narration.json"

    def _persist(self, narration: StoryNarration) -> None:
        directory = self._directory(narration.story_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = self._metadata(narration.story_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(narration.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def _load(self, story_id: str) -> StoryNarration | None:
        path = self._metadata(story_id)
        if not path.exists():
            return None
        try:
            return StoryNarration.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def prepare(self, story: DailyWealthStory) -> StoryNarration:
        with self._lock:
            existing = self._items.get(story.story_id) or self._load(story.story_id)
            if existing:
                self._items[story.story_id] = existing
                return existing.model_copy(deep=True)
            narration = StoryNarration(
                story_id=story.story_id,
                day_id=story.day_id,
                run_id=story.run_id,
                status=StoryNarrationStatus.QUEUED,
                scenes=[
                    StorySceneNarration(
                        scene_id=scene.scene_id,
                        text=_scene_text(scene),
                        status=StoryNarrationStatus.QUEUED,
                    )
                    for scene in story.scenes
                ],
                message="Preparing narration for each moment.",
            )
            self._items[story.story_id] = narration
            self._persist(narration)
            return narration.model_copy(deep=True)

    def start(self, story: DailyWealthStory) -> StoryNarration:
        narration = self.prepare(story)
        with self._lock:
            running = self._tasks.get(story.story_id)
            if narration.status == StoryNarrationStatus.READY or (running and not running.done()):
                return narration
            self._tasks[story.story_id] = asyncio.create_task(self._generate(story.story_id))
            return narration

    async def clear(self) -> None:
        """Cancel in-flight narration and discard the process-local index."""

        with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
            self._items.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _generate(self, story_id: str) -> None:
        with self._lock:
            narration = self._items[story_id]
            narration.status = StoryNarrationStatus.GENERATING
            narration.message = "Preparing synchronized narration."
            self._persist(narration)
        try:
            for index in range(len(narration.scenes)):
                with self._lock:
                    scene = self._items[story_id].scenes[index]
                    scene.status = StoryNarrationStatus.GENERATING
                    script = scene.text
                    scene_id = scene.scene_id
                    self._persist(self._items[story_id])
                wav_bytes = await self._provider.synthesize(script)
                with wave.open(BytesIO(wav_bytes), "rb") as audio:
                    if audio.getnchannels() != 1 or audio.getframerate() != 24000:
                        raise ValueError("Unexpected audio format")
                    duration = audio.getnframes() / audio.getframerate()
                audio_path = self._directory(story_id) / f"{scene_id}.wav"
                temporary = audio_path.with_suffix(".tmp")
                temporary.write_bytes(wav_bytes)
                temporary.replace(audio_path)
                with self._lock:
                    scene = self._items[story_id].scenes[index]
                    scene.status = StoryNarrationStatus.READY
                    scene.actual_duration_seconds = round(duration + 0.25, 2)
                    scene.audio_url = f"/api/v1/story/{story_id}/narration/{scene_id}/file"
                    self._persist(self._items[story_id])
            with self._lock:
                narration = self._items[story_id]
                narration.status = StoryNarrationStatus.READY
                narration.total_duration_seconds = round(
                    sum(scene.actual_duration_seconds or 0 for scene in narration.scenes), 2
                )
                narration.message = "Narration and visuals are synchronized."
                self._persist(narration)
        except Exception:
            logger.exception("Story narration failed for %s", story_id)
            with self._lock:
                narration = self._items[story_id]
                narration.status = StoryNarrationStatus.FALLBACK
                narration.message = "Narration is unavailable; the visual recap is still ready."
                for scene in narration.scenes:
                    if scene.status != StoryNarrationStatus.READY:
                        scene.status = StoryNarrationStatus.FALLBACK
                self._persist(narration)

    def get(self, story_id: str) -> StoryNarration | None:
        if not _SAFE_ID.fullmatch(story_id) or story_id in {".", ".."}:
            return None
        with self._lock:
            item = self._items.get(story_id) or self._load(story_id)
            if item:
                self._items[story_id] = item
            return item.model_copy(deep=True) if item else None

    def audio_path(self, story_id: str, scene_id: str) -> Path | None:
        narration = self.get(story_id)
        if narration is None:
            return None
        scene = next((item for item in narration.scenes if item.scene_id == scene_id), None)
        if scene is None or scene.status != StoryNarrationStatus.READY:
            return None
        path = self._directory(story_id) / f"{scene_id}.wav"
        return path if path.exists() else None


story_narration_service = StoryNarrationService()
