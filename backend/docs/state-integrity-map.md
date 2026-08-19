# Wealth Copilot State Integrity Map

Audit date: 2026-08-19

This map records the implementation and the single-source-of-truth repair. It intentionally distinguishes the API/state owner from the UI surface that renders the value.

## Canonical identity currently present

`FinancialDayState` is persisted by `FinancialDayStore` at one file per trading date. It carries `day_id`, `run_id`, `run_mode`, timeline, event assessments, portfolio snapshots, media IDs, advisor objects, market-close review, tomorrow events, Daily Wealth Story, and presentation clock fields. `PresentationClockService` owns an in-process minute/status view and mirrors its fields into `FinancialDayState`.

`active_financial_day()` exposes the canonical runtime identity from the persisted day and presentation clock. Presentation API surfaces now gate future event/story data at the backend boundary, and dashboard responses expose the canonical `AttentionSummary`.

## Surface ownership matrix

| User-visible surface / value | SOURCE | RUN_ID | DAY_ID | CHECKPOINT | CACHE / PERSISTENCE OWNER | Current integrity risk |
| --- | --- | --- | --- | --- | --- | --- |
| Attention headline count | `DashboardService.get_dashboard()` computes `high_relevance` from the selected `DailyBriefView.stories`, then adds `important_event.notification_required` | Dashboard response has `financial_day.run_id` and `financial_day.day_id`, but the count is recomputed per request | Dashboard response `financial_day.day_id` | No explicit checkpoint gate in backend; frontend presentation gate can subtract a future event | `FinancialDayStore` for day/event; `NewsCandidateCache` for candidates | Morning/media can calculate a different count; presentation can show a count derived from a later event while clock is earlier |
| Signal orbit count | Frontend `Dashboard` uses `visibleAttentionCount`, derived from dashboard count plus frontend event-time gating | Dashboard response run | Dashboard response day | Frontend uses presentation clock minute | Browser React state | Defense-in-depth only; not a canonical shared `AttentionSummary` |
| Personalized Daily Brief / Top 5 | `DashboardService._brief()` reads `NewsCandidateCache.snapshot()`, ranks with `RelevanceEngine`, selects with `DiversityRanker` | News snapshot has no run ID; dashboard wraps it with current financial-day IDs | Dashboard wraps current financial-day day ID | No presentation checkpoint freeze; cached batch can be newer/older than presentation time | `NewsCandidateCache` and persisted `MarketBriefSnapshot` | A live/cache snapshot can cross presentation runs/checkpoints |
| Morning Pulse script | `MediaService.prepare(MORNING)` calls `dashboard_service.get_dashboard()` and `AudioScriptBuilder.morning(dashboard)` | Audio brief has optional run ID assigned from current store, but script reads current dashboard/event | Audio brief gets current store day ID | No frozen 07:00 snapshot; can include current HDFC event | `MediaService` in-memory/cache metadata and `FinancialDayState.morning_brief_id` | 07:00 Morning Pulse can later include 12:17 HDFC/current attention state |
| Morning Pulse audio metadata | `AudioBrief` contains `day_id`, `run_id`, `source_snapshot_at`, `data_freshness`, used story/event IDs | `MediaService` identity includes day/run/stories/events/script, but not a formal source snapshot ID/checkpoint | Audio brief day ID | No explicit source checkpoint field | Audio metadata/WAV cache under configured audio cache directory | Existing audio can be reused by content identity while dashboard/current presentation has moved |
| Portfolio timestamp and prices | `get_portfolio_summary()` through active `PortfolioProvider`; `SimulatedPortfolioProvider` returns simulation snapshot | Provider summary has no FinancialDayState run binding | Provider `as_of` independent of day state | Simulation service checkpoint, not necessarily presentation clock checkpoint | Simulation service state and provider output | Portfolio can show a later simulation checkpoint than presentation clock |
| Important Event | `DashboardService._event()` gets `simulation_service.get_market_event()` and calls `EventDecisionEngine.assess()` or reuses persisted event | Persisted `EventAssessment` includes run ID; newly assessed event is passed current day/run | Passed current financial-day IDs | Simulation event availability plus frontend presentation gate | `DailyEventStore`, `FinancialDayState.events_detected/events_alerted` | API can assess/return event before presentation checkpoint unless backend gates it |
| Event Watcher trace | `EventDecisionEngine.assess()` creates trace; `DashboardService` maps trace into `ActivityItem` | Trace is inside event assessment with run ID | Event assessment day ID | Trigger/event time; not centrally gated in dashboard assembly | `DailyEventStore` and FinancialDayState event arrays | Relevance/decision trace can appear while clock is still before event |
| Financial Day timeline | `FinancialDayState.timeline`, mutated by `DayOrchestrator` checkpoint methods | State run ID | State day ID | Scheduled times and step status | `FinancialDayStore` JSON state | Timeline can be current while independent dashboard/news/media values are not from same run |
| Market Close Review | `DayOrchestrator.run_market_close()` derives from current provider and retained event IDs | Stored inside current FinancialDayState, but artifact has no explicit source snapshot ID | State day ID | 15:30 operation | FinancialDayStore | Provider/event inputs can be from a different simulation checkpoint/run |
| Evening Wealth Wrap | `MediaService.prepare(EVENING)` builds from current dashboard, daily interaction state, and optional current financial day | AudioBrief run ID from current store | AudioBrief day ID | No explicit 20:00 source checkpoint | MediaService audio cache + state `evening_brief_id` | Can read post-event/current dashboard state when reused as earlier artifact; cache identity lacks checkpoint/source snapshot ID |
| Tomorrow Prep | `DayOrchestrator.prepare_tomorrow()` derives from current dashboard/event context and writes `tomorrow_events` | Stored in FinancialDayState run | State day ID | 21:00 operation | FinancialDayStore | No artifact provenance object; stale tomorrow items can survive run reset if not cleared |
| Daily Wealth Story | `DailyStoryService` / `DailyStoryBuilder` consumes FinancialDayState snapshots, review, events, advisor, tomorrow | Story schema has day/run IDs | Story schema has day ID | Intended 21:01, but frontend receives `daily_story` from state and readiness is separately gated | FinancialDayStore plus story/narration caches | Existing persisted story can be offered before current presentation day is complete unless backend readiness is enforced |
| Advisor packet | `AdvisorService.create()` resolves current surface context and stores packet in FinancialDayState | Packet has day/run IDs | Packet has day ID | User interaction time; no presentation checkpoint binding | FinancialDayStore and advisor provider | Can be created from event/context not active at current presentation time |
| Advisor response | `AdvisorService` stores `AdvisorResponse` in FinancialDayState | Response has day/run IDs | Response has day ID | Provider reply time | FinancialDayStore | Replied object can remain visible across restart unless disassociated by run |
| Chat surface context | `InteractionService.respond()` resolves `SurfaceContext` from current dashboard/event/story context; browser persists thread in local storage | Conversation stores conversation ID, target, response; not a canonical day/run artifact contract | No required day ID in chat persistence | No presentation-time binding in request contract | `conversation_store` backend and `chat-storage.js` frontend | Chat can explain current/later context while presentation clock is earlier; durable chat intentionally may survive runs |

## Persistence and cache owners

- `FinancialDayStore`: per-date JSON persistence for the financial-day state and most day artifacts.
- `PresentationClockService`: in-process clock state mirrored into `FinancialDayState.presentation_*` fields.
- `NewsCandidateCache`: in-process and persisted live `MarketBriefSnapshot`; currently candidate batch identity is not bound to a presentation `run_id`.
- `MediaService`: in-process audio metadata and WAV/JSON cache; `AudioBrief` carries day/run but not source snapshot/checkpoint provenance.
- `DailyEventStore`: retained event assessments and user actions.
- `conversation_store` / frontend `chat-storage.js`: chat continuity, intentionally separate from the financial-day run.
- Simulation service: active simulated market checkpoint and portfolio snapshots, independent of `FinancialDayState` unless orchestrator explicitly advances it.

## Known contradictory paths to repair

1. Dashboard attention count and Morning Pulse count are computed from different inputs and times.
2. Presentation clock minute and portfolio provider `as_of` can refer to different simulation checkpoints.
3. Dashboard event activity can be built from an event assessment before the presentation clock reaches its trigger.
4. Morning Pulse regenerates from current dashboard state instead of a frozen 07:00 snapshot.
5. Audio metadata reports its own source snapshot time, which can be later than presentation time.
6. Daily Wealth Story readiness is not enforced solely by the backend financial-day checkpoint.
7. Restart/initialize behavior must be checked for new `run_id` and disassociation of event, media, advisor, close, tomorrow, and story artifacts.

## Repair status

- Dashboard event assessment is a quiet monitoring assessment before 12:17; future HDFC trace/relevance is not returned by the API.
- Dashboard and Morning Pulse use the same `AttentionSummary`; Morning Pulse persists that summary and its source identity at 07:00.
- Morning and evening scripts treat quiet monitoring as a real state rather than assuming an alert payload.
- Daily Wealth Story rejects presentation requests before 21:01.
- Restart still creates a new run through fresh `FinancialDayState` initialization and clears derived day artifacts; durable chat remains separate.

## Remaining repair target

Introduce/enforce an `ActiveFinancialDay` runtime view derived from the persisted state and presentation clock. Every current-run artifact should carry `day_id`, `run_id`, `source_checkpoint`, `source_snapshot_id`, and `generated_at`. A single `AttentionSummary` should be computed once for the active checkpoint and consumed by dashboard, Morning Pulse, audio, and financial-day summaries. Chat history may remain durable separately, but its resolved surface context must be rejected or labeled when it does not match the active run/checkpoint.
