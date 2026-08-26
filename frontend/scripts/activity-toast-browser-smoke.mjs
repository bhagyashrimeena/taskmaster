import { chromium } from "playwright-core";

const web = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const sizes = [
  { width: 360, height: 740 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
];
const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

async function clockState(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/backend/v1/day/clock", { cache: "no-store" });
    if (!response.ok) throw new Error(`Clock request failed: ${response.status}`);
    return response.json();
  });
}

try {
  const results = [];
  for (const viewport of sizes) {
    const context = await browser.newContext({ viewport, reducedMotion: "reduce", isMobile: true, hasTouch: true });
    const page = await context.newPage();
    await page.goto(`${web}/timeline`, { waitUntil: "networkidle", timeout: 60_000 });

    const restart = page.getByRole("button", { name: "Restart", exact: true });
    if (!(await restart.isVisible())) {
      const playAll = page.getByRole("button", { name: "Play all", exact: true });
      if (await playAll.isVisible()) {
        await playAll.click();
        await page.waitForTimeout(250);
        const pause = page.getByRole("button", { name: "Pause", exact: true });
        if (await pause.isVisible()) await pause.click();
      }
    }

    await page.getByRole("button", { name: "Restart", exact: true }).click();
    await page.getByRole("button", { name: "Restart at 07:00", exact: true }).click();

    const toast = page.locator('[data-testid="activity-toast"]');
    await page.getByText("Financial day restarted", { exact: true }).waitFor({ timeout: 10_000 });
    if ((await toast.count()) !== 1) throw new Error(`Expected one notification at ${viewport.width}px`);
    const restartNotice = await toast.innerText();
    if (!/Financial day restarted/i.test(restartNotice)) throw new Error(`Restart notification was not meaningful: ${restartNotice}`);

    const restarted = await clockState(page);
    if (restarted.status !== "paused" || restarted.current_time !== "07:00" || restarted.completed_checkpoint_ids.length !== 0) {
      throw new Error(`Restart did not pause cleanly: ${JSON.stringify(restarted)}`);
    }

    const geometry = await page.evaluate(() => {
      const header = document.querySelector("header")?.getBoundingClientRect();
      const nav = document.querySelector("[data-mobile-nav]")?.getBoundingClientRect();
      const notice = document.querySelector('[data-testid="activity-toast"]')?.getBoundingClientRect();
      return {
        overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        belowHeader: Boolean(header && notice && notice.top >= header.bottom),
        overlapsNav: Boolean(nav && notice && notice.bottom > nav.top && notice.top < nav.bottom),
        toastCount: document.querySelectorAll('[data-testid="activity-toast"]').length,
      };
    });
    if (geometry.overflow || !geometry.belowHeader || geometry.overlapsNav || geometry.toastCount !== 1) {
      throw new Error(`Unsafe notification geometry: ${JSON.stringify(geometry)}`);
    }

    await page.getByRole("button", { name: /Dismiss Financial day restarted/i }).click();
    await page.getByRole("button", { name: /Run next update: Morning Pulse at 07:00/i }).click();
    await page.getByText("Morning brief is ready", { exact: true }).waitFor({ timeout: 15_000 });

    const deadline = Date.now() + 10_000;
    let advanced = await clockState(page);
    while (advanced.status === "running" && Date.now() < deadline) {
      await page.waitForTimeout(100);
      advanced = await clockState(page);
    }
    if (advanced.status !== "paused" || advanced.completed_checkpoint_ids.join(",") !== "morning" || advanced.next_checkpoint !== "08:00") {
      throw new Error(`Next update advanced the wrong amount: ${JSON.stringify(advanced)}`);
    }
    if ((await toast.count()) !== 1) throw new Error("Completed update notifications stacked");

    results.push({ viewport, restarted: restarted.status, completed: advanced.completed_checkpoint_ids, notification: await toast.innerText(), geometry });
    await context.close();
  }
  console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
  await browser.close();
}
