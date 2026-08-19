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

async function api(path, options = {}) {
  const response = options.method === "POST"
    ? await page.request.post(`http://127.0.0.1:8001/api/v1${path}`, { data: options.data })
    : await page.request.get(`http://127.0.0.1:8001/api/v1${path}`);
  if (!response.ok()) throw new Error(`${path} returned ${response.status()}`);
  return response.json();
}

async function waitForClock(expectedTime, expectedStatus = "paused") {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const state = await api("/presentation-clock");
    if (state.current_time === expectedTime && state.status === expectedStatus) return state;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Clock did not reach ${expectedTime}`);
}

async function openPresentation() {
  await page.goto("http://127.0.0.1:3001/?presentation=true", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByTestId("presentation-clock").waitFor({ timeoutMs: 30000 });
}

async function assertBeforeEvent(label) {
  await openPresentation();
  if (await page.getByTestId("pre-event-monitoring").count() !== 1) throw new Error(`${label}: monitoring state missing`);
  if (await page.getByTestId("hero-event").count() !== 0) throw new Error(`${label}: future event leaked`);
  if (await page.getByTestId("proactive-event-alert").count() !== 0) throw new Error(`${label}: proactive alert leaked`);
  const timeline = await page.getByTestId("day-step-event").innerText();
  if (!timeline.includes("Market Watch")) throw new Error(`${label}: future event label leaked`);
}

try {
  await api("/simulation/scenarios/hdfc-company-shock", { method: "POST" });
  await api("/presentation-clock/restart", { method: "POST" });
  await api("/presentation-clock/advance", { method: "POST", data: { minutes: 1 } });
  await waitForClock("07:01");
  await assertBeforeEvent("07:01");

  await api("/presentation-clock/advance", { method: "POST", data: { minutes: 60 } });
  await waitForClock("08:01");
  await assertBeforeEvent("08:01");

  await api("/presentation-clock/restart", { method: "POST" });
  await api("/presentation-clock/advance", { method: "POST", data: { minutes: 316 } });
  await waitForClock("12:16");
  await assertBeforeEvent("12:16");

  await page.getByTestId("clock-next").click();
  await waitForClock("12:17");
  await page.getByTestId("hero-event").waitFor({ timeoutMs: 30000 });
  await page.getByTestId("proactive-event-alert").waitFor({ timeoutMs: 30000 });

  await api("/presentation-clock/advance", { method: "POST", data: { minutes: 193 } });
  await waitForClock("15:30");
  await openPresentation();
  await page.getByTestId("financial-day").getByText(/closing portfolio move explained/i).waitFor({ timeoutMs: 30000 });

  await api("/presentation-clock/advance", { method: "POST", data: { minutes: 270 } });
  await waitForClock("20:00");
  await openPresentation();
  await page.getByText("Your financial day in 90 seconds", { exact: true }).waitFor({ timeoutMs: 30000 });

  await api("/presentation-clock/advance", { method: "POST", data: { minutes: 61 } });
  await waitForClock("21:01", "complete");
  await openPresentation();
  await page.getByTestId("wealth-story-card").waitFor({ timeoutMs: 30000 });
  if (errors.length) throw new Error(errors.join("\n"));

  console.log(JSON.stringify({
    status: "passed",
    timestamps: ["07:01", "08:01", "12:16", "12:17", "15:30", "20:00", "21:01"],
    futureEventHiddenBefore1217: true,
    consoleErrors: errors,
  }, null, 2));
} finally {
  await browser.close();
}
