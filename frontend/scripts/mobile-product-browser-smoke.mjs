import { chromium } from "playwright-core";

const web = process.env.WEALTH_COPILOT_WEB_URL ?? "http://127.0.0.1:3001";
const browser = await chromium.launch({ executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", headless: true });
const routes = ["/", "/portfolio", "/copilot", "/alerts", "/timeline"];
const results = [];

try {
  for (const viewport of [{ width: 360, height: 740 }, { width: 390, height: 844 }, { width: 430, height: 932 }]) {
    const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
    const page = await context.newPage();
    for (const route of routes) {
      await page.goto(`${web}${route}`, { waitUntil: "domcontentloaded", timeout: 30_000 });
      await page.locator("main h1").waitFor();
      const geometry = await page.evaluate(() => ({ viewport: innerWidth, body: document.body.scrollWidth, document: document.documentElement.scrollWidth }));
      if (geometry.body > geometry.viewport + 1 || geometry.document > geometry.viewport + 1) throw new Error(`${viewport.width}px ${route} overflow: ${JSON.stringify(geometry)}`);
      const nav = page.locator('[data-mobile-nav] a');
      if (await nav.count() !== 5) throw new Error(`${viewport.width}px ${route} does not expose five destinations`);
      const undersized = await nav.evaluateAll((links) => links.filter((link) => link.getBoundingClientRect().height < 44).length);
      if (undersized) throw new Error(`${viewport.width}px ${route} has undersized navigation targets`);
    }
    results.push({ viewport: `${viewport.width}x${viewport.height}`, routes: routes.length, overflow: false });
    await context.close();
  }
  console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
  await browser.close();
}
