import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const baseUrl = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const artifactDirectory = new URL("../../artifacts/user-evaluation/", import.meta.url);
const artifactPath = fileURLToPath(artifactDirectory);
await mkdir(artifactDirectory, { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

const destinations = [
  { label: "Today", href: "/", expected: /Portfolio today/i, ready: /Portfolio today/i },
  { label: "Portfolio", href: "/portfolio", expected: /Your money, in context/i, ready: /Returns by horizon/i },
  { label: "Copilot", href: "/copilot", expected: /Ask about your portfolio/i, ready: /Talk about today/i },
  { label: "Alerts", href: "/alerts", expected: /What crossed the threshold/i, ready: /Nothing material needs your attention right now|Open case/i },
  { label: "Timeline", href: "/timeline", expected: /Context that compounds all day/i, ready: /checkpoints complete/i },
];

async function evaluateViewport(name, viewport) {
  // Service-worker behavior is covered by ui-ux-final-polish.mjs; blocking it here keeps the Copilot POST fixture deterministic.
  const context = await browser.newContext({ viewport, serviceWorkers: "block" });
  const page = await context.newPage();
  const errors = [];
  let mockedPosts = 0;
  const observedPosts = [];
  page.on("request", (request) => { if (request.method() === "POST") observedPosts.push(request.url()); });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });

  await page.route("**/api/backend/v1/copilot**", async (route, request) => {
    if (request.method() !== "POST") return route.continue();
    mockedPosts += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        conversation_id: "evaluation-conversation",
        message_id: "evaluation-answer",
        mode: "chat",
        route: "explain",
        answer: "Your portfolio context remains attached across destinations.",
        context: {},
        sources: [],
        suggested_questions: [],
        used_search: false,
        used_existing_context: true,
        fallback_used: false,
        agent_trace: [],
        created_at: new Date().toISOString(),
      }),
    });
  });

  const results = [];
  try {
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.locator("main h1").waitFor({ timeout: 30_000 });

    const manifestHref = await page.locator('link[rel="manifest"]').getAttribute("href");
    if (!manifestHref) throw new Error("Manifest link is missing");

    const visibleNavigation = page.locator('nav[aria-label="Primary navigation"]:visible');
    if (await visibleNavigation.getByRole("link").count() !== 5) {
      throw new Error("Expected five visible primary destinations");
    }

    if (name === "mobile") {
      const touchTargets = await visibleNavigation.getByRole("link").evaluateAll((links) =>
        links.map((link) => Math.round(link.getBoundingClientRect().height)),
      );
      if (touchTargets.some((height) => height < 44)) {
        throw new Error(`Primary touch target below 44px: ${touchTargets.join(",")}`);
      }
    }

    for (const destination of destinations) {
      if (page.url() !== new URL(destination.href, baseUrl).href) {
        await visibleNavigation.getByRole("link", { name: destination.label, exact: true }).click();
      }
      await page.waitForURL(new URL(destination.href, baseUrl).href);
      await page.getByText(destination.expected).first().waitFor({ timeout: 30_000 });
      await page.getByText(destination.ready).first().waitFor({ timeout: 30_000 });
      await page.waitForTimeout(500);

      const geometry = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
      }));
      const horizontalOverflow = geometry.document > geometry.viewport + 1 || geometry.body > geometry.viewport + 1;
      if (horizontalOverflow) throw new Error(`${destination.label} overflows: ${JSON.stringify(geometry)}`);

      results.push({
        destination: destination.label,
        path: new URL(page.url()).pathname,
        heading: await page.locator("main h1").first().innerText(),
        horizontalOverflow,
      });
      await page.screenshot({
        path: `${artifactPath}${name}-${destination.label.toLowerCase()}.png`,
        fullPage: true,
      });
    }

    const workerRegistration = "covered-by-polish-suite";
    await page.goto(new URL("/copilot", baseUrl).href, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Ask about your portfolio" }).waitFor();
    await page.waitForFunction(() => !document.querySelector(".copilot-page > header p:last-child")?.textContent?.includes("Preparing"));
    const persistenceQuestion = "What deserves my attention right now?";
    await page.locator('[aria-label="Suggested questions"] button', { hasText: persistenceQuestion }).click();
    await page.locator('article[aria-label="You"]', { hasText: persistenceQuestion }).waitFor();
    await page.waitForTimeout(500);
    if (mockedPosts !== 1) throw new Error(`Expected one mocked Copilot POST, received ${mockedPosts}; observed ${JSON.stringify(observedPosts)} at ${page.url()}. Conversation text: ${(await page.locator("main").innerText()).slice(-1200)}`);
    await page.locator("[data-copilot-answer-lead]", { hasText: "Your portfolio context remains attached across destinations." }).waitFor();
    await visibleNavigation.getByRole("link", { name: "Portfolio", exact: true }).click();
    await visibleNavigation.getByRole("link", { name: "Copilot", exact: true }).click();
    await page.locator('article[aria-label="You"]', { hasText: persistenceQuestion }).waitFor();
    await page.locator("[data-copilot-answer-lead]", { hasText: "Your portfolio context remains attached across destinations." }).waitFor();

    if (errors.length) throw new Error(errors.join("\n"));
    return { name, viewport, manifestHref, workerRegistration, copilotPersistent: true, results, errors };
  } finally {
    await context.close();
  }
}

try {
  const evaluations = [];
  evaluations.push(await evaluateViewport("mobile", { width: 390, height: 844 }));
  evaluations.push(await evaluateViewport("desktop", { width: 1440, height: 1000 }));
  console.log(JSON.stringify({ status: "passed", evaluations }, null, 2));
} finally {
  await browser.close();
}
