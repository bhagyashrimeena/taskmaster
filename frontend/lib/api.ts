import type { AdvisorCase, AdvisorProfile, AudioBrief, AudioBriefType, AudioGenerationResponse, ConversationInput, ConversationResponse, DailyWealthStory, DashboardData, FinancialDayState, ResearchJob, StoryNarration } from "./types";

const base = "/api/backend/v1";

export async function getDashboard(): Promise<DashboardData> {
  const response = await fetch(`${base}/dashboard`, { cache: "no-store" });
  if (!response.ok) throw new Error("Dashboard data is temporarily unavailable.");
  return response.json();
}

export async function startStoryNarration(): Promise<StoryNarration> {
  const response = await fetch(`${base}/story/today/narration`, { method: "POST" });
  if (!response.ok) throw new Error("Story narration could not be prepared.");
  return response.json();
}

export async function getStoryNarration(storyId: string): Promise<StoryNarration> {
  const response = await fetch(`${base}/story/${storyId}/narration`, { cache: "no-store" });
  if (!response.ok) throw new Error("Story narration is not ready.");
  return response.json();
}

export function storySceneAudioUrl(path: string): string {
  return path.replace("/api/v1", base);
}

export async function requestRefresh(): Promise<void> {
  const response = await fetch(`${base}/dashboard/refresh`, { method: "POST" });
  if (!response.ok) throw new Error("Refresh could not be queued.");
}

export async function saveEventAction(eventId: string, action: string): Promise<void> {
  const response = await fetch(`${base}/events/${eventId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!response.ok) throw new Error("The event could not be saved.");
}

export async function askTaskMaster(input: ConversationInput): Promise<ConversationResponse> {
  const response = await fetch(`${base}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error("Wealth Copilot could not answer right now.");
  return response.json();
}

export async function startResearch(input: Omit<ConversationInput, "mode">): Promise<ResearchJob> {
  const response = await fetch(`${base}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error("Research could not be started.");
  return response.json();
}

export async function getResearch(jobId: string): Promise<ResearchJob> {
  const response = await fetch(`${base}/research/${jobId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Research status is unavailable.");
  return response.json();
}

export async function saveStoryForEvening(storyId: string): Promise<void> {
  const response = await fetch(`${base}/stories/${storyId}/save`, { method: "POST" });
  if (!response.ok) throw new Error("The story could not be saved.");
}

export async function recordFeedback(input: {
  target_type: "story" | "event" | "conversation";
  target_id: string;
  value: "useful" | "not_relevant";
  conversation_id?: string;
}): Promise<void> {
  const response = await fetch(`${base}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error("Feedback could not be recorded.");
}

export async function getAudioBrief(type: AudioBriefType): Promise<AudioBrief> {
  const response = await fetch(`${base}/audio/${type}`, { cache: "no-store" });
  if (!response.ok) throw new Error("The audio brief is temporarily unavailable.");
  return response.json();
}

export async function generateAudioBrief(type: AudioBriefType): Promise<AudioGenerationResponse> {
  const response = await fetch(`${base}/audio/${type}/generate`, { method: "POST" });
  if (!response.ok) throw new Error("Audio generation could not be started.");
  return response.json();
}

export async function getAudioStatus(briefId: string): Promise<AudioBrief> {
  const response = await fetch(`${base}/audio/${briefId}/status`, { cache: "no-store" });
  if (!response.ok) throw new Error("Audio status is temporarily unavailable.");
  return response.json();
}

export function audioFileUrl(path: string): string {
  return path.replace(/^\/api\/v1/, "/api/backend/v1");
}

export async function getFinancialDay(): Promise<FinancialDayState> {
  const response = await fetch(`${base}/day`, { cache: "no-store" });
  if (!response.ok) throw new Error("Financial day state is temporarily unavailable.");
  return response.json();
}

export async function runDemoDay(): Promise<FinancialDayState> {
  const response = await fetch(`${base}/day/demo`, { method: "POST" });
  if (!response.ok) throw new Error("The financial day could not be started.");
  return response.json();
}

export async function getDailyWealthStory(): Promise<DailyWealthStory> {
  const response = await fetch(`${base}/story/today`, { cache: "no-store" });
  if (!response.ok) throw new Error("Your visual recap will be ready after market close.");
  return response.json();
}

export async function getAdvisorProfile(): Promise<AdvisorProfile> {
  const response = await fetch(`${base}/advisor/profile`, { cache: "no-store" });
  if (!response.ok) throw new Error("Advisor profile is unavailable.");
  return response.json();
}

export async function createAdvisorPacket(input: {
  target_type: "story" | "event";
  target_id: string;
  user_question: string;
}): Promise<AdvisorCase> {
  const response = await fetch(`${base}/advisor/packets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error("The advisor packet could not be prepared.");
  return response.json();
}

export async function markAdvisorPacketReady(requestId: string): Promise<AdvisorCase> {
  const response = await fetch(`${base}/advisor/packets/${requestId}/ready`, { method: "POST" });
  if (!response.ok) throw new Error("The advisor email could not be opened for review.");
  return response.json();
}

export async function sendAdvisorPacket(requestId: string): Promise<AdvisorCase> {
  const response = await fetch(`${base}/advisor/packets/${requestId}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed: true }),
  });
  if (!response.ok) throw new Error("The advisor request could not be sent.");
  return response.json();
}

export async function getAdvisorCase(requestId: string): Promise<AdvisorCase> {
  const response = await fetch(`${base}/advisor/packets/${requestId}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Advisor request status is unavailable.");
  return response.json();
}
