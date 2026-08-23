import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright-core";

const web = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

const bootstrap = {
  day_id: "voice-day",
  run_id: "voice-run",
  generated_at: new Date().toISOString(),
  conversation_id: null,
  context_summary: "14 holdings, 5 relevant stories, and 1 active financial case.",
  suggested_questions: ["Why does the latest alert matter?", "What deserves my attention right now?", "Summarize my biggest exposures", "What changed since morning?"],
  holdings_count: 14,
  relevant_story_count: 5,
  active_case_count: 1,
  saved_story_count: 0,
  saved_event_count: 0,
  voice_call_enabled: false,
  voice_call_reason: "Live call is not configured yet.",
};

function reply(message) {
  return {
    conversation_id: "voice-conversation",
    message_id: "voice-answer",
    mode: "voice",
    route: "taskmaster",
    answer: `Your voice question was checked against today’s portfolio context: ${message}`,
    context: {}, sources: [], suggested_questions: ["What should I monitor today?"], used_search: false,
    used_existing_context: true, fallback_used: false, agent_trace: ["TaskMaster completed"], created_at: new Date().toISOString(),
  };
}

async function configure(page, captured, bootstrapResponse = bootstrap) {
  await page.route("**/api/backend/v1/copilot**", async (route, request) => {
    if (request.method() === "GET") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(bootstrapResponse) });
    const body = request.postDataJSON();
    captured.push(body);
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(reply(body.message)) });
  });
}

try {
  const supportedContext = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce", serviceWorkers: "block" });
  await supportedContext.addInitScript(() => {
    class FakeSpeechRecognition {
      lang = ""; interimResults = true; continuous = false; onresult = null; onerror = null; onend = null;
      start() {
        setTimeout(() => {
          this.onresult?.({ resultIndex: 0, results: [{ 0: { transcript: "What changed since morning?" } }] });
          this.onend?.();
        }, 20);
      }
      stop() { this.onend?.(); }
      abort() { this.onend?.(); }
    }
    window.SpeechRecognition = FakeSpeechRecognition;
    window.webkitSpeechRecognition = FakeSpeechRecognition;
  });
  const page = await supportedContext.newPage();
  const captured = [];
  await configure(page, captured);
  await page.goto(`${web}/copilot`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Talk to your wealth agent" }).waitFor();
  await page.getByRole("button", { name: "Start voice input" }).first().click();
  await page.getByLabel("Ask Wealth Copilot").waitFor();
  await page.waitForFunction(() => document.querySelector('textarea[aria-label="Ask Wealth Copilot"]')?.value === "What changed since morning?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.locator("[data-copilot-answer-lead]").waitFor();
  if (captured[0]?.mode !== "voice") throw new Error(`Voice transcript bypassed the shared Copilot route: ${JSON.stringify(captured)}`);
  if (!(await page.getByRole("button", { name: "Call your wealth agent" }).isDisabled())) throw new Error("Unconfigured LiveKit call is actionable");
  const geometry = await page.evaluate(() => ({ viewport: innerWidth, body: document.body.scrollWidth, document: document.documentElement.scrollWidth }));
  if (geometry.body > geometry.viewport + 1 || geometry.document > geometry.viewport + 1) throw new Error(`Copilot overflows: ${JSON.stringify(geometry)}`);
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  if (axe.violations.length) throw new Error(`Accessibility violations: ${axe.violations.map((item) => item.id).join(", ")}`);
  const unsupportedContext = await browser.newContext({ viewport: { width: 360, height: 740 }, serviceWorkers: "block" });
  await unsupportedContext.addInitScript(() => { delete window.SpeechRecognition; delete window.webkitSpeechRecognition; });
  const unsupported = await unsupportedContext.newPage();
  const unsupportedCaptured = [];
  const unsupportedErrors = [];
  const unsupportedRequests = [];
  unsupported.on("pageerror", (error) => unsupportedErrors.push(error.message));
  unsupported.on("console", (message) => { if (message.type() === "error") unsupportedErrors.push(message.text()); });
  unsupported.on("request", (request) => { if (request.url().includes("copilot")) unsupportedRequests.push(`${request.method()} ${request.url()}`); });
  await configure(unsupported, unsupportedCaptured);
  await unsupported.goto(`${web}/copilot`, { waitUntil: "domcontentloaded" });
  await unsupported.getByText(/Voice input is not available in this browser/).waitFor();
  if (!(await unsupported.getByRole("button", { name: "Start voice input" }).first().isDisabled())) throw new Error("Unsupported voice input is actionable");
  const textComposer = unsupported.getByLabel("Ask Wealth Copilot");
  await textComposer.fill("Text remains available");
  await unsupported.getByRole("button", { name: "Send", exact: true }).waitFor({ state: "visible" });
  await textComposer.press("Enter");
  try {
    await unsupported.locator("[data-copilot-answer-lead]").waitFor();
  } catch (error) {
    const diagnostic = {
      captured: unsupportedCaptured,
      requests: unsupportedRequests,
      errors: unsupportedErrors,
      conversation: await unsupported.locator('[aria-label="Wealth Copilot conversation"]').allTextContents(),
      body: (await unsupported.locator("body").innerText()).slice(-1200),
    };
    throw new Error(`${error.message}\n${JSON.stringify(diagnostic, null, 2)}`);
  }
  if (unsupportedCaptured[0]?.mode !== "text") throw new Error(`Text fallback bypassed the shared Copilot route: ${JSON.stringify(unsupportedCaptured)}`);
  if (unsupportedErrors.length) throw new Error(unsupportedErrors.join(" | "));
  await unsupportedContext.close();

  const failedCallContext = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: "block" });
  const failedCall = await failedCallContext.newPage();
  await configure(failedCall, [], { ...bootstrap, voice_call_enabled: true, voice_call_reason: null });
  await failedCall.route("**/api/backend/v1/copilot/voice/session", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      enabled: true,
      livekit_url: "wss://127.0.0.1:9",
      token: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIiwidmlkZW8iOnsicm9vbSI6InRlc3QiLCJyb29tSm9pbiI6dHJ1ZX19.signature",
      room_name: "test-room",
      participant_name: "test-user",
      conversation_id: "voice-conversation",
    }),
  }));
  await failedCall.goto(`${web}/copilot`, { waitUntil: "domcontentloaded" });
  await failedCall.getByRole("button", { name: "Call your wealth agent" }).click();
  await failedCall.getByText("The call could not connect. You can retry or type your question.", { exact: true }).waitFor({ timeout: 20_000 });
  await failedCall.getByLabel("Ask Wealth Copilot").fill("Text still works after a failed call");
  await failedCallContext.close();
  await supportedContext.close();
  console.log(JSON.stringify({ status: "passed", voiceTranscriptMode: captured[0]?.mode, liveKitConfigured: false, textFallback: true, callFailureFallback: true }, null, 2));
} finally {
  await browser.close();
}
