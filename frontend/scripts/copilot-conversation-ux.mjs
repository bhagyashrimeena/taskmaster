import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const baseUrl = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const artifactDirectory = new URL("../../artifacts/copilot-conversation-pass/", import.meta.url);
const artifactPath = fileURLToPath(artifactDirectory);
await mkdir(artifactDirectory, { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

const viewports = [
  { name: "360x740", width: 360, height: 740 },
  { name: "390x844", width: 390, height: 844 },
  { name: "430x932", width: 430, height: 932 },
];

const bootstrap = {
  day_id: "copilot-ux-day",
  run_id: "copilot-ux-run",
  generated_at: "2026-08-23T12:00:00+05:30",
  conversation_id: null,
  context_summary: "14 holdings · 5 relevant stories · 0 active alerts",
  suggested_questions: [
    "What deserves my attention right now?",
    "Why is HDFC important to my portfolio?",
    "What changed since morning?",
    "Explain today’s portfolio movement.",
  ],
  holdings_count: 14,
  relevant_story_count: 5,
  active_case_count: 0,
  saved_story_count: 5,
  saved_event_count: 0,
  voice_call_enabled: false,
  voice_call_reason: "Live call is not configured yet.",
};

const normalAnswer = [
  "Nothing needs an immediate alert right now.",
  "HDFC Bank is still worth monitoring because it is your largest holding.",
  "Financial services are also your largest sector exposure.",
  "That makes HDFC developments more relevant to your portfolio than routine market noise.",
].join(" ");

const longResearch = Array.from({ length: 135 }, (_, index) =>
  `Research observation ${index + 1} preserves verified portfolio context, market evidence, source attribution, and the distinction between monitoring and immediate attention.`,
).join(" ");
const longAnswer = `Based on the current dashboard data and system state, here is what deserves your attention right now. Nothing needs an immediate alert right now. HDFC Bank remains worth monitoring because it is your largest holding. Financial services are your largest sector exposure. Recent developments therefore deserve proportionate attention, not an automatic action.\n\nWhy this matters\n• HDFC Bank is the largest single holding shown in the current context.\n• Financial services are the largest sector exposure shown in the current context.\n\nVerified facts\n• The current decision state is monitoring rather than an immediate alert.\n• The evidence remains linked to the saved sources.\n\nPortfolio impact\nHDFC-related movement can matter more to this portfolio because of its existing holding and sector exposure.\n\nFull research\n${longResearch}`;
if (longAnswer.trim().split(/\s+/).length < 800) throw new Error("Long-answer fixture must exceed 800 words");

function reply(answer, index, suggestions = []) {
  return {
    conversation_id: "copilot-ux-conversation",
    message_id: `assistant-${index}`,
    mode: "chat",
    route: "explain",
    answer,
    context: {},
    sources: [{ name: "Portfolio snapshot", url: "https://example.com/portfolio", canonical_url: "https://example.com/portfolio", provider: "fixture", published_at: null }],
    suggested_questions: suggestions,
    used_search: false,
    used_existing_context: true,
    fallback_used: false,
    agent_trace: [],
    created_at: new Date().toISOString(),
  };
}

async function assertLayout(page, label) {
  const state = await page.evaluate(() => {
    const composer = document.querySelector(".copilot-composer-dock form")?.getBoundingClientRect();
    const nav = document.querySelector("[data-mobile-nav]")?.getBoundingClientRect();
    const lead = [...document.querySelectorAll("[data-copilot-answer-lead]")].at(-1)?.getBoundingClientRect();
    return {
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      composer: composer ? { top: composer.top, bottom: composer.bottom, width: composer.width } : null,
      nav: nav ? { top: nav.top, bottom: nav.bottom } : null,
      leadWidth: lead?.width ?? null,
    };
  });
  if (state.documentWidth > state.viewport + 1 || state.bodyWidth > state.viewport + 1) throw new Error(`${label}: horizontal overflow ${JSON.stringify(state)}`);
  if (!state.composer || state.composer.top < 0 || state.composer.bottom > page.viewportSize().height + 1) throw new Error(`${label}: composer is not visible ${JSON.stringify(state)}`);
  if (state.nav && state.composer.bottom > state.nav.top + 1) throw new Error(`${label}: composer overlaps navigation ${JSON.stringify(state)}`);
  if (state.leadWidth !== null && state.leadWidth < 210) throw new Error(`${label}: assistant response wraps too narrowly ${JSON.stringify(state)}`);
}

async function assertAxe(page, label) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  if (results.violations.length) {
    throw new Error(`${label}: ${JSON.stringify(results.violations.map((violation) => ({ id: violation.id, impact: violation.impact, targets: violation.nodes.map((node) => node.target) })))}`);
  }
}

async function sendQuestion(page, question) {
  const composer = page.getByLabel("Ask Wealth Copilot");
  await composer.fill(question);
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

async function evaluateViewport(viewport) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, serviceWorkers: "allow", reducedMotion: "reduce" });
  await context.addInitScript(() => {
    delete window.SpeechRecognition;
    delete window.webkitSpeechRecognition;
  });
  const page = await context.newPage();
  let mode = "normal";
  let responseCount = 0;
  const runtimeErrors = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error" && !message.text().includes("500")) runtimeErrors.push(message.text()); });

  await page.route("**/api/backend/v1/copilot**", async (route, request) => {
    if (request.method() === "GET") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(bootstrap) });
    responseCount += 1;
    if (mode === "error") return route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "fixture failure" }) });
    if (mode === "loading") await new Promise((resolve) => setTimeout(resolve, 700));
    const answer = mode === "long" ? longAnswer : `${normalAnswer} Exchange ${responseCount} is complete.`;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(reply(answer, responseCount, ["Why is HDFC important to my portfolio?", "Research recent HDFC developments"])),
    });
  });

  try {
    await page.goto(new URL("/copilot", baseUrl).href, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.getByRole("heading", { name: "Talk to your wealth agent" }).waitFor();
    await page.getByText("The agent already has today’s context.", { exact: true }).waitFor();
    await page.getByText("Live call is not configured yet.", { exact: true }).waitFor();
    if (await page.locator('[aria-label="Suggested prompts"] button').count() < 3) throw new Error(`${viewport.name}: fresh state needs at least three prompts`);
    if (!(await page.getByRole("button", { name: "Start voice input" }).first().isDisabled())) throw new Error(`${viewport.name}: unavailable voice control must stay disabled`);
    if (!(await page.getByRole("button", { name: "Call your wealth agent" }).isDisabled())) throw new Error(`${viewport.name}: unconfigured call must stay disabled`);
    await assertLayout(page, `${viewport.name} fresh`);
    await assertAxe(page, `${viewport.name} fresh`);
    await page.screenshot({ path: `${artifactPath}${viewport.name}-fresh.png`, fullPage: true });

    const composer = page.getByLabel("Ask Wealth Copilot");
    await composer.focus();
    await page.waitForTimeout(100);
    const keyboardState = await page.evaluate(() => ({
      navOpacity: getComputedStyle(document.querySelector("[data-mobile-nav]")).opacity,
      composerBottom: document.querySelector(".copilot-composer-dock form").getBoundingClientRect().bottom,
      viewportHeight: window.innerHeight,
    }));
    if (keyboardState.navOpacity !== "0" || keyboardState.composerBottom > keyboardState.viewportHeight + 1) throw new Error(`${viewport.name}: keyboard focus layout failed ${JSON.stringify(keyboardState)}`);
    await page.getByRole("heading", { name: "Talk to your wealth agent" }).click();

    await sendQuestion(page, "What deserves my attention right now?");
    await page.getByText(/Exchange 1 is complete/).waitFor();
    if (await page.locator('[aria-label="Suggested follow-ups"] button').count() !== 2) throw new Error(`${viewport.name}: conversation should show two follow-ups`);
    await assertLayout(page, `${viewport.name} one response`);

    await page.getByRole("link", { name: "Portfolio", exact: true }).click();
    await page.getByRole("link", { name: "Copilot", exact: true }).click();
    await page.getByText("What deserves my attention right now?", { exact: true }).waitFor();
    await page.getByText(/Exchange 1 is complete/).waitFor();

    for (let index = 2; index <= 5; index += 1) {
      mode = "normal";
      await sendQuestion(page, `Follow-up question ${index}`);
      await page.getByText(new RegExp(`Exchange ${index} is complete`)).waitFor();
    }
    if (await page.locator(".copilot-message-timeline article").count() !== 10) throw new Error(`${viewport.name}: expected a 10-message conversation`);
    await assertLayout(page, `${viewport.name} ten messages`);

    mode = "long";
    await sendQuestion(page, "Give me the long research response");
    const lastAssistant = page.locator('article[aria-label="Wealth Copilot"]').last();
    await lastAssistant.getByText("Full research", { exact: true }).waitFor();
    const lead = lastAssistant.locator("p").first();
    const leadText = await lead.innerText();
    if (leadText.length > 600) throw new Error(`${viewport.name}: primary answer is too long (${leadText.length})`);
    if ((await page.locator("body").innerText()).includes("Based on the current dashboard data and system state")) throw new Error(`${viewport.name}: internal-sounding preamble is visible`);
    if (await lastAssistant.getByText(/Research observation 100/).isVisible().catch(() => false)) throw new Error(`${viewport.name}: long research is expanded by default`);
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await assertLayout(page, `${viewport.name} long response`);
    await assertAxe(page, `${viewport.name} long response`);
    await page.screenshot({ path: `${artifactPath}${viewport.name}-long.png`, fullPage: true });

    mode = "loading";
    await sendQuestion(page, "Show the loading state");
    await page.getByText("Checking your portfolio and today’s context…", { exact: true }).waitFor();
    await assertLayout(page, `${viewport.name} loading`);
    await page.getByText(/Exchange 7 is complete/).waitFor();

    mode = "error";
    await sendQuestion(page, "Show the error state");
    await page.getByText(/Wealth Copilot could not answer right now/).waitFor();
    await assertLayout(page, `${viewport.name} error`);
    mode = "normal";

    await page.locator('summary[aria-label="Conversation actions"]').click();
    await page.getByRole("button", { name: "Clear conversation", exact: true }).click();
    await page.getByRole("heading", { name: "Talk to your wealth agent" }).waitFor();
    await assertLayout(page, `${viewport.name} cleared`);
    if (runtimeErrors.length) throw new Error(`${viewport.name}: runtime errors ${runtimeErrors.join(" | ")}`);

    return { viewport: viewport.name, longFixtureWords: longAnswer.trim().split(/\s+/).length, conversationMessages: 10, persisted: true, clearLifecycle: true };
  } finally {
    await context.close();
  }
}

try {
  const results = [];
  for (const viewport of viewports) results.push(await evaluateViewport(viewport));
  console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
  await browser.close();
}
