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

async function waitForClockIdle(expectedTime) {
  await page.waitForFunction(
    async (time) => {
      const response = await fetch("/api/backend/v1/presentation-clock", { cache: "no-store" });
      const clock = await response.json();
      return clock.current_time === time && clock.status === "paused";
    },
    expectedTime,
    { timeout: 45000 },
  );
}

async function clickNextAndWait(time, stepId) {
  await page.getByTestId("clock-next").click();
  await waitForClockIdle(time);
  await page.getByTestId(`day-step-${stepId}`).locator(".day-step__marker svg").waitFor({ timeout: 45000 });
}

try {
  const scenario = await page.request.post(
    "http://127.0.0.1:8001/api/v1/simulation/scenarios/hdfc-company-shock",
  );
  if (!scenario.ok()) throw new Error(`HDFC scenario returned ${scenario.status()}`);

  await page.goto("http://127.0.0.1:3001/?presentation=true", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.getByTestId("presentation-clock").waitFor();
  await page.getByTestId("clock-restart").click();
  await waitForClockIdle("07:00");

  // The clock can genuinely play and pause before the deterministic judge path.
  await page.getByTestId("clock-play-pause").click();
  await page.getByRole("button", { name: "Pause financial day" }).waitFor();
  await page.getByTestId("day-step-morning").locator(".day-step__marker svg").waitFor({ timeout: 45000 });
  await page.getByTestId("clock-play-pause").click();
  await page.getByRole("button", { name: "Play financial day" }).waitFor();

  // Restart is the only backwards operation, keeping the golden path repeatable.
  await page.getByTestId("clock-restart").click();
  await waitForClockIdle("07:00");
  await clickNextAndWait("07:01", "morning");
  await clickNextAndWait("08:00", "health");
  await page.getByTestId("clock-next").click();
  await page.getByTestId("proactive-event-alert").waitFor({ timeout: 45000 });
  await waitForClockIdle("12:17");
  await page.getByTestId("day-step-event").locator(".day-step__marker svg").waitFor({ timeout: 45000 });
  await page.getByText("Wealth Copilot found something that deserves attention", { exact: true }).waitFor();
  await page.screenshot({ path: "../artifacts/presentation-clock-hdfc-alert.png", fullPage: true });

  const dayResponse = await page.request.get("http://127.0.0.1:8001/api/v1/day");
  const day = await dayResponse.json();
  const clockResponse = await page.request.get("http://127.0.0.1:8001/api/v1/presentation-clock");
  const clock = await clockResponse.json();
  if (day.run_mode !== "presentation") throw new Error(`Unexpected run mode: ${day.run_mode}`);
  if (day.events_detected.length !== 1) throw new Error(`Expected one event, got ${day.events_detected.length}`);
  if (day.events_detected[0].run_id !== day.run_id) throw new Error("Event escaped the shared financial-day run");
  if (clock.current_time !== "12:17") throw new Error(`Unexpected clock time: ${clock.current_time}`);
  if (clock.completed_checkpoint_ids.join(",") !== "morning,health,event") {
    throw new Error(`Unexpected completed checkpoints: ${clock.completed_checkpoint_ids.join(",")}`);
  }

  await page.goto("http://127.0.0.1:3001/", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText("Simulated Portfolio", { exact: true }).waitFor();
  if (await page.getByTestId("presentation-clock").count()) {
    throw new Error("Presentation clock leaked into normal product mode");
  }
  if (await page.getByTestId("proactive-event-alert").count()) {
    throw new Error("Presentation alert leaked into normal product mode");
  }
  if (errors.length) throw new Error(errors.join("\n"));

  console.log(JSON.stringify({
    status: "passed",
    currentTime: clock.current_time,
    completedCheckpoints: clock.completed_checkpoint_ids,
    decision: day.events_detected[0].decision,
    relevance: day.events_detected[0].relevance_score,
    exposure: day.events_detected[0].affected_portfolio_percentage,
    oneSharedRun: day.events_detected[0].run_id === day.run_id,
    normalModeControlsHidden: true,
    consoleErrors: errors,
  }, null, 2));
} finally {
  await browser.close();
}
