import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

await mkdir(new URL("../../artifacts/", import.meta.url), { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(`console: ${message.text()}`);
});
page.on("pageerror", (error) => errors.push(`page: ${error.message}`));

try {
  const response = await page.request.get("http://127.0.0.1:8001/api/v1/dashboard");
  if (!response.ok()) throw new Error(`Dashboard API returned ${response.status()}`);
  const dashboard = await response.json();
  if (!dashboard.daily_brief.stories.length) throw new Error("No stories available");
  const simulatedProvider = dashboard.portfolio.source.provider === "simulated";
  for (const story of dashboard.daily_brief.stories) {
    if (/example\.(?:com|invalid)/i.test(story.source_url)) {
      throw new Error(`Placeholder source leaked: ${story.source_url}`);
    }
    if (!simulatedProvider && /simulated|scenario|demo/i.test(story.source_name)) {
      throw new Error(`Scenario source leaked: ${story.source_name}`);
    }
  }

  await page.goto("http://127.0.0.1:3001/", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText(/Demo portfolio/i).first().waitFor();
  await page.getByText(dashboard.daily_brief.stories[0].source_name, { exact: false }).first().waitFor();
  if (await page.getByTestId("presentation-clock").count()) {
    throw new Error("Presentation control leaked into normal product mode");
  }
  const visibleText = await page.locator("body").innerText();
  const implementationWords = visibleText.match(/\b(?:cached|deterministic|retained|fixture|provider|simulation|simulated)\b/gi) ?? [];
  const recommendations = visibleText.match(/\b(?:buy|sell|hold|rebalance)\s+(?:this|that|the|more|less|shares|position|allocation|it)\b/gi) ?? [];
  if (implementationWords.length) throw new Error(`Implementation words found: ${implementationWords.join(", ")}`);
  if (recommendations.length) throw new Error(`Recommendation words found: ${recommendations.join(", ")}`);
  const transientLinks = await page.locator('a[target="_blank"]').evaluateAll((links) =>
    links.filter((link) => /vertexaisearch\.cloud\.google\.com/i.test(link.getAttribute("href") ?? "")).length,
  );
  if (transientLinks) throw new Error(`${transientLinks} transient grounding citations rendered as clickable links`);
  if (errors.length) throw new Error(errors.join("\n"));
  await page.screenshot({ path: "../artifacts/normal-live-market-dashboard.png", fullPage: true });

  console.log(JSON.stringify({
    status: "passed",
    mode: simulatedProvider ? "simulated" : "live",
    provider: dashboard.daily_brief.stories[0].source_name,
    durableSourceLinks: await page.locator('a[target="_blank"]').count(),
    unavailableSourceLabels: await page.locator('.story-source--unavailable').count(),
    stories: dashboard.daily_brief.stories.length,
    freshness: dashboard.daily_brief.freshness.label,
    presentationControlHidden: true,
    consoleErrors: errors,
  }, null, 2));
} finally {
  await browser.close();
}
