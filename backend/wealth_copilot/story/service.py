"""Cached orchestration for Daily Wealth Stories."""

from datetime import date, datetime, timezone

from ..config import application_today
from ..day.store import FinancialDayStore, financial_day_store
from ..day.integrity import checkpoint_released
from ..media.schemas import AudioBriefType
from ..media.service import media_service
from .builder import daily_story_builder, source_signature
from .schemas import DailyWealthStory


class DailyStoryService:
    def __init__(self, store: FinancialDayStore | None = None) -> None:
        self.store = store or financial_day_store

    async def prepare(self, trading_date: date | None = None) -> DailyWealthStory:
        selected = trading_date or application_today()
        state = self.store.get(selected)
        if state.run_mode == "presentation" and not checkpoint_released(state, "21:01"):
            raise ValueError("Daily Wealth Story is available after the financial day is complete")
        signature = source_signature(state)
        if state.daily_story and state.daily_story.source_signature == signature:
            cached = state.daily_story.model_copy(deep=True)
            cached.cached = True
            timeline_story = next(
                (item for item in state.timeline if item.step_id == "story"), None
            )
            if timeline_story and timeline_story.status.value != "complete":
                self._persist(selected, state.daily_story)
            return cached
        story = daily_story_builder.build(state)
        audio = await media_service.prepare(AudioBriefType.STORY, state)
        story.audio_brief_id = audio.brief_id
        self._persist(selected, story)
        return story.model_copy(deep=True)

    def _persist(self, selected: date, story: DailyWealthStory) -> None:
        def mutate(state) -> None:
            state.daily_story = story
            state.story_audio_brief_id = story.audio_brief_id
            step = next((item for item in state.timeline if item.step_id == "story"), None)
            if step:
                now = datetime.now(timezone.utc)
                from ..day.schemas import StepStatus

                step.status = StepStatus.COMPLETE
                step.started_at = step.started_at or now
                step.completed_at = now
                step.detail = (
                    f"{len(story.scenes)} deterministic scenes · "
                    f"{story.duration_seconds} sec recap ready."
                )
                step.linked_ids = [
                    story.story_id,
                    *([story.audio_brief_id] if story.audio_brief_id else []),
                ]

        self.store.update(mutate, selected)


daily_story_service = DailyStoryService()
