import { chromium } from "playwright-core";

const frontend = "http://127.0.0.1:3001";
const edge = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const browser = await chromium.launch({
  executablePath: edge,
  headless: true,
});
const page = await browser.newPage();
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(`console: ${message.text()}`);
});
page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
page.on("response", (response) => {
  if (response.status() >= 400) errors.push(`http ${response.status()}: ${response.url()}`);
});

async function verifyPlayback(type) {
  const control = page.getByTestId(`${type}-audio`);
  await control.waitFor({ timeout: 30000 });
  const button = control.locator(".audio-listen-button");
  await page.waitForFunction(
    (id) => {
      const candidate = document.querySelector(`[data-testid="${id}"] .audio-listen-button`);
      return candidate && !candidate.hasAttribute("disabled") && !/Preparing audio/i.test(candidate.textContent || "");
    },
    `${type}-audio`,
    { timeout: 90000 },
  );
  if (!/^Play/i.test((await button.textContent()) || "")) {
    await button.click();
    await page.waitForFunction(
      (id) => /^Play/i.test(document.querySelector(`[data-testid="${id}"] .audio-listen-button`)?.textContent || ""),
      `${type}-audio`,
      { timeout: 90000 },
    );
  }
  await button.click();
  await page.waitForFunction(
    (id) => {
      const audio = document.querySelector(`[data-testid="${id}"] audio`);
      return audio instanceof HTMLAudioElement && !audio.paused && audio.currentTime > 0.2 && audio.duration > 1;
    },
    `${type}-audio`,
    { timeout: 15000 },
  );
  const state = await control.locator("audio").evaluate((audio) => ({
    paused: audio.paused,
    currentTime: audio.currentTime,
    duration: audio.duration,
    source: audio.currentSrc,
  }));
  await button.click();
  return state;
}

try {
  await page.goto(frontend, { waitUntil: "domcontentloaded", timeout: 30000 });
  const morning = await verifyPlayback("morning");
  const evening = await verifyPlayback("evening");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(JSON.stringify({
    status: "passed",
    provider: "Gemini TTS via Vertex ADC",
    morning,
    evening,
    browserErrors: errors,
  }, null, 2));
} finally {
  await browser.close();
}
