# Wealth Copilot

## What it is

Wealth Copilot is a portfolio-aware financial intelligence assistant. V1 turns portfolio and market context into a personalized daily brief, deterministic event alerts, explanations, research handoffs, audio briefs, a financial-day timeline, an optional advisor handoff, and a Daily Wealth Story. It prioritizes information and uncertainty; it does not provide investment instructions or place trades.

The portfolio and controlled financial-day scenarios are simulated. Market news can use Google Search grounding when configured.

## Architecture

- **TaskMaster:** Google ADK supervisor and intent router.
- **Portfolio Agent:** provider-neutral portfolio contract; the included provider is simulated and Zerodha is optional read-only integration.
- **Market Intelligence Agent:** Google Search grounding or deterministic scenario news.
- **Research Agent:** source-first follow-up research.
- **Media Agent:** Morning Pulse, Evening Wrap, and story scripts with optional Gemini TTS.
- **RelevanceEngine:** deterministic exposure, sector, materiality, freshness, and movement scoring.
- **EventDecisionEngine / Event Watcher:** deterministic trigger, investigation, relevance, and `IGNORE` / `MONITOR` / `INVESTIGATE` / `ALERT` decisions.
- **FinancialDayState / DayOrchestrator:** durable day identity, checkpoints, artifacts, event continuity, advisor state, and story state.
- **Financial-day clock:** accelerated product controls run all 13 scheduled checkpoints from 07:00 through 21:01, with a new run on restart.

## Tech stack

- Python 3.10+; FastAPI; Pydantic Settings; Uvicorn
- Google ADK 2.5.0; Gemini/Vertex AI; Google Search grounding
- Next.js 16.3.1; React 19; TypeScript 5.9; Tailwind CSS 4; TanStack Query; Zustand; Recharts; Motion; Radix; Lucide React; LiveKit client
- Pytest and pytest-asyncio; Playwright Core browser smoke scripts

## Repository structure

```text
backend/       Application, agents, providers, workflows, API, tests, docs
frontend/      Next.js app, components, API client, types, browser scripts
```

## Prerequisites

- Python 3.10 or newer; Python 3.11 is the tested local version.
- Node.js compatible with Next.js 16.3.1 and npm.
- Google Cloud CLI only for Google ADK, Gemini/Vertex, or Search grounding.
- Application Default Credentials for Vertex/Agent Platform mode.

## Installation

### Backend

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

The default backend configuration uses the simulated portfolio and demo advisor provider.

### Frontend

```powershell
Set-Location ..\frontend
npm install
Copy-Item .env.example .env.local
```

The frontend environment file is optional when using the default backend URL.

## Running locally

Backend from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn wealth_copilot.api:app --host 127.0.0.1 --port 8001
```

Frontend from `frontend/`:

```powershell
npm run dev -- --port 3001
```

URLs:

- Product Today view: http://127.0.0.1:3001/
- Portfolio / Copilot / Alerts / Timeline: `/portfolio`, `/copilot`, `/alerts`, `/timeline`
- API health: http://127.0.0.1:8001/health
- API documentation: http://127.0.0.1:8001/docs

## Google Cloud and Gemini setup

```powershell
gcloud init
gcloud config set project YOUR_GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
```

Set `GOOGLE_GENAI_USE_ENTERPRISE=TRUE`, `GOOGLE_CLOUD_PROJECT`, and `GOOGLE_CLOUD_LOCATION` in `backend/.env`. Enable the required Google Cloud services and grant the authenticated principal Gemini/Vertex AI access. Google Search grounding requires a supported ADK/Gemini configuration and network access. `GOOGLE_API_KEY` is an optional alternative for Gemini Developer API mode; never commit its value.

## Financial-day controls

Timeline is the single day-running surface. **Start the day**, **Pause the day**, and **Resume the day** preserve completed work. **Restart the day** requires confirmation, resets the simulated run to 07:00, and starts it immediately. The clock executes every product checkpoint in scheduled order:

```text
07:00 Morning Pulse
08:00 Portfolio Health
09:15 Market Open Monitor
10:00 Adaptive Market Watch
11:30 Sector Deep Dive
12:17 Event Investigations
13:00 Learn From Your Portfolio
15:30 Market Close
17:00 Portfolio Intelligence
18:30 Action Queue
20:00 Evening Wrap
21:00 Tomorrow Prep
21:01 Daily Wealth Story
```

Qualifying events continue through the deterministic decision engine. A new alert updates the product queries and appears as a dismissible in-app notification; no browser-notification permission is requested.

## Copilot voice and calls

Browser speech recognition can transcribe into the persistent composer for review before sending through the same `/api/v1/copilot` TaskMaster path. Text remains available when speech recognition or microphone permission is unavailable.

Live calls are config-gated. Set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `backend/.env`; the API secret is used only on the server to mint a 15-minute participant token. `LIVEKIT_AGENT_NAME` defaults to `wealth-copilot`.

Run the voice worker alongside the API:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m wealth_copilot.voice.agent dev
```

The worker uses LiveKit Inference for `LIVEKIT_STT_MODEL`/`LIVEKIT_TTS_MODEL`, then sends each finalized transcript through the existing `InteractionService` in `call` mode. A non-callable SDK sentinel makes any accidental direct LLM bypass fail. Final LiveKit transcriptions are appended to the same persisted browser conversation. Without the three LiveKit credentials, the control remains visible but disabled; with credentials but no reachable worker, the UI times out safely and keeps text chat available.

No separate Deepgram, Inworld, or OpenAI key is required when using the default LiveKit Inference models. TaskMaster still requires the existing Google Vertex ADC or Gemini configuration.

## Simulated vs live data

- Portfolio prices, holdings, and scenario event triggers are simulated.
- The controlled HDFC event is a deterministic fixture.
- Normal-mode market/news intelligence can be live through Google Search grounding.
- Relevance, event decisions, exposure calculations, checkpoint gating, and artifact identity are deterministic code.
- Advisor email delivery defaults to a demo provider; Gmail is optional.

## Tests and checks

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run typecheck
npm run lint
npm run build
```

With both servers running, browser smoke tests include:

```powershell
npm run test:e2e:mobile
npm run test:e2e:copilot
npm run test:e2e:copilot-ux
npm run test:e2e
npm run test:e2e:polish
```

## Known limitations

- The portfolio remains simulated; no autonomous trading is implemented.
- Zerodha is optional read-only integration and not the default path.
- Google Search, Gemini, TTS, and Gmail advisor behavior depend on external credentials, quotas, and network access.
- Audio falls back to a complete text transcript when TTS is unavailable.
- LiveKit credentials and a running/deployed `wealth-copilot` voice worker are required for realtime calls; the browser UI and voice worker do not create a second financial reasoning path.
- Some publisher source links may not have durable URLs.
- The demo advisor provider simulates review, send, and reply behavior.

## Architecture documentation

- [System architecture](backend/docs/system-architecture.md)
- [State integrity map](backend/docs/state-integrity-map.md)
- [Final system validation](backend/docs/final-system-validation.md)
- [UI/UX self-audit](backend/docs/ui-ux-self-audit.md)

## Safety disclaimer

Wealth Copilot provides information prioritization, portfolio context, and research support. It is not a financial advisor and does not provide investment instructions. Users remain responsible for financial decisions.
