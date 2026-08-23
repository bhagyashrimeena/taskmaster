import type { ConversationInput, FinancialDayClockState } from "../types";
import type {
  AlertCategory,
  AlertDetailResponse,
  AlertInboxResponse,
  CopilotBootstrapResponse,
  CopilotReply,
  PortfolioResponse,
  TimelineResponse,
  TodayResponse,
  VoiceSessionResponse,
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
