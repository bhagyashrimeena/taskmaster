import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

await mkdir(new URL("../../artifacts/", import.meta.url), { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(`console: ${message.text()}`);
});
page.on("pageerror", (error) => errors.push(`page: ${error.message}`));

try {
  await page.goto("http://127.0.0.1:3001", { waitUntil: "networkidle", timeout: 30000 });
  await page.getByTestId("hero-event").waitFor();
  await page.getByTestId("ask-advisor-event").click();
  await page.getByTestId("advisor-sheet").waitFor();
  await page.screenshot({ path: "../artifacts/phase7-advisor-compose.png", fullPage: false });

  await page.getByTestId("prepare-advisor-packet").click();
  await page.getByText("Packet prepared", { exact: true }).waitFor();
  await page.getByTestId("advisor-sheet").getByText(
    "Your direct exposure is 18.01% and sector exposure is 28.01%.",
    { exact: true },
  ).waitFor();
  await page.getByTestId("review-advisor-email").click();
  await page.getByText("Review before sending", { exact: true }).waitFor();
  await page.locator(".email-preview").getByText(
    "Ananya Rao <advisor@example.com>",
    { exact: true },
  ).waitFor();
  await page.screenshot({ path: "../artifacts/phase7-advisor-review.png", fullPage: false });

  await page.getByTestId("confirm-send-advisor").click();
  await page.getByText("Waiting for advisor response", { exact: true }).waitFor();
  await page.getByTestId("advisor-reply").waitFor({ timeout: 12000 });
  await page.getByText("Advisor perspective", { exact: true }).waitFor();
  await page.screenshot({ path: "../artifacts/phase7-advisor-reply.png", fullPage: false });

  const day = await page.request.get("http://127.0.0.1:8001/api/v1/day");
  const dayState = await day.json();
  if (dayState.advisor_requests.at(-1)?.status !== "REPLIED") {
    throw new Error("Advisor reply was not persisted in FinancialDayState");
  }
  console.log(JSON.stringify({
    status: "passed",
    requestId: dayState.advisor_requests.at(-1).request_id,
    persistedResponses: dayState.advisor_responses.length,
    consoleErrors: errors,
  }, null, 2));
  if (errors.length) process.exitCode = 1;
} finally {
  await browser.close();
}
