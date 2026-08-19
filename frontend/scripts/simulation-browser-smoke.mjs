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
page.on("response", (response) => {
  if (response.status() >= 400) errors.push(`http ${response.status()}: ${response.url()}`);
});

try {
  const hdfcResponse = await page.request.post(
    "http://127.0.0.1:8001/api/v1/simulation/scenarios/hdfc-company-shock",
  );
  if (!hdfcResponse.ok()) throw new Error(`HDFC scenario returned ${hdfcResponse.status()}`);

  await page.goto("http://127.0.0.1:3001/", { waitUntil: "domcontentloaded", timeout: 30000 });
  try {
    await page.getByText("Simulated Portfolio", { exact: true }).waitFor();
  } catch (error) {
    console.error(await page.locator("body").innerText());
    console.error(errors);
    await page.screenshot({ path: "../artifacts/simulation-browser-debug.png", fullPage: true });
    throw error;
  }
  await page.getByTestId("hero-event").getByText("ALERT", { exact: true }).waitFor();
  await page.getByText("HDFC Bank", { exact: true }).waitFor();
  await page.screenshot({ path: "../artifacts/simulation-hdfc-alert.png", fullPage: true });

  const hdfcDashboard = await page.request.get("http://127.0.0.1:8001/api/v1/dashboard");
  const hdfc = await hdfcDashboard.json();
  if (hdfc.portfolio.source.provider !== "simulated") throw new Error("Provider provenance missing");
  if (hdfc.portfolio.source.scenario_id !== "hdfc-company-shock") throw new Error("Scenario provenance missing");
  if (!hdfc.important_event.notification_required) throw new Error("HDFC scenario did not alert");

  const quietResponse = await page.request.post(
    "http://127.0.0.1:8001/api/v1/simulation/scenarios/quiet-market-day",
  );
  if (!quietResponse.ok()) throw new Error(`Quiet scenario returned ${quietResponse.status()}`);
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByTestId("quiet-market-state").waitFor();
  await page.getByText("Nothing needs your attention right now", { exact: true }).waitFor();
  await page.getByText("No event crossed the interruption threshold.", { exact: false }).waitFor();
  await page.screenshot({ path: "../artifacts/simulation-quiet-day.png", fullPage: true });

  const quietDashboard = await page.request.get("http://127.0.0.1:8001/api/v1/dashboard");
  const quiet = await quietDashboard.json();
  if (quiet.important_event.decision !== "IGNORE") throw new Error("Quiet scenario was not ignored");
  if (quiet.important_event.notification_required) throw new Error("Quiet scenario created a notification");

  const visibleText = await page.locator("body").innerText();
  const recommendations = visibleText.match(/\b(?:buy|sell|hold|rebalance)\b/gi) ?? [];
  const implementationWords = visibleText.match(/\b(?:demo|cached|deterministic|retained|fixture|provider|simulation)\b/gi) ?? [];
  if (recommendations.length) throw new Error(`Investment recommendation words found: ${recommendations.join(", ")}`);
  if (implementationWords.length) {
    const matchAt = visibleText.toLowerCase().indexOf(implementationWords[0].toLowerCase());
    throw new Error(`Implementation words found: ${implementationWords.join(", ")} near "${visibleText.slice(Math.max(0, matchAt - 80), matchAt + 120)}"`);
  }
  if (await page.getByTestId("presentation-clock").count()) throw new Error("Presentation control leaked into product mode");

  await page.goto("http://127.0.0.1:3001/?presentation=true", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByTestId("presentation-clock").waitFor();
  if (errors.length) throw new Error(errors.join("\n"));

  console.log(JSON.stringify({
    status: "passed",
    hdfc: {
      decision: hdfc.important_event.decision,
      exposure: hdfc.important_event.affected_portfolio_percentage,
      relevance: hdfc.important_event.relevance_score,
      checkpoint: hdfc.portfolio.source.checkpoint,
    },
    quiet: {
      decision: quiet.important_event.decision,
      notificationRequired: quiet.important_event.notification_required,
      checkpoint: quiet.portfolio.source.checkpoint,
    },
    consoleErrors: errors,
    recommendationWords: recommendations,
    implementationWords,
    presentationControlHiddenByDefault: true,
  }, null, 2));
} finally {
  await browser.close();
}
