"""Deterministic scripts over already-approved portfolio intelligence."""

import re
from typing import TYPE_CHECKING

from ..dashboard.schemas import DashboardResponse, StoryView
from ..interaction.schemas import DailyInteractionView
from .schemas import AudioBriefType, AudioSection

if TYPE_CHECKING:
    from ..day.schemas import FinancialDayState


_ACTION_WORDS = re.compile(r"\b(buy|sell|hold|rebalance)\b", re.IGNORECASE)


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return _ACTION_WORDS.sub("review", value)


def _trim_words(value: str, limit: int) -> str:
    words = _clean(value).split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]).rstrip(".,;:") + "."


def _story_line(
    position: str,
    story: StoryView,
    *,
    headline_words: int = 16,
    summary_words: int = 25,
) -> str:
    holdings = ", ".join(story.affected_holdings)
    exposure = (
        f" It connects to {story.direct_exposure_pct:.1f} percent of your portfolio through {holdings}."
        if holdings and story.direct_exposure_pct
        else f" It connects to your {story.sector_exposure_pct:.1f} percent sector exposure."
    )
    return (
        f"{position}, {_trim_words(story.headline, headline_words)}. "
        f"{_trim_words(story.summary, summary_words)}{exposure}"
    )


class AudioScriptBuilder:
    """Selects and verbalizes dashboard facts without making new conclusions."""

    def morning(self, dashboard: DashboardResponse) -> tuple[list[AudioSection], str, list[str], list[str]]:
        event = dashboard.important_event
        stories = dashboard.daily_brief.stories[:3]
        opening = (
            f"Good morning. {dashboard.attention_message}. Your portfolio is valued at "
            f"approximately {dashboard.portfolio.portfolio_value / 100000:.2f} lakh rupees."
        )
        if event.notification_required:
            event_text = (
                f"The main event is {event.event.company}. It moved {event.event.price_change_pct:.1f} percent, "
                f"compared with {event.event.sector_change_pct:.1f} percent for its sector. "
                f"Because it represents {event.affected_portfolio_percentage:.1f} percent of your portfolio, "
                "the unusually large difference deserves attention."
            )
            event_ids = [event.event.event_id]
        else:
            event_text = "Monitoring your holdings. No material event currently needs your attention."
            event_ids = []
        story_text = " ".join(
            _story_line(label, story, headline_words=8, summary_words=10)
            for label, story in zip(("First", "Second", "Third"), stories)
        )
        close = (
            "Everything else is lower priority in the current snapshot. Open Wealth Copilot whenever you want "
            "the supporting facts, sources, or a deeper explanation."
        )
        sections = [
            AudioSection(title="Opening", text=opening),
            AudioSection(title="Important event", text=event_text),
            AudioSection(title="What matters", text=story_text),
            AudioSection(title="Close", text=close),
        ]
        script = _clean(" ".join(section.text for section in sections))
        return sections, script, [story.id for story in stories], event_ids

    def evening(
        self,
        dashboard: DashboardResponse,
        daily_state: DailyInteractionView,
        financial_day: "FinancialDayState | None" = None,
    ) -> tuple[list[AudioSection], str, list[str], list[str]]:
        event = dashboard.important_event
        by_id = {story.id: story for story in dashboard.daily_brief.stories}
        saved_ids = list(daily_state.saved_story_ids)
        if financial_day:
            saved_ids.extend(item for item in financial_day.saved_stories if item not in saved_ids)
        saved = [by_id[item] for item in saved_ids if item in by_id]
        selected = saved[:3] or dashboard.daily_brief.stories[:2]
        opening = "Here is your financial day in about ninety seconds."
        if event.notification_required:
            event_text = (
                f"The main event was {event.event.company}, which moved {event.event.price_change_pct:.1f} percent "
                f"while its sector moved {event.event.sector_change_pct:.1f} percent. It mattered because your direct "
                f"exposure is {event.affected_portfolio_percentage:.1f} percent. The event remains an attention item, "
                "and the retained evidence does not establish one confirmed cause."
            )
        else:
            event_text = "Monitoring your holdings. No material event currently needs your attention."
        sectors = dashboard.portfolio.sector_exposure[:2]
        sector_text = " and ".join(
            f"{item.sector} at {item.portfolio_weight:.1f} percent"
            for item in sectors
        )
        if financial_day and financial_day.market_close_review:
            review = financial_day.market_close_review
            negative = review.top_negative_contributors[0].symbol if review.top_negative_contributors else "no single holding"
            positive = review.top_positive_contributors[0].symbol if review.top_positive_contributors else "no single holding"
            portfolio_text = (
                f"At market close, the portfolio moved {review.portfolio_return_pct:+.2f} percent. "
                f"{negative} led losses and {positive} led gains. "
                f"Today's earlier alert is included. The largest sector exposures remain {sector_text}."
            )
        else:
            portfolio_text = (
                f"At the portfolio level, the closing snapshot is approximately "
                f"{dashboard.portfolio.portfolio_value / 100000:.2f} lakh rupees across "
                f"{dashboard.portfolio.holdings_count} holdings. Your two largest sector exposures remain "
                f"{sector_text}. They provide context, not a suggested action."
            )
        if saved:
            saved_intro = f"You saved {len(saved)} item{'s' if len(saved) != 1 else ''} to revisit."
        else:
            saved_intro = "You did not save a story today, so this wrap uses the two highest-ranked items."
        stories_text = saved_intro + " " + " ".join(
            _story_line(label, story, headline_words=8, summary_words=10)
            for label, story in zip(("One", "Two", "Three"), selected)
        )
        question_count = len(financial_day.questions_asked) if financial_day else 0
        tomorrow_count = len(financial_day.tomorrow_events) if financial_day else 0
        close = (
            f"You asked {question_count} question{'s' if question_count != 1 else ''} today. "
            + (
                f"Your advisor provided {len(financial_day.advisor_responses)} perspective"
                f"{'s' if len(financial_day.advisor_responses) != 1 else ''}, retained as attributed commentary. "
                if financial_day and financial_day.advisor_responses
                else ""
            )
            + f"There are {tomorrow_count} portfolio-relevant scheduled item{'s' if tomorrow_count != 1 else ''} retained for tomorrow. "
            "Sources and unresolved context remain available."
        )
        sections = [
            AudioSection(title="Opening", text=opening),
            AudioSection(title="Main event", text=event_text),
            AudioSection(title="Portfolio context", text=portfolio_text),
            AudioSection(title="Saved for evening", text=stories_text),
            AudioSection(title="Close", text=close),
        ]
        script = _clean(" ".join(section.text for section in sections))
        used_events = [event.event.event_id]
        saved_event_ids = list(daily_state.saved_event_ids)
        if financial_day:
            saved_event_ids.extend(item for item in financial_day.saved_events if item not in saved_event_ids)
        used_events.extend(event_id for event_id in saved_event_ids if event_id not in used_events)
        return sections, script, [story.id for story in selected], used_events

    def story(
        self, financial_day: "FinancialDayState"
    ) -> tuple[list[AudioSection], str, list[str], list[str]]:
        from ..story.builder import daily_story_builder

        story = daily_story_builder.build(financial_day)
        review = financial_day.market_close_review
        assert review is not None
        movement = "down" if review.portfolio_return_pct < 0 else "up" if review.portfolio_return_pct > 0 else "unchanged"
        summary = (
            f"Here is your financial day. Your portfolio closed at {story.portfolio_close / 100000:.2f} lakh rupees, "
            f"{movement} {abs(review.portfolio_return_pct):.2f} percent."
        )
        driver = story.top_negative_contributors[0] if story.top_negative_contributors else story.top_positive_contributors[0] if story.top_positive_contributors else None
        driver_text = (
            f"{driver.symbol} was the largest driver, moving {driver.daily_return_pct:+.1f} percent "
            f"at {driver.portfolio_weight_pct:.2f} percent exposure."
            if driver
            else "No single holding dominated the closing move."
        )
        if story.important_event:
            event = story.important_event
            event_text = (
                f"{event.company} was flagged at {event.relevance_score:.2f} relevance because it diverged from its sector."
            )
        else:
            event_text = "No retained event crossed the alert threshold today."
        if story.advisor_interaction:
            advisor_text = (
                "Your advisor's perspective was received and retained as human commentary."
                if story.advisor_interaction.response_id
                else "You asked your advisor for perspective, and the response is still pending."
            )
        else:
            advisor_text = ""
        tomorrow_text = (
            f"Tomorrow, {len(story.tomorrow_events)} portfolio-relevant "
            f"item{'s are' if len(story.tomorrow_events) != 1 else ' is'} retained. "
            "This is context, not an investment instruction."
        )
        sections = [
            AudioSection(title="Your day", text=summary),
            AudioSection(title="Biggest driver", text=driver_text),
            AudioSection(title="Alert", text=event_text),
        ]
        if advisor_text:
            sections.append(AudioSection(title="Human context", text=advisor_text))
        sections.append(AudioSection(title="Tomorrow", text=tomorrow_text))
        script = _clean(" ".join(section.text for section in sections))
        event_ids = [story.important_event.event_id] if story.important_event else []
        return sections, script, list(story.saved_items), event_ids


def validate_script(script: str) -> None:
    if _ACTION_WORDS.search(script):
        raise ValueError("Audio script crossed the investment-instruction boundary")
    words = len(script.split())
    if not 105 <= words <= 190:
        raise ValueError(f"Audio script must contain 105–190 words, got {words}")


def validate_story_script(script: str) -> None:
    if _ACTION_WORDS.search(script):
        raise ValueError("Story narration crossed the investment-instruction boundary")
    words = len(script.split())
    if not 45 <= words <= 70:
        raise ValueError(f"Story narration must contain 45–70 words, got {words}")


audio_script_builder = AudioScriptBuilder()
