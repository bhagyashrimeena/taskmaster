export const productKeys = {
  all: ["wealth-copilot"] as const,
  today: ["wealth-copilot", "today"] as const,
  portfolio: ["wealth-copilot", "portfolio"] as const,
  alerts: (category?: string) => ["wealth-copilot", "alerts", category ?? "all"] as const,
  alert: (caseId: string) => ["wealth-copilot", "alert", caseId] as const,
  timeline: ["wealth-copilot", "timeline"] as const,
  dayClock: ["wealth-copilot", "day-clock"] as const,
  onboarding: (userId = "demo_user") => ["wealth-copilot", "onboarding", userId] as const,
  copilot: (conversationId?: string | null) => ["wealth-copilot", "copilot", conversationId ?? "new"] as const,
};
