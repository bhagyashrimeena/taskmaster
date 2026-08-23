const backend = "http://127.0.0.1:8001/api/v1";

async function api(path, options = {}) {
  const response = await fetch(`${backend}${path}`, {
    method: options.method ?? "GET",
    headers: options.data ? { "Content-Type": "application/json" } : undefined,
    body: options.data ? JSON.stringify(options.data) : undefined,
  });
  if (!response.ok) {
    throw new Error(`${options.method ?? "GET"} ${path} returned ${response.status}`);
  }
  return response.json();
}

async function poll(read, complete, timeoutMs, label) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const value = await read();
    if (complete(value)) return value;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${label} did not finish within ${Math.round(timeoutMs / 1000)} seconds`);
}

const clockBefore = await api("/day/clock");
if (clockBefore.current_time !== "07:00" || clockBefore.status !== "paused") {
  throw new Error(
    `Restart the financial day and leave it paused at 07:00 before prewarming; current clock is ${clockBefore.current_time}/${clockBefore.status}.`,
  );
}
const dayBefore = await api("/day");

await api("/dashboard/refresh", { method: "POST" });
const dashboard = await poll(
  () => api("/dashboard"),
  (value) => !["queued", "running"].includes(value.refresh.phase),
  240_000,
  "Market prewarm",
);
if (dashboard.refresh.phase !== "complete" || dashboard.daily_brief.freshness.status !== "live") {
  throw new Error(
    `Live market prewarm is not ready (${dashboard.refresh.phase}/${dashboard.daily_brief.freshness.status}). Retained fallback remains available, but do not claim a live refresh.`,
  );
}

const generation = await api("/audio/morning/generate", { method: "POST" });
const audio = await poll(
  () => api(`/audio/${generation.brief.brief_id}/status`),
  (value) => !["queued", "generating"].includes(value.status),
  120_000,
  "Morning Pulse audio prewarm",
);
if (audio.status !== "ready" || !audio.audio_url) {
  throw new Error(
    `Morning Pulse audio is ${audio.status}; the transcript remains available, but skip live audio.`,
  );
}

const media = await fetch(`http://127.0.0.1:8001${audio.audio_url}`, {
  headers: { Range: "bytes=0-15" },
});
if (![200, 206].includes(media.status) || !media.headers.get("content-type")?.includes("audio/wav")) {
  throw new Error(`Prewarmed audio file is not browser-ready (${media.status}).`);
}

const [clockAfter, dayAfter] = await Promise.all([
  api("/day/clock"),
  api("/day"),
]);
if (
  clockAfter.current_time !== "07:00"
  || clockAfter.status !== "paused"
  || dayAfter.run_id !== dayBefore.run_id
) {
  throw new Error("Presentation state changed while prewarming; restart and prewarm again.");
}

console.log(JSON.stringify({
  status: "ready",
  runId: dayAfter.run_id,
  clock: `${clockAfter.current_time}/${clockAfter.status}`,
  marketFreshness: dashboard.daily_brief.freshness.status,
  marketStories: dashboard.daily_brief.stories.length,
  morningAudio: audio.status,
  morningAudioDurationSeconds: audio.actual_duration_seconds,
  instruction: "Keep this run. Do not click Restart again; begin with Next.",
}, null, 2));
