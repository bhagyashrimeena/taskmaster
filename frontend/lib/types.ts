export type FreshnessStatus = "live" | "cached" | "stale";
export type RefreshPhase = "idle" | "queued" | "running" | "complete" | "failed";

export interface HoldingView {
  symbol: string;
  market_value: number;
  portfolio_weight: number;
  day_change_pct: number | null;
}

export interface SectorView {
  sector: string;
  portfolio_weight: number;
}

export interface StoryView {
  id: string;
  headline: string;
  summary: string;
  source_name: string;
  source_url: string;
  canonical_url: string | null;
  canonical_url_status: "verified" | "unavailable";
  published_at: string;
  affected_holdings: string[];
  direct_exposure_pct: number;
  sector_exposure_pct: number;
  relevance_score: number;
  final_utility_score: number;
  source_authority: string;
  why_am_i_seeing_this: string;
  actions: string[];
}

export interface TraceStep {
  stage: string;
  outcome: string;
  details: Record<string, unknown>;
}

export interface EventAssessment {
  event: {
    event_id: string;
    timestamp: string;
    symbol: string | null;
    company: string | null;
    sector: string | null;
    price_change_pct: number | null;
    sector_change_pct: number | null;
    headline: string;
  };
  affected_portfolio_percentage: number;
  sector_exposure_percentage: number;
  relevance_score: number;
  decision: "IGNORE" | "MONITOR" | "INVESTIGATE" | "ALERT";
  notification_required: boolean;
  title: string;
  reason: string;
  actions: string[];
  trace: TraceStep[];
  investigation_status: string;
  developments: Array<{ id: string; headline: string; source_url: string }>;
}

export interface DashboardData {
  day_id: string;
  run_id: string;
  generated_at: string;
  greeting: string;
  attention_count: number;
  attention_summary?: {
    high_priority_count: number;
    portfolio_relevant_story_count: number;
    active_event_count: number;
    story_ids: string[];
    event_ids: string[];
  };
  attention_message: string;
  portfolio: {
    source: {
      label: string;
      is_live: boolean;
      provider: string;
      scenario_id: string | null;
      checkpoint: string | null;
    };
    as_of: string;
    currency: string;
    portfolio_value: number;
    invested_value: number;
    unrealized_pnl: number;
    day_pnl: number | null;
    day_change_pct: number | null;
    holdings_count: number;
    largest_holdings: HoldingView[];
    sector_exposure: SectorView[];
  };
  daily_brief: {
    day_id: string;
    run_id: string;
    freshness: {
      status: FreshnessStatus;
      label: string;
      fetched_at: string;
      cache_age_seconds: number;
      refresh_attempted: boolean;
    };
    candidate_count: number;
    analyzed_count: number;
    stories: StoryView[];
  };
  important_event: EventAssessment;
  today_events: EventAssessment[];
  agent_activity: Array<{
    stage: string;
    label: string;
    status: string;
    detail: string;
  }>;
  refresh: {
    refresh_id: string | null;
    phase: RefreshPhase;
    started_at: string | null;
    completed_at: string | null;
    message: string;
  };
  daily_state: {
    trading_date: string;
    saved_story_ids: string[];
    saved_event_ids: string[];
    feedback: Record<string, string>;
  };
  disclaimer: string;
}

export type InteractionMode = "explain" | "chat" | "research";

export interface SourceReference {
  name: string;
  url: string;
  authority: string;
  kind: string;
  title?: string | null;
  publisher?: string | null;
  citation_uri?: string | null;
  canonical_url?: string | null;
  retrieved_at?: string | null;
}

export interface SurfaceContext {
  day_id?: string | null;
  run_id?: string | null;
  target_type: string;
  target_id: string | null;
  title: string;
  facts: string[];
  interpretation: string[];
  unknowns: string[];
  sources: SourceReference[];
  portfolio_context: string;
}

export interface ConversationResponse {
  conversation_id: string;
  message_id: string;
  mode: InteractionMode;
  route: string;
  answer: string;
  context: SurfaceContext;
  sources: SourceReference[];
  suggested_questions: string[];
  used_search: boolean;
  used_existing_context: boolean;
  fallback_used: boolean;
  agent_trace: string[];
  created_at: string;
}

export interface ResearchJob {
  job_id: string;
  status: "queued" | "researching" | "complete" | "fallback" | "failed";
  message: string;
  result: ConversationResponse | null;
  created_at: string;
  completed_at: string | null;
}

export interface ConversationInput {
  conversation_id?: string;
  message: string;
  mode?: InteractionMode;
  active_story_id?: string;
  active_event_id?: string;
}

export type AudioBriefType = "morning" | "evening" | "story";
export type AudioStatus = "text_ready" | "queued" | "generating" | "ready" | "fallback";

export interface AudioBrief {
  brief_id: string;
  day_id: string | null;
  run_id: string | null;
  type: AudioBriefType;
  title: string;
  generated_at: string;
  source_snapshot_at: string;
  sections: Array<{ title: string; text: string }>;
  script: string;
  duration_target_seconds: number;
  estimated_duration_seconds: number;
  actual_duration_seconds: number | null;
  voice: string;
  model: string;
  status: AudioStatus;
  audio_url: string | null;
  fallback_text: string;
  data_freshness: string;
  used_stories: string[];
  used_events: string[];
  cached: boolean;
  message: string;
}

export interface AudioGenerationResponse {
  brief: AudioBrief;
  accepted: boolean;
}

export type DayStatus = "not_started" | "running" | "complete" | "failed";
export type DayStepStatus = "pending" | "running" | "complete" | "failed";

export interface PresentationClockState {
  trading_date: string;
  current_time: string;
  speed: number;
  status: "paused" | "running" | "complete" | "failed";
  active_checkpoint: string | null;
  next_checkpoint: string | null;
  completed_checkpoint_ids: string[];
  message: string;
}

export interface FinancialDayState {
  trading_date: string;
  day_id: string;
  run_id: string;
  scenario_id: string;
  user_id: string;
  status: DayStatus;
  run_mode: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  morning_brief_id: string | null;
  evening_brief_id: string | null;
  story_audio_brief_id: string | null;
  daily_story: DailyWealthStory | null;
  portfolio_health: {
    status: "NORMAL" | "WATCH" | "ATTENTION";
    concentration_flags: string[];
  } | null;
  events_alerted: EventAssessment[];
  saved_stories: string[];
  saved_events: string[];
  questions_asked: Array<{ question: string; asked_at: string }>;
  advisor_requests: AdvisorPacket[];
  advisor_responses: AdvisorResponse[];
  market_close_review: {
    portfolio_return_pct: number;
    alert_event_ids: string[];
    explanation: string;
  } | null;
  tomorrow_events: Array<{
    event_id: string;
    title: string;
    scheduled_at: string;
    portfolio_exposure_pct: number;
    why_relevant: string;
    relevance_rank: number;
  }>;
  timeline: Array<{
    step_id: string;
    scheduled_time: string;
    label: string;
    status: DayStepStatus;
    detail: string;
    linked_ids: string[];
  }>;
  simulated_duration_seconds: number | null;
  last_error: string | null;
}

export type StorySceneKind = "summary" | "driver" | "alert" | "quiet" | "saved" | "advisor" | "tomorrow";

export interface StoryScene {
  scene_id: string;
  order: number;
  kind: StorySceneKind;
  duration_seconds: number;
  eyebrow: string;
  title: string;
  primary_value: string | null;
  secondary_text: string | null;
  detail: string | null;
}

export interface DailyWealthStory {
  story_id: string;
  day_id: string;
  run_id: string;
  trading_date: string;
  generated_at: string;
  source_signature: string;
  portfolio_open: number | null;
  portfolio_close: number | null;
  portfolio_change_pct: number | null;
  top_positive_contributors: Array<{
    symbol: string;
    portfolio_weight_pct: number;
    daily_return_pct: number;
    contribution_percentage_points: number;
    direction: string;
  }>;
  top_negative_contributors: Array<{
    symbol: string;
    portfolio_weight_pct: number;
    daily_return_pct: number;
    contribution_percentage_points: number;
    direction: string;
  }>;
  important_event: {
    event_id: string;
    company: string;
    price_change_pct: number;
    sector_change_pct: number;
    exposure_pct: number;
    relevance_score: number;
    alert_time: string;
  } | null;
  saved_items: string[];
  advisor_interaction: {
    request_id: string;
    question: string;
    response_id: string | null;
    response_summary: string | null;
    advisor_name: string | null;
  } | null;
  tomorrow_events: Array<{
    event_id: string;
    title: string;
    scheduled_at: string;
    portfolio_exposure_pct: number;
  }>;
  scenes: StoryScene[];
  audio_brief_id: string | null;
  duration_seconds: number;
  status: "ready";
  cached: boolean;
}

export interface StorySceneNarration {
  scene_id: string;
  text: string;
  status: "queued" | "generating" | "ready" | "fallback";
  audio_url: string | null;
  actual_duration_seconds: number | null;
}

export interface StoryNarration {
  story_id: string;
  day_id: string;
  run_id: string;
  status: "queued" | "generating" | "ready" | "fallback";
  scenes: StorySceneNarration[];
  total_duration_seconds: number | null;
  muted: boolean;
  message: string;
}

export type AdvisorStatus = "DRAFT" | "READY" | "SENT" | "REPLIED" | "CLOSED";

export interface AdvisorProfile {
  advisor_id: string;
  name: string;
  email: string;
  firm: string;
  provider: "demo" | "gmail";
  connected: boolean;
}

export interface AdvisorEmailDraft {
  to_name: string;
  to_email: string;
  subject: string;
  body: string;
}

export interface AdvisorPacket {
  request_id: string;
  created_at: string;
  updated_at: string;
  target_type: "story" | "event";
  target_id: string;
  title: string;
  exposure: string;
  relevance: string;
  facts: string[];
  interpretations: string[];
  unknowns: string[];
  sources: SourceReference[];
  user_question: string;
  suggested_questions: string[];
  status: AdvisorStatus;
  provider: "demo" | "gmail";
  email: AdvisorEmailDraft;
  sent_at: string | null;
  response_id: string | null;
  send_error: string | null;
}

export interface AdvisorResponse {
  response_id: string;
  request_id: string;
  received_at: string;
  advisor_name: string;
  message: string;
  perspective_label: string;
}

export interface AdvisorCase {
  packet: AdvisorPacket;
  response: AdvisorResponse | null;
}
