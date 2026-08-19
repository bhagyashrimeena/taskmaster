"""Compose accurate visual scenes exclusively from FinancialDayState."""

from datetime import datetime
import hashlib
import json
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .schemas import (
    DailyWealthStory,
    StoryAdvisorInteraction,
    StoryContributor,
    StoryEvent,
    StoryScene,
    StorySceneKind,
    StoryTomorrowEvent,
)
from ..day.active import ArtifactProvenance

if TYPE_CHECKING:
    from ..day.schemas import FinancialDayState


_DISPLAY_NAMES = {
    "HDFCBANK": "HDFC Bank",
    "RELIANCE": "Reliance",
    "INFY": "Infosys",
    "TCS": "TCS",
    "ICICIBANK": "ICICI Bank",
    "BHARTIARTL": "Bharti Airtel",
}


def _compact_inr(value: float) -> str:
    if value >= 10_000_000:
        return f"₹{value / 10_000_000:.2f}Cr"
    if value >= 100_000:
        return f"₹{value / 100_000:.2f}L"
    return f"₹{value:,.0f}"


def _signed(value: float) -> str:
    arrow = "↑" if value > 0 else "↓" if value < 0 else "→"
    return f"{arrow} {abs(value):.2f}%"


def _trim(value: str, limit: int = 120) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _signature(state: "FinancialDayState") -> str:
    review = state.market_close_review
    payload = {
        "story_schema_version": 1,
        "day_id": state.day_id,
        "run_id": state.run_id,
        "date": state.trading_date.isoformat(),
        "open": state.portfolio_open_snapshot.portfolio_value if state.portfolio_open_snapshot else None,
        "close": state.portfolio_close_snapshot.portfolio_value if state.portfolio_close_snapshot else None,
        "return": review.portfolio_return_pct if review else None,
        "positive": [item.model_dump(mode="json") for item in review.top_positive_contributors] if review else [],
        "negative": [item.model_dump(mode="json") for item in review.top_negative_contributors] if review else [],
        "alerts": [item.model_dump(mode="json") for item in state.events_alerted],
        "saved": [*state.saved_stories, *state.saved_events],
        "advisor_requests": [item.model_dump(mode="json") for item in state.advisor_requests],
        "advisor_responses": [item.model_dump(mode="json") for item in state.advisor_responses],
        "tomorrow": [item.model_dump(mode="json") for item in state.tomorrow_events],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()[:20]


def source_signature(state: "FinancialDayState") -> str:
    return _signature(state)


def _durations(count: int, target: int = 24) -> list[int]:
    base, remainder = divmod(target, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


class DailyStoryBuilder:
    """Select and verbalize day-state fields without adding financial reasoning."""

    def build(self, state: "FinancialDayState") -> DailyWealthStory:
        if state.portfolio_close_snapshot is None or state.market_close_review is None:
            raise ValueError("The Daily Wealth Story is available after Market Close Review")

        review = state.market_close_review
        positives = [StoryContributor.model_validate(item.model_dump()) for item in review.top_positive_contributors]
        negatives = [StoryContributor.model_validate(item.model_dump()) for item in review.top_negative_contributors]
        alert = state.events_alerted[0] if state.events_alerted else None
        event = None
        if alert:
            event = StoryEvent(
                event_id=alert.event.event_id,
                company=alert.event.company or alert.event.symbol or "Portfolio holding",
                price_change_pct=float(alert.event.price_change_pct or 0),
                sector_change_pct=float(alert.event.sector_change_pct or 0),
                exposure_pct=alert.affected_portfolio_percentage,
                relevance_score=alert.relevance_score,
                alert_time=alert.event.timestamp,
            )

        advisor = None
        if state.advisor_requests:
            request = next(
                (item for item in reversed(state.advisor_requests) if item.response_id),
                state.advisor_requests[-1],
            )
            response = next(
                (item for item in state.advisor_responses if item.request_id == request.request_id),
                None,
            )
            advisor = StoryAdvisorInteraction(
                request_id=request.request_id,
                question=request.user_question,
                response_id=response.response_id if response else None,
                response_summary=_trim(response.message) if response else None,
                advisor_name=response.advisor_name if response else None,
            )

        tomorrow = [
            StoryTomorrowEvent(
                event_id=item.event_id,
                title=item.title,
                scheduled_at=item.scheduled_at,
                portfolio_exposure_pct=item.portfolio_exposure_pct,
            )
            for item in state.tomorrow_events
        ]
        saved = [*state.saved_stories, *state.saved_events]
        scene_values: list[dict] = []
        scene_values.append(
            dict(
                kind=StorySceneKind.SUMMARY,
                eyebrow="Your financial day",
                title="Portfolio at close",
                primary_value=_compact_inr(state.portfolio_close_snapshot.portfolio_value),
                secondary_text=_signed(review.portfolio_return_pct),
                detail="A recap of what shaped your portfolio today.",
            )
        )
        driver = negatives[0] if negatives else positives[0] if positives else None
        if driver:
            direction = "negative" if driver.direction == "negative" else "positive"
            scene_values.append(
                dict(
                    kind=StorySceneKind.DRIVER,
                    eyebrow="Biggest driver",
                    title=_DISPLAY_NAMES.get(driver.symbol, driver.symbol),
                    primary_value=f"{driver.daily_return_pct:+.1f}%",
                    secondary_text=f"{driver.portfolio_weight_pct:.2f}% portfolio exposure",
                    detail=f"Largest {direction} contribution: {driver.contribution_percentage_points:+.2f} percentage points.",
                )
            )
        if event:
            alert_time = event.alert_time.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p").lstrip("0")
            scene_values.append(
                dict(
                    kind=StorySceneKind.ALERT,
                    eyebrow="What Wealth Copilot did",
                    title="Unusual event detected",
                    primary_value=f"{event.relevance_score:.2f} relevance",
                    secondary_text=f"Alert surfaced · {alert_time}",
                    detail=f"{event.company} moved {event.price_change_pct:+.1f}% versus {event.sector_change_pct:+.1f}% for its sector.",
                )
            )
        else:
            scene_values.append(
                dict(
                    kind=StorySceneKind.QUIET,
                    eyebrow="What Wealth Copilot did",
                    title="A relatively quiet day",
                    primary_value="No alert",
                    secondary_text="No event crossed the alert threshold.",
                )
            )
        if advisor:
            scene_values.append(
                dict(
                    kind=StorySceneKind.ADVISOR,
                    eyebrow="Human context",
                    title="You asked your advisor",
                    primary_value=f'“{_trim(advisor.question, 92)}”',
                    secondary_text="Perspective received ✓" if advisor.response_id else "Response pending",
                    detail=advisor.response_summary,
                )
            )
        elif saved:
            scene_values.append(
                dict(
                    kind=StorySceneKind.SAVED,
                    eyebrow="Saved for later",
                    title=f"{len(saved)} item{'s' if len(saved) != 1 else ''} saved",
                    primary_value="Evening context",
                    secondary_text="Ready when you want to revisit the day.",
                )
            )
        scene_values.append(
            dict(
                kind=StorySceneKind.TOMORROW,
                eyebrow="Tomorrow",
                title=f"{len(tomorrow)} event{'s' if len(tomorrow) != 1 else ''}",
                primary_value="may matter",
                secondary_text="to your portfolio" if tomorrow else "No scheduled portfolio events",
                detail=" · ".join(item.title for item in tomorrow) if tomorrow else None,
            )
        )
        # Keep one polished 3–5 scene template. Summary, driver, alert, human/saved, tomorrow.
        scene_values = scene_values[:4] + [scene_values[-1]] if len(scene_values) > 5 else scene_values
        durations = _durations(len(scene_values))
        scenes = [
            StoryScene(
                scene_id=f"scene-{index}",
                order=index,
                duration_seconds=durations[index - 1],
                **values,
            )
            for index, values in enumerate(scene_values, 1)
        ]
        signature = _signature(state)
        return DailyWealthStory(
            story_id=f"wealth-story-{state.trading_date.isoformat()}-{signature[:10]}",
            day_id=state.day_id,
            run_id=state.run_id,
            trading_date=state.trading_date,
            generated_at=datetime.now().astimezone(),
            source_signature=signature,
            portfolio_open=state.portfolio_open_snapshot.portfolio_value if state.portfolio_open_snapshot else None,
            portfolio_close=state.portfolio_close_snapshot.portfolio_value,
            portfolio_change_pct=review.portfolio_return_pct,
            top_positive_contributors=positives,
            top_negative_contributors=negatives,
            important_event=event,
            saved_items=saved,
            advisor_interaction=advisor,
            tomorrow_events=tomorrow,
            scenes=scenes,
            duration_seconds=sum(durations),
            provenance=ArtifactProvenance(
                day_id=state.day_id,
                run_id=state.run_id,
                source_checkpoint="21:01",
                source_snapshot_id=signature,
                generated_at=datetime.now().astimezone(),
            ),
        )


daily_story_builder = DailyStoryBuilder()
