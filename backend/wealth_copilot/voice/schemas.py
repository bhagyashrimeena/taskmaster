"""Credential-safe contracts and context packets for Copilot voice calls."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class VoiceHoldingContext(VoiceModel):
    symbol: str
    name: str | None = None
    value: float
    weight_percent: float
    today_change_percent: float | None = None
    sector: str | None = None


class VoiceSectorContext(VoiceModel):
    sector: str
    weight_percent: float


class VoicePortfolioContext(VoiceModel):
    total_value: float
    today_change_amount: float | None = None
    today_change_percent: float | None = None
    overall_gain_amount: float | None = None
    overall_gain_percent: float | None = None
    benchmark_change_percent: float | None = None
    benchmark_label: str | None = None
    holdings_count: int
    top_holdings: list[VoiceHoldingContext]
    sector_exposure: list[VoiceSectorContext]
    largest_holding: str | None = None
    top_three_concentration: float | None = None
    risk_flags: list[str]


class VoiceAttentionContext(VoiceModel):
    high_priority_count: int = 0
    portfolio_relevant_story_count: int = 0
    active_case_count: int = 0
    monitoring_count: int = 0
    ignored_count: int = 0


class VoiceCaseContext(VoiceModel):
    case_id: str
    symbol: str | None = None
    title: str
    status: str
    priority: str
    detected_at: datetime
    price_change_percent: float | None = None
    sector_change_percent: float | None = None
    benchmark_change_percent: float | None = None
    direct_exposure_percent: float
    sector_exposure_percent: float
    relevance_score: float | None = None
    short_reason: str
    known_facts: list[str]
    uncertainties: list[str]
    suggested_next_actions: list[str]


class VoiceStoryContext(VoiceModel):
    story_id: str
    title: str
    source_name: str
    symbols: list[str]
    sectors: list[str]
    summary: str
    relevance_score: float
    direct_exposure_percent: float
    sector_exposure_percent: float
    source_status: str


class VoiceTimelineContext(VoiceModel):
    time: str
    type: str
    title: str
    status: str
    summary: str


class VoicePreviousTurnContext(VoiceModel):
    user: str
    assistant_summary: str | None = None
    topic: str | None = None
    case_id: str | None = None


class VoicePinnedContext(VoiceModel):
    active_topic: str | None = None
    last_discussed_symbol: str | None = None
    last_discussed_case_id: str | None = None
    last_user_intent: str | None = None
    last_market_question: str | None = None
    last_listed_items: list[str] = Field(default_factory=list)
    last_answer_summary: str | None = None
    interrupted_turn_summary: str | None = None


class VoiceContext(VoiceModel):
    conversation_id: str
    mode: str
    user_local_time: datetime
    day_id: str
    run_id: str
    current_checkpoint: str | None = None
    financial_day_status: str
    portfolio: VoicePortfolioContext
    attention_summary: VoiceAttentionContext
    active_cases: list[VoiceCaseContext]
    relevant_stories: list[VoiceStoryContext]
    timeline: list[VoiceTimelineContext]
    previous_voice_turns: list[VoicePreviousTurnContext]
    pinned_context: VoicePinnedContext
