import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

await mkdir(new URL("../../artifacts/", import.meta.url), { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(`console: ${message.text()}`);
});
page.on("pageerror", (error) => errors.push(`page: ${error.message}`));

try {
  const storyResponse = await page.request.get("http://127.0.0.1:8001/api/v1/story/today");
  if (!storyResponse.ok()) throw new Error(`Story API returned ${storyResponse.status()}`);
  const story = await storyResponse.json();
  const dayResponse = await page.request.get("http://127.0.0.1:8001/api/v1/day");
  const day = await dayResponse.json();
  const storyStep = day.timeline.find((step) => step.step_id === "story");
  if (storyStep?.status !== "complete") throw new Error("Daily Wealth Story checkpoint is not complete");
  if (story.duration_seconds < 20 || story.duration_seconds > 30) throw new Error("Story duration is outside 20–30 seconds");

  await page.goto("http://127.0.0.1:3001", { waitUntil: "networkidle", timeout: 30000 });
  await page.getByTestId("wealth-story-card").waitFor();
  await page.getByRole("heading", {
    name: new RegExp(`Your financial day.*${story.duration_seconds} sec`, "i"),
  }).waitFor();
  await page.screenshot({ path: "../artifacts/phase8-dashboard-story-card.png", fullPage: true });

  await page.getByTestId("watch-wealth-story").click();
  const player = page.getByTestId("wealth-story-player");
  await player.waitFor();
  await player.getByRole("button", { name: "Pause recap" }).click();

  const verifyScene = async (index, screenshotName) => {
    const expected = story.scenes[index];
    await player.getByText(expected.title, { exact: true }).waitFor();
    if (expected.primary_value) await player.getByText(expected.primary_value, { exact: true }).waitFor();
    if (expected.secondary_text) await player.getByText(expected.secondary_text, { exact: true }).waitFor();
    if (screenshotName) await page.screenshot({ path: `../artifacts/${screenshotName}`, fullPage: false });
  };

  await verifyScene(0, "phase8-story-summary.png");
  for (let index = 1; index < story.scenes.length; index += 1) {
    await player.getByRole("button", { name: "Next scene" }).click();
    await verifyScene(index, story.scenes[index].kind === "advisor" ? "phase8-story-advisor.png" : story.scenes[index].kind === "tomorrow" ? "phase8-story-tomorrow.png" : null);
  }

  if (story.advisor_interaction && !story.scenes.some((scene) => scene.kind === "advisor")) {
    throw new Error("Advisor interaction was not rendered as a scene");
  }
  console.log(JSON.stringify({
    status: "passed",
    storyId: story.story_id,
    scenes: story.scenes.map((scene) => scene.kind),
    durationSeconds: story.duration_seconds,
    storyCheckpoint: storyStep.status,
    advisorIncluded: Boolean(story.advisor_interaction),
    consoleErrors: errors,
  }, null, 2));
  if (errors.length) process.exitCode = 1;
} finally {
  await browser.close();
}
