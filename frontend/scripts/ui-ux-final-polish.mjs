import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const baseUrl = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const artifactDirectory = new URL("../../artifacts/ui-ux-final-polish/after/", import.meta.url);
const artifactPath = fileURLToPath(artifactDirectory);
await mkdir(artifactDirectory, { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

const viewports = [
  { name: "320", width: 320, height: 568 },
  { name: "360", width: 360, height: 800 },
  { name: "390", width: 390, height: 844 },
  { name: "430", width: 430, height: 932 },
  { name: "768", width: 768, height: 1024 },
  { name: "1024", width: 1024, height: 900 },
  { name: "1440", width: 1440, height: 1000 },
];

const destinations = [
  { label: "Today", href: "/", ready: /Portfolio today/i },
  { label: "Portfolio", href: "/portfolio", ready: /Returns by horizon/i },
  { label: "Copilot", href: "/copilot", ready: /Talk to your wealth agent/i },
  { label: "Alerts", href: "/alerts", ready: /Nothing material needs your attention right now|Open case/i },
  { label: "Timeline", href: "/timeline", ready: /checkpoints complete/i },
];

const fixedAlert = {
  case_id: "final-polish-case",
  event_id: "evt-final-polish",
  instrument: "TCS",
  company: "Tata Consultancy Services",
  headline: "TCS moved sharply while its sector remained comparatively steady.",
  occurred_at: "2026-08-23T10:12:00+05:30",
  updated_at: "2026-08-23T10:14:00+05:30",
  category: "attention",
  status: "OPEN",
  priority: "HIGH",
  decision: "ALERT",
  notification_required: true,
  price_change_pct: -4.2,
  sector_change_pct: -0.8,
  index_change_pct: -0.3,
  direct_exposure_pct: 8.4,
  sector_exposure_pct: 21.7,
  portfolio_impact_pct: -0.35,
  relevance_score: 91,
  reason: "A direct holding crossed the movement threshold and represents meaningful portfolio exposure.",
};

const alertInboxFixture = {
  day_id: "day-final-polish",
  run_id: "run-final-polish",
  generated_at: "2026-08-23T10:14:00+05:30",
  counts: { attention: 1, investigating: 0, monitoring: 0, ignored: 0 },
  items: [fixedAlert],
};

const alertDetailFixture = {
  day_id: "day-final-polish",
  run_id: "run-final-polish",
  generated_at: "2026-08-23T10:14:00+05:30",
  case: {},
  item: fixedAlert,
  intraday: [
    { timestamp: "2026-08-23T09:15:00+05:30", price: 3312, volume: 1000 },
    { timestamp: "2026-08-23T09:45:00+05:30", price: 3278, volume: 1400 },
    { timestamp: "2026-08-23T10:12:00+05:30", price: 3173, volume: 2400 },
  ],
  benchmark: { index_name: "Nifty 50", change_pct: -0.3, last_price: 24500 },
  sector: { sector: "Information Technology", change_pct: -0.8 },
  assessment: {
    trace: [
      { stage: "EVENT_DETECTED", outcome: "triggered", details: {} },
      { stage: "PORTFOLIO_CHECK", outcome: "direct", details: {} },
      { stage: "MARKET_INVESTIGATION", outcome: "complete", details: {} },
      { stage: "RELEVANCE", outcome: "91.00/100", details: {} },
      { stage: "DECISION", outcome: "ALERT", details: {} },
    ],
  },
};

async function assertNoOverflow(page, label) {
  const geometry = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  if (geometry.document > geometry.viewport + 1 || geometry.body > geometry.viewport + 1) {
    throw new Error(`${label} overflows horizontally: ${JSON.stringify(geometry)}`);
  }
}

async function assertTouchTargets(page, label) {
  const undersized = await page.locator("main a:visible, main button:visible, main summary:visible, nav:visible a:visible").evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return { name: node.getAttribute("aria-label") ?? node.textContent?.trim().slice(0, 50), width: Math.round(rect.width), height: Math.round(rect.height) };
    }).filter((target) => target.width < 44 || target.height < 44),
  );
  if (undersized.length) throw new Error(`${label} has targets below 44px: ${JSON.stringify(undersized)}`);
}

async function assertBottomClearance(page, label) {
  const overlap = await page.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
    const nav = document.querySelector('nav[aria-label="Primary navigation"]');
    const main = document.querySelector("main");
    if (!nav || !main || getComputedStyle(nav).position !== "fixed") return null;
    const navTop = nav.getBoundingClientRect().top;
    const content = [...main.querySelectorAll("*")].filter((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && style.position !== "fixed" && !node.closest("nav");
    });
    const lowest = content.reduce((best, node) => node.getBoundingClientRect().bottom > best.getBoundingClientRect().bottom ? node : best, content[0]);
    if (!lowest) return null;
    const rect = lowest.getBoundingClientRect();
    return rect.bottom > navTop + 1 ? { navTop: Math.round(navTop), contentBottom: Math.round(rect.bottom), text: lowest.textContent?.trim().slice(0, 60) } : null;
  });
  if (overlap) throw new Error(`${label} ends behind navigation: ${JSON.stringify(overlap)}`);
}

async function assertFocusVisible(page, label) {
  await page.keyboard.press("Tab");
  const focus = await page.evaluate(() => {
    const element = document.activeElement;
    if (!(element instanceof HTMLElement) || element === document.body) return null;
    const style = getComputedStyle(element);
    return { tag: element.tagName, outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  if (!focus || focus.outlineStyle === "none" || focus.outlineWidth === "0px") {
    throw new Error(`${label} does not expose a visible first keyboard focus: ${JSON.stringify(focus)}`);
  }
}

async function assertAxe(page, label) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  if (results.violations.length) {
    const summary = results.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => ({ target: node.target, html: node.html, failure: node.failureSummary })),
    }));
    throw new Error(`${label} accessibility violations: ${JSON.stringify(summary)}`);
  }
}

async function evaluateViewport(viewport) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, serviceWorkers: "allow" });
  const page = await context.newPage();
  const runtimeErrors = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") runtimeErrors.push(message.text()); });
  const results = [];

  try {
    for (const destination of destinations) {
      await page.goto(new URL(destination.href, baseUrl).href, { waitUntil: "domcontentloaded", timeout: 30_000 });
      await page.locator("main h1").waitFor({ timeout: 30_000 });
      await page.getByText(destination.ready).first().waitFor({ timeout: 30_000 });
      await page.waitForTimeout(250);
      const label = `${viewport.name}px ${destination.label}`;
      const navLinks = page.locator('nav[aria-label="Primary navigation"]:visible a');
      if (await navLinks.count() !== 5) throw new Error(`${label} does not show five destinations`);
      await assertNoOverflow(page, label);
      if (viewport.width <= 430) await assertTouchTargets(page, label);
      if (viewport.width < 1024) await assertBottomClearance(page, label);
      await assertFocusVisible(page, label);
      await assertAxe(page, label);
      results.push({ destination: destination.label, heading: await page.locator("main h1").innerText() });

      if (["390", "430", "768", "1440"].includes(viewport.name)) {
        await page.screenshot({ path: `${artifactPath}${viewport.name}-${destination.label.toLowerCase()}.png`, fullPage: true });
      }
    }
    if (runtimeErrors.length) throw new Error(`${viewport.name}px runtime errors: ${runtimeErrors.join(" | ")}`);
    return { viewport: viewport.name, results };
  } finally {
    await context.close();
  }
}

async function evaluateContractsAndStates() {
  const portfolioResponse = await fetch(new URL("/api/backend/v1/portfolio", baseUrl));
  if (!portfolioResponse.ok) throw new Error(`Portfolio fixture fetch failed: ${portfolioResponse.status}`);
  const portfolioPayload = await portfolioResponse.json();
  const portfolio = portfolioPayload.portfolio;
  const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });

  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: "allow" });
  const page = await context.newPage();
  try {
    await page.goto(new URL("/portfolio", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.getByText("Returns by horizon", { exact: true }).waitFor();
    for (const expected of [inr.format(portfolio.portfolio_value), inr.format(portfolio.day_pnl ?? 0), inr.format(portfolio.unrealized_pnl)]) {
      if (!(await page.locator("body").innerText()).includes(expected)) throw new Error(`Contract value is not rendered unchanged: ${expected}`);
    }

    let alertState = "empty";
    await page.route("**/api/backend/v1/alerts**", async (route) => {
      const url = new URL(route.request().url());
      const emptyInbox = { ...alertInboxFixture, counts: { attention: 0, investigating: 0, monitoring: 0, ignored: 0 }, items: [] };
      const body = url.pathname.endsWith("/final-polish-case") ? alertDetailFixture : alertState === "empty" ? emptyInbox : alertInboxFixture;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(new URL("/alerts", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.getByText("Nothing material needs your attention right now", { exact: true }).waitFor();
    await assertNoOverflow(page, "empty Alerts");
    await assertAxe(page, "empty Alerts");
    await page.screenshot({ path: `${artifactPath}390-alerts-empty.png`, fullPage: true });

    alertState = "populated";
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByText("Tata Consultancy Services", { exact: true }).waitFor();
    await page.getByText("ALERT", { exact: true }).waitFor();
    await assertNoOverflow(page, "populated Alerts");
    await assertAxe(page, "populated Alerts");
    await page.screenshot({ path: `${artifactPath}390-alerts-populated.png`, fullPage: true });

    await page.goto(new URL("/alerts/final-polish-case", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.getByText("Relevance 91", { exact: true }).waitFor();
    await page.getByText("Market movement detected", { exact: true }).waitFor();
    if (await page.getByText("EVENT_DETECTED", { exact: true }).count()) throw new Error("Raw trace stage is visible");
    await assertNoOverflow(page, "alert detail deep link");
    await assertAxe(page, "alert detail deep link");
    await page.screenshot({ path: `${artifactPath}390-alert-detail.png`, fullPage: true });
  } finally {
    await context.close();
  }
}

async function evaluatePersistenceAndPwa() {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: "allow", reducedMotion: "reduce" });
  const page = await context.newPage();
  try {
    await page.route("**/api/backend/v1/copilot", async (route, request) => {
      if (request.method() !== "POST") return route.continue();
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        conversation_id: "polish-conversation", message_id: "polish-answer", mode: "chat", route: "explain",
        answer: "Your portfolio context remains attached across destinations.", context: {}, sources: [], suggested_questions: [],
        used_search: false, used_existing_context: true, fallback_used: false, agent_trace: [], created_at: new Date().toISOString(),
      }) });
    });
    await page.goto(new URL("/copilot", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.getByLabel("Ask Wealth Copilot").fill("Does my context survive navigation?");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.locator("[data-copilot-answer-lead]", { hasText: "Your portfolio context remains attached across destinations." }).waitFor();
    await page.goto(new URL("/portfolio", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.goto(new URL("/copilot", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.getByText("Does my context survive navigation?", { exact: true }).waitFor();
    const manifestHref = await page.locator('link[rel="manifest"]').getAttribute("href");
    if (!manifestHref) throw new Error("Manifest link is missing");
    const workerRegistration = await page.evaluate(async () => {
      if (!("serviceWorker" in navigator)) return false;
      const registration = await navigator.serviceWorker.ready;
      return Boolean(registration.active?.scriptURL.endsWith("/sw.js"));
    });
    if (!workerRegistration) throw new Error("Production service worker did not become active");
    const activeAnimations = await page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === "running").length);
    if (activeAnimations) throw new Error(`Reduced-motion mode still has ${activeAnimations} running animations`);
    return { manifestHref, workerRegistration, copilotPersistent: true, reducedMotion: true };
  } finally {
    await context.close();
  }
}

try {
  const responsive = [];
  for (const viewport of viewports) responsive.push(await evaluateViewport(viewport));
  await evaluateContractsAndStates();
  const product = await evaluatePersistenceAndPwa();
  console.log(JSON.stringify({ status: "passed", responsive, product }, null, 2));
} finally {
  await browser.close();
}
