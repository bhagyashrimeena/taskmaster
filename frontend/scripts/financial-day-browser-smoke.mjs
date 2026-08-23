import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const web = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const api = process.env.WEALTH_COPILOT_API_URL ?? "http://127.0.0.1:8001/api/v1";
const artifacts = new URL("../../artifacts/financial-day-controls/", import.meta.url);
await mkdir(artifacts, { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce", serviceWorkers: "block" });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });

async function json(path, method = "GET") {
  const response = method === "POST" ? await page.request.post(`${api}${path}`) : await page.request.get(`${api}${path}`);
  if (!response.ok()) throw new Error(`${method} ${path} returned ${response.status()}`);
  return response.json();
}

async function noOverflow(label) {
  const geometry = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }));
  if (geometry.document > geometry.width + 1 || geometry.body > geometry.width + 1) throw new Error(`${label} overflow: ${JSON.stringify(geometry)}`);
}

try {
  await json("/simulation/scenarios/hdfc-company-shock", "POST");
  await page.goto(`${web}/timeline`, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.getByTestId("day-clock-controls").waitFor();
  const before = await json("/day/clock");
  await page.getByRole("button", { name: "Start the day", exact: true }).click();
  await page.getByRole("button", { name: "Pause the day", exact: true }).waitFor();
  await page.getByRole("button", { name: "Pause the day", exact: true }).click();
  await page.getByRole("button", { name: "Resume the day", exact: true }).waitFor();
  await page.getByRole("button", { name: "Resume the day", exact: true }).click();

  const morning = page.locator("li", { hasText: "Morning Pulse" });
  await morning.getByText("complete", { exact: true }).waitFor({ timeout: 30_000 });
  await page.getByRole("button", { name: "Restart the day", exact: true }).click();
  await page.getByRole("dialog", { name: "Restart the day?" }).waitFor();
  await page.getByRole("button", { name: "Restart and start", exact: true }).click();
  await page.getByRole("button", { name: "Pause the day", exact: true }).waitFor();
  const afterRestart = await json("/day");
  if (afterRestart.run_id === before.run_id) throw new Error("Restart did not create a fresh financial-day run");

  const toast = page.getByTestId("proactive-alert-toast");
  try {
    await toast.waitFor({ timeout: 60_000 });
  } catch (error) {
    const diagnostic = {
      clock: await json("/day/clock"),
      alerts: await json("/alerts"),
      seen: await page.evaluate(() => sessionStorage.getItem("wealth-copilot-seen-alerts-v1")),
      errors,
    };
    throw new Error(`${error.message}\n${JSON.stringify(diagnostic, null, 2)}`);
  }
  await toast.getByRole("button", { name: "View alert", exact: true }).click();
  try {
    await page.getByRole("heading", { name: /HDFC Bank/i }).first().waitFor({ timeout: 30_000 });
  } catch (error) {
    throw new Error(`${error.message}\n${JSON.stringify({ url: page.url(), body: (await page.locator("body").innerText()).slice(-1600), errors }, null, 2)}`);
  }
  await noOverflow("390px alert detail");
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  if (axe.violations.length) throw new Error(`Accessibility violations: ${axe.violations.map((item) => item.id).join(", ")}`);
  await page.screenshot({ path: fileURLToPath(new URL("390-proactive-alert.png", artifacts)), fullPage: true });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${web}/timeline`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("day-clock-controls").waitFor();
  await noOverflow("1440px Timeline");
  await page.screenshot({ path: fileURLToPath(new URL("1440-timeline.png", artifacts)), fullPage: true });
  if (errors.length) throw new Error(errors.join(" | "));
  console.log(JSON.stringify({ status: "passed", controls: ["start", "pause", "resume", "restart"], proactiveAlert: true, viewports: [390, 1440] }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
