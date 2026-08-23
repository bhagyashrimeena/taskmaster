# Wealth Copilot backend

The backend combines Google ADK agents with deterministic workflows and stable
application contracts. The current hackathon build includes personalized Top 5
market intelligence, Event Watcher, cached-first dashboard, Explain/Research,
Gemini TTS, Autonomous Financial Day, reviewed human-advisor handoff, Daily
Wealth Story, and deterministic simulation scenarios.

## Setup

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

For Agent Platform calls, authenticate with Application Default Credentials:

```powershell
gcloud init
gcloud config set project YOUR_GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GOOGLE_CLOUD_PROJECT
```

Use one Vertex AI authentication path for TaskMaster, specialist agents,
Google Search grounding, and Gemini TTS:

```env
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_GENAI_USE_ENTERPRISE=True
GOOGLE_CLOUD_PROJECT=YOUR_GOOGLE_CLOUD_PROJECT
GOOGLE_CLOUD_LOCATION=global
GEMINI_API_KEY=
GOOGLE_API_KEY=
```

`GOOGLE_GENAI_USE_ENTERPRISE` is retained as a compatibility alias. Application
code normalizes either flag into one Vertex-enabled setting. API keys remain an
optional Developer API fallback and are not required when Vertex AI and ADC are
configured. `GET /api/v1/readiness` reports the project and configuration state
without returning credentials. It does not make a billable model call.

Run the API and ADK agent from `backend/`:

```powershell
uvicorn wealth_copilot.api:app --host 127.0.0.1 --port 8001
adk run wealth_copilot
```

## LiveKit voice worker

Create a LiveKit Cloud project and add these server-only values to `.env`:

```env
LIVEKIT_URL=wss://YOUR_PROJECT.livekit.cloud
LIVEKIT_API_KEY=YOUR_LIVEKIT_API_KEY
LIVEKIT_API_SECRET=YOUR_LIVEKIT_API_SECRET
LIVEKIT_AGENT_NAME=wealth-copilot
```

The default STT and TTS use LiveKit Inference, so they need no separate provider keys. Start the explicitly dispatched worker in development or production mode:

```powershell
python -m wealth_copilot.voice.agent dev
# production:
python -m wealth_copilot.voice.agent start
```

The browser requests `/api/v1/copilot/voice/session`, joins the short-lived room, and waits for the worker before showing an active call. The worker transcribes speech, delegates each finalized turn to the canonical TaskMaster-backed `InteractionService`, and synthesizes that returned answer. It does not contain an independent financial LLM path. `record=False` disables LiveKit session recording; the existing Copilot conversation memory retains the text turns.

## Copilot long-term memory

Copilot now includes a local SQLite-backed memory layer for user-specific context such as name, goals, preferences, and prior exchanges. Configure it with:

```env
INTERACTION_MEMORY_DB_PATH=.cache/memory/interaction.db
INTERACTION_MEMORY_RECALL_LIMIT=6
```

Memory retrieval is local and lightweight: it uses SQLite plus lexical ranking, not Oracle or an external vector database. The copilot UI shows a `Remembered context used` badge when a reply used recalled memory.

Run a credential-free two-turn TaskMaster adapter check with:

```powershell
$env:PYTHONPATH='.'
python scripts/livekit_voice_conversation_smoke.py
```

Run the dashboard from `frontend/`:

```powershell
npm install
npm run dev -- --port 3001
```

## Simulation configuration

The canonical hackathon provider is explicit:

```env
PORTFOLIO_PROVIDER=simulated
SIMULATION_MODE=normal
SIMULATION_SCENARIO_ID=hdfc-company-shock
NEWS_PROVIDER=google_search
```

`judge` mode uses deterministic scenario news even when the normal news
provider is configured for Google Search. This provides a repeatable judging
path. Set `SIMULATION_MODE=normal` to retain the simulated portfolio while using
live Search and its 15-minute stale-safe cache.

The legacy environment value `demo` is accepted and normalized to `simulated`
during migration, but API responses always return the canonical value.

## Scenario controller

The process-wide `SimulationService` supports:

```text
load_scenario()
reset_scenario()
advance_to(time)
get_current_snapshot()
get_market_event()
get_close_snapshot()
```

Financial Day advances the active scenario through fixed checkpoints:

```text
07:00 Morning Pulse
08:00 Portfolio Health
12:17 Market Event
15:30 Market Close
20:00 Evening Wealth Wrap
21:00 Tomorrow Prep
```

All values are deterministic. There is no unseeded/random price generation.

## Simulation API

| Route | Purpose |
| --- | --- |
| `GET /api/v1/simulation` | Current mode, scenario, checkpoint, and provenance |
| `POST /api/v1/simulation/scenarios/{scenario_id}` | Load a scenario at its event checkpoint |
| `POST /api/v1/simulation/reset` | Reset the current scenario to 07:00 |
| `POST /api/v1/simulation/advance` | Advance using `{"checkpoint":"15:30"}` |

Portfolio responses expose `source`, `provider`, `scenario_id`, and `as_of`.
The dashboard source contract additionally exposes the active checkpoint.

## Key behavior

- The dashboard renders retained portfolio and news immediately.
- Live Search refreshes run in the background and fall back to the last
  successful batch on quota or availability errors.
- Deterministic code owns normalization, portfolio matching, relevance,
  source-quality scoring, deduplication, diversity, event triggers, and alert
  decisions.
- LLMs are used where interpretation, search extraction, or conversation adds
  value.
- No feature places trades or gives investment instructions.

## Tests

Run the complete offline suite:

```powershell
python -m pytest tests -q
```

Run frontend validation:

```powershell
Set-Location ..\frontend
npm run typecheck
npm run lint
npm run build
```

The simulation suite verifies provenance, timestamped price changes, all five
scenario paths, quiet-day no-alert behavior, API load/advance/reset controls,
and full Financial Day continuity.

## Production realism

Normal mode combines the transparent Simulated Portfolio with live Google
Search-grounded market intelligence. Every successful live candidate batch is
atomically persisted at `.cache/market/latest.json`; a restart can therefore
render real headlines, publisher names, and clickable source URLs immediately
without waiting for another Search request. Scenario news remains available for
controlled financial-day runs only.

Every financial-day replay receives a new `run_id` beneath a stable `day_id`.
Dashboard briefs, Event Watcher assessments, advisor exchanges, audio briefs,
and Daily Wealth Stories carry those identifiers. Changing scenarios clears the
visible day, which prevents an event from one run being shown beside a timeline
or recap from another.

Freshness internals remain in telemetry, while the product uses simple
`Updated` and `Last updated` language. The accelerated financial-day controls
live on the product Timeline and delegate every checkpoint to the same
`DayOrchestrator`.

## Runtime boundary

The current hackathon runtime is intentionally single-user and process-local:
the simulated portfolio, financial-day clock, conversation context, background
jobs, and interaction state are shared by the running API process. Do not expose
the API directly to multiple users or the public internet without adding
authentication, user-scoped persistence, and authorization around simulation,
advisor-send, and other mutation endpoints.

Daily Wealth Story narration is generated as one WAV per scene. Each scene
records its measured duration plus a short breathing interval, and the React
player advances on the audio `ended` event. Pause, previous, next, replay, and
mute operate on the same visual/audio timeline.
