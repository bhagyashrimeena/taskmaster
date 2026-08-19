import { chromium } from "playwright-core";

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

const results = [];

try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("http://127.0.0.1:3001/?presentation=true", { waitUntil: "domcontentloaded" });
    await page.getByTestId("story-1").getByRole("button", { name: "Explain" }).click();
    await page.getByTestId("copilot-sheet").waitFor();

    for (let cycle = 0; cycle < 10; cycle += 1) {
      await page.getByRole("button", { name: "Close Wealth Copilot" }).click();
      await page.waitForTimeout(50);
      const closed = await page.evaluate(() => ({
        sheet: document.querySelectorAll('[data-testid="copilot-sheet"]').length,
        dock: document.querySelectorAll(".copilot-dock").length,
        bodyOverflow: document.body.style.overflow,
        htmlOverflow: document.documentElement.style.overflow,
        centerTag: document.elementFromPoint(innerWidth / 2, innerHeight / 2)?.tagName,
      }));
      if (closed.sheet || closed.dock || closed.bodyOverflow || closed.htmlOverflow) throw new Error(`close cycle ${cycle + 1} left chat state: ${JSON.stringify(closed)}`);
      const launcher = page.getByRole("button", { name: "Open Wealth Copilot" });
      if (await launcher.count()) await launcher.click();
      else await page.getByTestId("story-1").getByRole("button", { name: "Explain" }).click();
      await page.getByTestId("copilot-sheet").waitFor();
      if (await page.locator('[data-testid="copilot-sheet"]').count() !== 1 || await page.locator('input[aria-label="Ask a follow-up"]').count() !== 1) throw new Error(`reopen cycle ${cycle + 1} did not produce one sheet and composer`);
    }

    await page.getByRole("button", { name: "Minimize Wealth Copilot" }).click();
    await page.getByRole("button", { name: "Restore Wealth Copilot" }).click();
    await page.getByRole("button", { name: "Close Wealth Copilot" }).click();
    await page.mouse.wheel(0, 500);
    const scrollY = await page.evaluate(() => window.scrollY);
    results.push({ viewport, cycles: 10, minimizeRestore: true, scrollY, errors });
    await page.close();
  }
  console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
  await browser.close();
}

