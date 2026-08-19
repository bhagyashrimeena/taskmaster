# Phase 3: Usable Dashboard

The Phase 3 dashboard visualizes the existing portfolio, daily-brief, and Event
Watcher intelligence. It does not add a new AI capability or investment advice.

## Latency contract

`GET /api/v1/dashboard` never waits for Google Search. It returns the newest
retained candidate batch or seeds the deterministic demo batch, then exposes:

- provider-neutral portfolio snapshot and source label;
- five already-ranked personalized stories and preserved source links;
- live/cached/stale freshness metadata;
- the HDFC hero Event Watcher assessment;
- today's retained event assessments;
- the five-stage agent trace;
- current background-refresh state.

`POST /api/v1/dashboard/refresh` returns HTTP 202 immediately. Demo mode
refreshes from deterministic fixtures without Gemini. Live mode runs only the
Search-focused Market Agent in the background, updates the retained candidate
pool, and lets future GET requests deterministically rerank it. Concurrent or
repeated refreshes within five minutes are coalesced.

If Search fails, the prior candidate batch remains available and the contract
returns `freshness.status=stale` with the label `Using last successful market
update`.

## Endpoints

```text
GET  /health
GET  /api/v1/dashboard
POST /api/v1/dashboard/refresh
POST /api/v1/events/{event_id}/actions
```

## Run locally

From `backend/`:

```powershell
uvicorn wealth_copilot.api:app --host 127.0.0.1 --port 8001
```

From `frontend/`:

```powershell
npm install
npm run dev
```

The frontend proxies `/api/backend/*` to `http://127.0.0.1:8001`. Override it
with `WEALTH_COPILOT_BACKEND_URL` when needed. If port 3000 is occupied, use
`npm run dev -- --port 3001`.

## Product boundary

Actions are limited to `Explain`, `Learn more`, and `Save`. They reveal or
retain context only. No investment decision language or sent notifications are
part of Phase 3.

