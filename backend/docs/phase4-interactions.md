# Phase 4 — Interactive Explain, Research, and Chat

Phase 4 keeps the Phase 3 dashboard bootstrap independent from model latency. `GET /api/v1/dashboard` still returns cached or demo intelligence immediately; every interaction happens through a separate endpoint after the page is usable.

## Architecture

```text
Dashboard card / global question
              |
          TaskMaster
      /         |          \
retained     portfolio     Research Agent
context       agent        (explicit only)
      \         |          /
       safe, sourced response
```

- `Explain` sends the stable `story_id` or `event_id` to the real TaskMaster.
- Retained story, event, exposure, relevance, source, and recent conversation history are supplied first. Explain is forbidden from refreshing news or invoking Research.
- `Learn more` creates an asynchronous job. TaskMaster delegates that request to the source-first Research Agent.
- A timeout, quota error, or search failure returns a clearly marked answer from retained context rather than exposing a backend error.
- Facts, interpretation, uncertainty, and sources are separate response fields.
- Output is filtered for unsafe transaction instructions in addition to agent-level safety rules.
- Save-for-evening and lightweight feedback are retained in the current daily state.

## HTTP contract

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/chat` | Explain or continue a contextual TaskMaster conversation |
| `POST` | `/api/v1/research` | Queue an explicit deeper investigation |
| `GET` | `/api/v1/research/{job_id}` | Poll Research Agent progress/result |
| `POST` | `/api/v1/stories/{story_id}/save` | Persist a story for the evening wrap |
| `POST` | `/api/v1/events/{event_id}/actions` | Persist an event action; `save_for_evening` also enters daily state |
| `POST` | `/api/v1/feedback` | Record `useful` or `not_relevant` feedback |

The dashboard response contains `daily_state`, including saved story IDs, saved event IDs, and feedback. The UI remains provider-neutral.

## Context behavior

The client retains the returned `conversation_id`. A follow-up can omit item IDs and the backend resolves the active story/event from conversation state. Up to twelve recent user/assistant messages are retained per conversation in this hackathon implementation.

## Run

```powershell
cd backend
uvicorn wealth_copilot.api:app --host 127.0.0.1 --port 8001
```

In a second terminal:

```powershell
cd frontend
npm run dev -- --port 3001
```

Open `http://127.0.0.1:3001`. The configured Next.js proxy forwards `/api/backend/*` to the backend.

## Verification

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run typecheck
npm run lint
npm run build
```
