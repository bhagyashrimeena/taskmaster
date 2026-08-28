import type {
  ConversationResponse,
  DashboardData,
  EventAssessment,
  FinancialDayState,
} from "./types";

export type PortfolioData = DashboardData["portfolio"];
export type DailyBriefData = DashboardData["daily_brief"];
export type DailyStateData = DashboardData["daily_state"];
export type TimelineStep = FinancialDayState["timeline"][number];

export interface AttentionItem {
  item_id: string;
  case_id: string | null;
  kind: "event" | "story";
  priority: string;
  title: string;
  summary: string;
  relevance_score: number;
  direct_exposure_pct: number;
  sector_exposure_pct: number;
  status: string;
  occurred_at: string;
  actions: string[];
}

export interface TodayResponse {
  day_id: string;
  run_id: string;
  trading_date: string;
  generated_at: string;
  greeting: string;
  attention_count: number;
  attention_message: string;
  attention_items: AttentionItem[];
  portfolio: PortfolioData;
  daily_brief: DailyBriefData;
  recent_timeline: TimelineStep[];
  next_checkpoint: TimelineStep | null;
  morning_brief_id: string | null;
  evening_brief_id: string | null;
  daily_state: DailyStateData;
  news_snapshots: NewsSnapshot[];
  likely_scenarios: LikelyScenario[];
  calendar_watch_events: CalendarWatchEvent[];
  disclaimer: string;
}

export interface PortfolioResponse {
  day_id: string;
  run_id: string;
  generated_at: string;
  portfolio: PortfolioData;
}

export type AlertCategory = "attention" | "investigating" | "monitoring" | "ignored";

export interface AlertInboxItem {
  case_id: string | null;
  event_id: string;
  instrument: string | null;
  company: string | null;
  headline: string;
  occurred_at: string;
  updated_at: string;
  category: AlertCategory;
  status: string;
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  decision: "IGNORE" | "MONITOR" | "INVESTIGATE" | "ALERT";
  notification_required: boolean;
  price_change_pct: number | null;
  sector_change_pct: number | null;
  index_change_pct: number | null;
  direct_exposure_pct: number;
  sector_exposure_pct: number;
  portfolio_impact_pct: number | null;
  relevance_score: number;
  reason: string;
}

export interface AlertInboxResponse {
  day_id: string;
  run_id: string;
  generated_at: string;
  counts: Record<AlertCategory, number>;
  items: AlertInboxItem[];
}

export interface FinancialCaseData {
  case_id: string;
  instrument: string | null;
  opened_at: string;
  updated_at: string;
  status: string;
  priority: string;
  trigger: EventAssessment["event"] & { instrument?: string | null };
  portfolio_exposure: {
    direct_pct: number;
    sector_pct: number;
    affected_holdings: string[];
  };
  sources: string[];
  user_questions: string[];
  saves: string[];
  advisor_interactions: string[];
  market_close_result: string | null;
  tomorrow_status: string | null;
}

export interface IntradayPoint {
  timestamp: string;
  price: number;
  volume: number;
}

export interface AlertDetailResponse {
  day_id: string;
  run_id: string;
  generated_at: string;
  case: FinancialCaseData;
  assessment: EventAssessment | null;
  item: AlertInboxItem;
  intraday: IntradayPoint[];
  benchmark: {
    index_name: string;
    change_pct: number | null;
    last_price: number;
  } | null;
  sector: { sector: string; change_pct: number } | null;
  likely_scenarios: LikelyScenario[];
  calendar_watch_events: CalendarWatchEvent[];
}

export interface TimelineResponse {
  day_id: string;
  run_id: string;
  trading_date: string;
  generated_at: string;
  status: FinancialDayState["status"];
  run_mode: string;
  completed_count: number;
  total_count: number;
  active_step_id: string | null;
  next_checkpoint: TimelineStep | null;
  timeline: TimelineStep[];
  financial_day: FinancialDayState;
  likely_scenarios: LikelyScenario[];
  calendar_watch_events: CalendarWatchEvent[];
}

export interface CopilotBootstrapResponse {
  day_id: string;
  run_id: string;
  generated_at: string;
  conversation_id: string | null;
  context_summary: string;
  suggested_questions: string[];
  holdings_count: number;
  relevant_story_count: number;
  active_case_count: number;
  saved_story_count: number;
  saved_event_count: number;
  voice_call_enabled: boolean;
  voice_call_reason: string | null;
  likely_scenario_count: number;
  watch_event_count: number;
  scenario_context: string | null;
}

export interface NewsSnapshot {
  story_id: string;
  day_id: string;
  title: string;
  source_name: string;
  source_url: string;
  source_status: string;
  published_at: string;
  symbols: string[];
  sectors: string[];
  summary: string;
  known_facts: string[];
  uncertainties: string[];
  portfolio_relevance_reason: string;
  direct_exposure_percent: number;
  sector_exposure_percent: number;
  relevance_score: number;
  decision: string;
  created_at: string;
}

export interface LikelyScenario {
  scenario_id: string;
  story_id: string;
  case_id: string | null;
  symbol: string | null;
  title: string;
  base_summary: string;
  scenario_type: "bullish" | "neutral" | "risk" | string;
  likelihood_label: "possible" | "plausible" | "less_likely" | string;
  confidence: "low" | "medium" | "high" | string;
  why_it_could_happen: string;
  what_to_monitor: string;
  portfolio_relevance: string;
  created_at: string;
  expires_at: string;
  status: "active" | "resolved" | "expired" | string;
}

export interface CalendarWatchEvent {
  event_id: string;
  day_id: string;
  case_id: string | null;
  story_id: string | null;
  scenario_id: string | null;
  symbol: string | null;
  title: string;
  description: string;
  scheduled_for: string;
  trigger_type: string;
  status: "scheduled" | "triggered" | "completed" | "cancelled" | string;
  created_by: "agent" | "user" | string;
  created_at: string;
  completed_at: string | null;
  reminder_copy: string;
  external_provider: string | null;
  external_event_id: string | null;
}

export interface WatchEventResponse {
  event: CalendarWatchEvent;
  external_calendar_synced: boolean;
  message: string;
}

export type OnboardingConfidence = "low" | "medium" | "high";

export interface OnboardingInferenceInput {
  user_id?: string;
  age_range?: string | null;
  income_range?: string | null;
  employment_type?: string | null;
  investment_experience?: string | null;
  existing_investments?: string[];
  primary_goals?: string[];
  time_horizon?: string | null;
  dependents?: string | null;
  emergency_fund_status?: string | null;
  market_interest_level?: string | null;
  preferred_explanation_style?: string | null;
  quiet_mode?: boolean;
}

export interface SuggestedValue<T = string> {
  value: T;
  confidence: OnboardingConfidence;
  reason: string;
}

export interface SuggestedProfile {
  financial_profile_suggestions: {
    life_stage: SuggestedValue;
    cashflow_profile: SuggestedValue;
    emergency_fund_focus: SuggestedValue;
  };
  risk_profile_suggestions: {
    risk_profile: SuggestedValue;
    risk_capacity: SuggestedValue;
    risk_comfort: SuggestedValue;
  };
  goal_suggestions: {
    primary_goal: string;
    secondary_goals: string[];
    suggested_order: string[];
  };
  agent_preferences: {
    alert_sensitivity: string;
    minimum_attention_outcome: string;
    focus_areas: string[];
    checkpoint_preferences: Record<string, boolean>;
    voice_preferences: {
      voice_briefings: boolean;
      live_agent_call: boolean;
      voice_style: string;
      answer_length: string;
    };
    learning_preference: string;
    safety_preferences: string[];
  };
  missing_inputs: string[];
  disclaimer: string;
}

export interface OnboardingSession {
  user_id: string;
  raw_inputs: OnboardingInferenceInput;
  suggested_profile: SuggestedProfile;
  final_profile: Record<string, unknown>;
  overrides: Array<{ field: string; suggested: unknown; selected: unknown; updated_at: string }>;
  created_at: string;
  updated_at: string;
}

export interface OnboardingProfileResponse {
  session: OnboardingSession | null;
}

export interface VoiceSessionResponse {
  enabled: boolean;
  reason: string | null;
  livekit_url: string | null;
  token: string | null;
  room_name: string | null;
  participant_name: string | null;
  conversation_id: string | null;
}

export interface ProductEvent {
  event_type:
    | "SNAPSHOT"
    | "EVENT_ALERT_CREATED"
    | "FINANCIAL_CASE_UPDATED"
    | "CHECKPOINT_COMPLETED"
    | "AUDIO_READY";
  emitted_at: string;
  day_id: string;
  run_id: string;
  entity_id: string | null;
  data: Record<string, unknown>;
}

export type CopilotReply = ConversationResponse;
