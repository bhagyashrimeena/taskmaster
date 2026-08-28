import type { ConversationInput, FinancialDayClockState } from "../types";
import type {
  AlertCategory,
  AlertDetailResponse,
  AlertInboxResponse,
  CopilotBootstrapResponse,
  CopilotReply,
  OnboardingInferenceInput,
  OnboardingProfileResponse,
  OnboardingSession,
  PortfolioResponse,
  SuggestedProfile,
  TimelineResponse,
  TodayResponse,
  VoiceSessionResponse,
  WatchEventResponse,
} from "../product-types";

const base = "/api/backend/v1";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

export const getToday = () => getJson<TodayResponse>("/today");
export const getPortfolio = () => getJson<PortfolioResponse>("/portfolio");
export const getTimeline = () => getJson<TimelineResponse>("/timeline");
export const getFinancialDayClock = () => getJson<FinancialDayClockState>("/day/clock");
export const startFinancialDayClock = () => postJson<FinancialDayClockState>("/day/clock/start");
export const pauseFinancialDayClock = () => postJson<FinancialDayClockState>("/day/clock/pause");
export const restartFinancialDayClock = () => postJson<FinancialDayClockState>("/day/clock/restart");
export const advanceFinancialDayClock = () => postJson<FinancialDayClockState>("/day/clock/next");
export const getAlert = (caseId: string) => getJson<AlertDetailResponse>(`/alerts/${caseId}`);
export const getCopilotBootstrap = (conversationId?: string | null) =>
  getJson<CopilotBootstrapResponse>(
    `/copilot${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""}`,
  );
export const getAlerts = (category?: AlertCategory) =>
  getJson<AlertInboxResponse>(`/alerts${category ? `?category=${category}` : ""}`);

export async function askCopilot(input: ConversationInput): Promise<CopilotReply> {
  const response = await fetch(`${base}/copilot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error("Wealth Copilot could not answer right now.");
  return response.json();
}

export const createVoiceSession = (conversationId?: string | null, currentCaseId?: string | null) =>
  postJson<VoiceSessionResponse>("/copilot/voice/session", {
    conversation_id: conversationId ?? null,
    current_case_id: currentCaseId ?? null,
  });

export const productEventStreamUrl = "/api/events/stream";

export const createWatchEvent = (input: {
  title: string;
  description: string;
  symbol?: string | null;
  story_id?: string | null;
  case_id?: string | null;
  scenario_id?: string | null;
  trigger_type?: string;
}) => postJson<WatchEventResponse>("/watch-events", input);

export const inferOnboardingProfile = (input: OnboardingInferenceInput) =>
  postJson<SuggestedProfile>("/onboarding/infer", input);

export const saveOnboardingProfile = (input: {
  user_id?: string;
  raw_inputs: OnboardingInferenceInput;
  suggested_profile: SuggestedProfile;
  final_profile: Record<string, unknown>;
}) => postJson<OnboardingSession>("/onboarding/profile", input);

export const getOnboardingProfile = (userId = "demo_user") =>
  getJson<OnboardingProfileResponse>(`/onboarding/profile?user_id=${encodeURIComponent(userId)}`);
