# Wealth Copilot

## What it is

Wealth Copilot is a portfolio-aware financial intelligence assistant. V1 turns portfolio and market context into a personalized daily brief, deterministic event alerts, explanations, research handoffs, audio briefs, a financial-day timeline, an optional advisor handoff, and a Daily Wealth Story. It prioritizes information and uncertainty; it does not provide investment instructions or place trades.

The portfolio and controlled presentation scenarios are simulated. Market news can use Google Search grounding when configured.

## Architecture

- **TaskMaster:** Google ADK supervisor and intent router.
- **Portfolio Agent:** provider-neutral portfolio contract; the included provider is simulated and Zerodha is optional read-only integration.
- **Market Intelligence Agent:** Google Search grounding or deterministic scenario news.
- **Research Agent:** source-first follow-up research.
- **Media Agent:** Morning Pulse, Evening Wrap, and story scripts with optional Gemini TTS.
- **RelevanceEngine:** deterministic exposure, sector, materiality, freshness, and movement scoring.
- **EventDecisionEngine / Event Watcher:** deterministic trigger, investigation, relevance, and `IGNORE` / `MONITOR` / `INVESTIGATE` / `ALERT` decisions.
- **FinancialDayState / DayOrchestrator:** durable day identity, checkpoints, artifacts, event continuity, advisor state, and story state.
- **Presentation mode:** accelerated simulated time from 07:00 through 21:01, with controlled scenario checkpoints and a new run on restart.

## Tech stack

- Python 3.10+; FastAPI; Pydantic Settings; Uvicorn
- Google ADK 2.5.0; Gemini/Vertex AI; Google Search grounding
- Next.js 16.3.1; React 19; TypeScript 5.9; ESLint 9; Lucide React
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

- Dashboard: http://127.0.0.1:3001/
- simulated clock Presentation mode: http://127.0.0.1:3001/?presentation=true
- API health: http://127.0.0.1:8001/health
- API documentation: http://127.0.0.1:8001/docs

## Google Cloud and Gemini setup

```powershell
gcloud init
gcloud config set project YOUR_GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
```

Set `GOOGLE_GENAI_USE_ENTERPRISE=TRUE`, `GOOGLE_CLOUD_PROJECT`, and `GOOGLE_CLOUD_LOCATION` in `backend/.env`. Enable the required Google Cloud services and grant the authenticated principal Gemini/Vertex AI access. Google Search grounding requires a supported ADK/Gemini configuration and network access. `GOOGLE_API_KEY` is an optional alternative for Gemini Developer API mode; never commit its value.

## Normal mode vs presentation mode

Normal mode opens the cached-first dashboard and hides accelerated day controls. Presentation mode uses `/?presentation=true` and exposes:

```text
07:00 Morning Pulse
08:00 Portfolio Health
12:17 controlled market event
15:30 Market Close
20:00 Evening Wrap
21:00 Tomorrow Prep
21:01 Daily Wealth Story
```

Restarting presentation creates a new run and clears derived day artifacts. Presentation time is simulated time, not wall-clock time.

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
node scripts/normal-product-browser-smoke.mjs
node scripts/phase87-copilot-browser-smoke.mjs
node scripts/presentation-clock-browser-smoke.mjs
node scripts/phase9-temporal-browser-smoke.mjs
```

## Known limitations

- The portfolio remains simulated; no autonomous trading is implemented.
- Zerodha is optional read-only integration and not the default path.
- Google Search, Gemini, TTS, and Gmail advisor behavior depend on external credentials, quotas, and network access.
- Audio falls back to a complete text transcript when TTS is unavailable.
- Some publisher source links may not have durable URLs.
- The demo advisor provider simulates review, send, and reply behavior.

## Architecture documentation

- [System architecture](backend/docs/system-architecture.md)
- [State integrity map](backend/docs/state-integrity-map.md)
- [Final system validation](backend/docs/final-system-validation.md)
- [UI/UX self-audit](backend/docs/ui-ux-self-audit.md)

## Safety disclaimer

Wealth Copilot provides information prioritization, portfolio context, and research support. It is not a financial advisor and does not provide investment instructions. Users remain responsible for financial decisions.
