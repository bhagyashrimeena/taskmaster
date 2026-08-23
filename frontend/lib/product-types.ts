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
