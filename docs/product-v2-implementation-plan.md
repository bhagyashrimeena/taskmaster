# Wealth Copilot Product V2 implementation plan

> Current-state note (2026-08-23): the separate presentation fixture described below has been retired. Timeline is now the single user-facing financial-day runner; internal presentation-mode fields and endpoints remain compatibility details only.

## Product contract

Wealth Copilot is an attention-management product whose primary question is: **What deserves this user's attention right now?** TaskMaster operates a continuous, timezone-aware financial day. Deterministic code owns portfolio values, market comparisons, relevance thresholds, attention decisions, case state, and contribution calculations. Models may research and explain those facts, but may not calculate financial values, recommend trades, or execute transactions.

The existing Google ADK agents, FastAPI application, Next.js application, provider integrations, advisor flow, Search grounding, Gemini TTS, demo clock, and working demo scenarios remain in place. The accelerated clock and HDFC event become developer fixtures rather than normal-product architecture.

## Audit baseline (2026-08-22)

- The repository has one initial commit and a large pre-existing dirty worktree. Product V2 work must avoid overwriting unrelated changes.
- Backend baseline: 133 tests collected; 120 passed and 13 failed before Product V2 edits. Most failures are inconsistent fixture expectations after earlier portfolio/UI changes. New phases need focused tests plus a full-suite report that distinguishes these baseline failures.
- Existing foundations: `PortfolioProvider`, a simulated portfolio, Zerodha adapter, news provider/Search agent split, `MarketEvent`, `EventDecisionEngine`, JSON `FinancialDayStore`, real-time `DayScheduler`, presentation clock, `DayOrchestrator`, ADK TaskMaster, advisor flow, TTS, and a five-destination mobile shell.
- Principal gaps: static sector/allocation summaries, no quote-specific `MarketDataProvider`, event-id-specific scoring, HDFC-specific timeline/orchestrator paths, an incomplete wall-clock schedule, no `FinancialCase`, no explicit attention budget, and TaskMaster that mostly routes intent.

## Foundation implementation status

Implemented after the audit:

- **Phase 0 foundation:** normal day identity uses the configured wall clock; real scheduling is the default; a fresh real timeline is generic; fixture time advances only in demo/presentation mode or when an explicit fixture trading date is used.
- **Phase 1:** `DemoPortfolioProvider` is the canonical compatibility entry point. Holding weights, sector look-through exposure, asset allocation, and equity/defensive totals are calculated from current values.
- **Phase 2:** the new `MarketDataProvider` contract covers quote(s), intraday, index, sector, snapshot, volume, and history. Its deterministic implementation is explicitly non-live and independent of Search/news.
- **Phase 3:** `MarketEvent` now carries normalized instrument and metadata, `MarketEventStream`/`EventWatcher` are provider-independent, and the event-id scoring branch was removed.
- **Phase 4:** the scheduler covers all requested wall-clock checkpoints and recurring 15-minute adaptive-watch slots from 10:00 through 11:15.
- **Phase 5:** a deterministic TaskMaster operator records observations, plan, delegation, verification, decision, and follow-up; the ADK TaskMaster can read this retained state.
- **Phase 6/7 foundation:** material events open durable `FinancialCase` records, case transitions are validated, case endpoints are available, and an attention budget tracks processed/interrupted/deferred/monitored/ignored signals.

Validation at this checkpoint: all six new Product V2 foundation tests pass; frontend lint, TypeScript, and production build pass. The full backend suite is 126 passed / 13 failed, the same 13 pre-existing fixture-expectation failures recorded at baseline (plus six new passing tests).

## Product frontend implementation status

Implemented after the backend foundation:

- Focused FastAPI contracts now serve `/today`, `/portfolio`, `/alerts`, `/alerts/{caseId}`, `/timeline`, `/copilot`, and `/events/stream`.
- The Next.js application is split into Today, Portfolio, Copilot, Alerts, alert detail, and Timeline routes under one persistent mobile-first shell.
- TanStack Query owns remote state and SSE invalidation. Zustand owns only alert/range UI state and persistent Copilot conversation state.
- Recharts consumes backend-supplied portfolio, contribution, exposure, benchmark, and alert-detail values; React does not recreate financial calculations or decisions.
- Tailwind consumes semantic CSS variables for financial and attention states. Reusable loading, error, empty, status, financial-value, and page-header primitives are in place.
- The installable PWA includes manifest metadata, safe-area layout, an offline truth-preserving fallback, and a service worker that never caches financial API responses.
- The accelerated scenario remains available only at `/dev/presentation?presentation=true` as a developer fixture.

Validation at this checkpoint: 146 backend tests pass; frontend TypeScript, ESLint, and the Next.js production build pass; the product Playwright evaluation passes at 390x844 and 1440x1000 with five-route navigation, no horizontal overflow, an active PWA worker, and Copilot continuity across route changes.

## Phase plans

### Phase 0 — Remove presentation-first assumptions

- **CURRENT STATE:** Normal and presentation surfaces are separated in the frontend, but `FinancialDayState.default_timeline`, `DayOrchestrator`, `application_today`, and several copy paths still assume the 12:17 HDFC scenario. Presentation controls are query-string gated.
- **GAP:** Normal operation must use local wall-clock time and generic events; the accelerated clock may only drive developer/test runs.
- **FILES AFFECTED:** `config.py`, `day/schemas.py`, `day/orchestrator.py`, `day/presentation.py`, `api.py`, dashboard/frontend copy, simulation tests.
- **MODEL/SCHEMA CHANGE:** Add an explicit run-mode enum and generic checkpoint identifiers; stop making `scenario_id` part of default real-day identity.
- **API CHANGE:** Preserve presentation endpoints as developer utilities; normal `/day` never starts or advances presentation time.
- **FRONTEND CHANGE:** Keep one “Demo portfolio” source indicator; hide clock/scenario controls outside developer presentation mode.
- **TESTS:** Wall-clock date selection, presentation isolation, no HDFC label in a fresh real day, developer clock regression.
- **DEPENDENCIES:** None.
- **RISK:** Existing demo/browser tests encode historical times and labels; preserve compatibility through explicit demo mode.

### Phase 1 — Portfolio domain

- **CURRENT STATE:** A provider ABC and detailed multi-asset fixture exist. Holding weights are calculated, but simulated sector exposure, asset allocation, equity/defensive exposure, and performance are partly static.
- **GAP:** One canonical `DemoPortfolioProvider` must derive every aggregate from current market values and expose enough history/look-through data for all consumers.
- **FILES AFFECTED:** `portfolio/schemas.py`, `portfolio/provider.py`, `portfolio/demo_provider.py`, `portfolio/simulated_provider.py`, `portfolio/zerodha_provider.py`, agents/dashboard consumers.
- **MODEL/SCHEMA CHANGE:** Add canonical portfolio value history, benchmark history, transaction/event metadata, and optional fund sector look-through. Treat weights as calculated output, never fixture input.
- **API CHANGE:** Portfolio responses retain compatibility while adding canonical history and `data_source_label="Demo portfolio"`.
- **FRONTEND CHANGE:** Later charts consume the canonical response; no duplicate finance fixtures.
- **TESTS:** Aggregate equality, weights sum/tolerance, current-value recomputation at each checkpoint, sector look-through, history consistency, provider contract tests.
- **DEPENDENCIES:** Phase 0 naming/run-mode boundary.
- **RISK:** Earlier tests assert obsolete hard-coded values; replace assertions with invariants where product values are intentionally dynamic.

### Phase 2 — Market data abstraction

- **CURRENT STATE:** News has a provider/Search boundary, while portfolio providers also expose quote methods. No independent market-price contract exists.
- **GAP:** Search cannot be treated as a quote feed. Event detection needs provider-neutral quotes, indexes, sectors, volume, intraday, historical prices, and snapshots.
- **FILES AFFECTED:** New `market_data/` package, `config.py`, `events/`, `agents/event_watcher.py`, readiness/docs.
- **MODEL/SCHEMA CHANGE:** Add `MarketQuote`, `IntradayPoint`, `IndexQuote`, `SectorSnapshot`, `MarketSnapshot`, and volume/history models.
- **API CHANGE:** Internal provider selection first; a diagnostic snapshot endpoint may follow after contracts stabilize.
- **FRONTEND CHANGE:** None in the foundation phase.
- **TESTS:** ABC contract, deterministic provider behavior, provider selection, freshness/as-of propagation, no Search-price coupling.
- **DEPENDENCIES:** Phase 1 canonical instruments.
- **RISK:** A demo adapter backed by portfolio data is acceptable initially but must not masquerade as live data.

### Phase 3 — Generic event stream

- **CURRENT STATE:** `MarketEvent` and deterministic decisions exist, but fixtures and orchestration remain HDFC-centric and the engine contains an event-id score override.
- **GAP:** Watchers must consume arbitrary normalized events from a stream/provider without symbol- or event-id-specific business logic.
- **FILES AFFECTED:** `events/schemas.py`, new `events/stream.py`, `events/engine.py`, `events/fixtures.py`, `agents/event_watcher.py`, simulation adapter.
- **MODEL/SCHEMA CHANGE:** Add generic `instrument`, structured metadata, provider provenance, observed/baseline values, and event stream batch/cursor types.
- **API CHANGE:** Internal stream ingestion and optional test-only fixture injection; existing event action API remains.
- **FRONTEND CHANGE:** Event details render instrument/company data generically.
- **TESTS:** Multiple symbols/types, idempotent ingestion, no event-id branch in engine, fixture-to-stream adapter, provider-independent decisions.
- **DEPENDENCIES:** Phase 2.
- **RISK:** Preserving the hero scenario’s expected decision while removing its hard-coded score requires rule calibration, not another fixture branch.

### Phase 4 — Real financial-day scheduler

- **CURRENT STATE:** A timezone-aware 30-second scheduler exists for six checkpoints. It omits market open, adaptive watch, sector/learning, portfolio intelligence, and action queue; orchestrator methods advance the simulation clock unconditionally.
- **GAP:** Configure the complete real-day checkpoint set and a bounded recurring market-watch window, with idempotent crash recovery.
- **FILES AFFECTED:** `day/scheduler.py`, `day/schemas.py`, `day/orchestrator.py`, `config.py`, `api.py` lifecycle.
- **MODEL/SCHEMA CHANGE:** Declarative schedule entries with checkpoint, local time/window, cadence, operation, and run-mode eligibility.
- **API CHANGE:** Existing day endpoints remain; expose schedule/readiness only if operationally useful.
- **FRONTEND CHANGE:** Timeline reads checkpoint definitions returned by state instead of recreating them.
- **TESTS:** Timezone boundaries, late startup catch-up, recurring-window cadence, restart idempotency, weekend policy, real mode never advances demo time.
- **DEPENDENCIES:** Phases 0–3.
- **RISK:** Catch-up operations can cause stale alerts after downtime; each operation needs a freshness policy.

### Phase 5 — TaskMaster autonomous operator

- **CURRENT STATE:** The ADK TaskMaster routes intents to tools/agents. `DayOrchestrator` executes fixed checkpoints but has no explicit observe/plan/verify/attention/follow-up record.
- **GAP:** Material goals need a durable operator cycle and a deterministic next-action policy.
- **FILES AFFECTED:** New `taskmaster/` domain package or `agents/taskmaster_operator.py`, `agents/taskmaster.py`, `day/orchestrator.py`, state schemas.
- **MODEL/SCHEMA CHANGE:** `TaskmasterDecision`, `OperatorCycle`, evidence/verification result, planned follow-up, and action/defer reason.
- **API CHANGE:** Add read-only operator/case state to day and alert responses; chat continues through ADK.
- **FRONTEND CHANGE:** Surface “monitoring”, “researching”, “deferred”, and next follow-up without exposing chain-of-thought.
- **TESTS:** Policy table for `INTERRUPT_NOW`, `MONITOR`, `RESEARCH_FIRST`, `DEFER_TO_EVENING`, `ASK_USER`, `PREPARE_ADVISOR_HANDOFF`, `CARRY_TO_TOMORROW`, `CLOSE_CASE`.
- **DEPENDENCIES:** Phases 1–4 and Phase 6 case schema.
- **RISK:** LLM routing must never override deterministic attention or financial decisions.

### Phase 6 — Financial cases

- **CURRENT STATE:** Events, research, saves, questions, and advisor exchanges are stored in separate day lists with no durable material-event aggregate.
- **GAP:** One case must retain trigger-to-close continuity across every surface and into tomorrow.
- **FILES AFFECTED:** New `cases/` or `day/cases.py`, `day/schemas.py`, `day/store.py`, `day/orchestrator.py`, interaction/advisor services.
- **MODEL/SCHEMA CHANGE:** `FinancialCase` with the requested identity, status, priority, trigger, exposure, evidence/sources, research, interactions, close result, tomorrow status, and timestamps.
- **API CHANGE:** Case list/detail endpoints; event detail can link its case id.
- **FRONTEND CHANGE:** Alerts and Timeline use case state rather than reconstructing it from event arrays.
- **TESTS:** Open/upsert/transition/close, illegal transitions, persistence round-trip, advisor/research linkage, carry-forward.
- **DEPENDENCIES:** Phase 3; then consumed by Phase 5.
- **RISK:** Schema migration of saved JSON state must be additive and tolerant of older state files.

### Phase 7 — Attention management

- **CURRENT STATE:** `AttentionSummary` counts high-priority stories and active events. There is no per-day notification budget or outcome ledger.
- **GAP:** Track processed, interrupted, deferred, monitored, and ignored signals and enforce interruption restraint.
- **FILES AFFECTED:** `day/active.py`, `day/schemas.py`, TaskMaster policy, event engine/orchestrator.
- **MODEL/SCHEMA CHANGE:** `AttentionBudget`, `AttentionDisposition`, limit/window settings, and auditable reason codes.
- **API CHANGE:** Add attention ledger/summary to day/dashboard responses.
- **FRONTEND CHANGE:** Today can show “17 processed, 1 interrupted” and emphasize restraint.
- **TESTS:** Budget enforcement, critical bypass, dedupe, daily reset, no notification for monitor/ignore.
- **DEPENDENCIES:** Phases 5–6.
- **RISK:** A rigid budget must never suppress a genuinely critical event; critical bypass stays deterministic and audited.

### Phase 8 — Morning intelligence

- **CURRENT STATE:** Parallel portfolio/market collection, deterministic relevance, a frozen morning artifact, and TTS preparation exist.
- **GAP:** Explicit overnight/India pre-market/company normalization and dedupe should feed an attention-ranked “few things” artifact with immutable checkpoint provenance.
- **FILES AFFECTED:** `agents/daily_brief_workflow.py`, market normalization/cache, media service, day orchestrator/state.
- **MODEL/SCHEMA CHANGE:** `MorningPulseSnapshot` containing candidate counts, selected reasons, portfolio snapshot id, source set, and attention dispositions.
- **API CHANGE:** Morning artifact endpoint or embedded day response.
- **FRONTEND CHANGE:** Today shows a compact attention summary, not an unbounded card feed.
- **TESTS:** Frozen snapshot, dedupe, portfolio matching, top-N constraints, source validity, deterministic fallback, TTS input integrity.
- **DEPENDENCIES:** Phases 1, 5, and 7.
- **RISK:** Live Search latency/failure; retain cached/last-known provenance and disclose freshness.

### Phase 9 — Portfolio health

- **CURRENT STATE:** Largest holding/sector and concentration flags exist; health enum is `NORMAL/WATCH/ATTENTION` and lacks benchmark/upcoming/unresolved inputs.
- **GAP:** Calculate the requested health set and classify `NO_ACTION/WATCH/INVESTIGATE` deterministically.
- **FILES AFFECTED:** portfolio analytics, `day/schemas.py`, `day/orchestrator.py`, dashboard schemas/service.
- **MODEL/SCHEMA CHANGE:** Rich `PortfolioHealthSnapshot` with calculation provenance and classification reasons.
- **API CHANGE:** Embed in portfolio/day responses.
- **FRONTEND CHANGE:** Portfolio and Today show consistent health facts.
- **TESTS:** Concentration thresholds, top-three sum, benchmark calculations, unresolved/upcoming inputs, classification table.
- **DEPENDENCIES:** Phases 1 and 6.
- **RISK:** Sector look-through must not double-count funds and direct holdings.

### Phase 10 — Market watch

- **CURRENT STATE:** Event watcher can assess a supplied fixture; it does not poll a quote feed to discover anomalies.
- **GAP:** Convert snapshots into candidate events using price, divergence, volume, news, regulation, and macro rules; most candidates stay silent.
- **FILES AFFECTED:** `market_data/`, `events/stream.py`, new detector, event watcher, scheduler/orchestrator.
- **MODEL/SCHEMA CHANGE:** Baseline/anomaly records and detection provenance.
- **API CHANGE:** Internal watch run; diagnostic endpoint only for operators/developers.
- **FRONTEND CHANGE:** Alerts only receives non-ignored case states.
- **TESTS:** Detection thresholds, index/sector comparisons, no-data behavior, stale snapshot rejection, silence rate.
- **DEPENDENCIES:** Phases 2–7.
- **RISK:** Provider rate limits and false positives; use cadence, batching, caching, and baselines.

### Phase 11 — Sector deep dive

- **CURRENT STATE:** Sector exposures exist but no checkpoint artifact selects a sector contextually.
- **GAP:** Rank sectors by exposure, active cases, developments, and recent user interest.
- **FILES AFFECTED:** new sector service/schema, orchestrator, media, dashboard/API.
- **MODEL/SCHEMA CHANGE:** `SectorDeepDive` with rank inputs, facts, sources, and optional audio id.
- **API CHANGE:** Day artifact/detail endpoint.
- **FRONTEND CHANGE:** Today/Timeline link a short sector explainer.
- **TESTS:** Portfolio relevance ordering, no random rotation, source/case linkage, deterministic tie-breaking.
- **DEPENDENCIES:** Phases 1, 6, and 10.
- **RISK:** Thin news days; exposure alone may select a sector but copy must state why.

### Phase 12 — Contextual learning

- **CURRENT STATE:** No dedicated contextual-learning artifact; chat can explain retained events.
- **GAP:** Generate education only from a real portfolio fact or retained case.
- **FILES AFFECTED:** new learning service/schema, Research/Media agents, day orchestrator.
- **MODEL/SCHEMA CHANGE:** `LearningMoment` with concept, triggering case/artifact, deterministic facts, explanation, and sources.
- **API CHANGE:** Day artifact/detail endpoint.
- **FRONTEND CHANGE:** Today/Timeline learning card with clear educational boundary.
- **TESTS:** Requires source context, blocks generic filler, no advice, fact preservation.
- **DEPENDENCIES:** Phases 5–6 and 11.
- **RISK:** Model drift into advice; prompts and output validation must enforce explanation-only scope.

### Phase 13 — Market close

- **CURRENT STATE:** Holding-level contribution is deterministic but uses open weights and simulated copy; sector contribution and case resolution are absent.
- **GAP:** Canonically calculate portfolio/holding/sector contribution and carry the day’s 2–3 actual drivers and case outcomes.
- **FILES AFFECTED:** portfolio analytics, `day/schemas.py`, `day/orchestrator.py`, media/story builders.
- **MODEL/SCHEMA CHANGE:** Add value contribution, sector contribution, driver reasons, data snapshot ids, and case result links.
- **API CHANGE:** Expanded close artifact.
- **FRONTEND CHANGE:** Contribution chart/table derives directly from the artifact.
- **TESTS:** Decimal contribution reconciliation, sector sums, top-driver ordering, zero/missing close handling, model never calculates values.
- **DEPENDENCIES:** Phases 1, 6, and 10.
- **RISK:** Weight timing methodology must be explicit and consistent (start-of-day weights for return attribution).

### Phase 14 — Portfolio intelligence

- **CURRENT STATE:** Pieces exist across portfolio summary, health, events, and tomorrow lists; no 17:00 consolidated artifact.
- **GAP:** Consolidate concentration, diversification, allocation, benchmark divergence, upcoming events, watched signals, and research gaps without recommendations.
- **FILES AFFECTED:** new analytics/intelligence service, day state/orchestrator, API/dashboard.
- **MODEL/SCHEMA CHANGE:** `PortfolioIntelligenceSnapshot` with metrics, observations, gaps, and provenance.
- **API CHANGE:** Portfolio/day intelligence endpoint.
- **FRONTEND CHANGE:** Portfolio destination consumes the same snapshot/analytics.
- **TESTS:** Cross-artifact consistency, gap generation, advice boundary.
- **DEPENDENCIES:** Phases 1, 6, 9, 10, and 13.
- **RISK:** Duplication; metrics must live in one analytics layer and be referenced elsewhere.

### Phase 15 — Action queue

- **CURRENT STATE:** Saved items, unresolved strings, questions, cases, and advisor records exist separately.
- **GAP:** Normalize them into deduplicated actions and let deterministic policy choose research/review/monitor/advisor/carry/close.
- **FILES AFFECTED:** new action queue service/schema, TaskMaster policy, day state/orchestrator.
- **MODEL/SCHEMA CHANGE:** `ActionQueueItem`, source links, disposition, due checkpoint/date, owner, and completion state.
- **API CHANGE:** Queue list and explicit user-action endpoints.
- **FRONTEND CHANGE:** 18:30 queue with safe actions and no trade buttons.
- **TESTS:** Deduplication, policy mapping, explicit advisor confirmation, carry-forward, close.
- **DEPENDENCIES:** Phases 5–7, 12, and 14.
- **RISK:** Automatic external communication remains prohibited; advisor send keeps its existing confirm step.

### Phase 16 — Evening wrap

- **CURRENT STATE:** Evening audio uses retained day state, but coverage and saved-item counts have inconsistent tests/state sources.
- **GAP:** Build one frozen wrap from all day artifacts/cases/interactions and use exactly that script for TTS.
- **FILES AFFECTED:** media script/service/schemas, day orchestrator, story builder.
- **MODEL/SCHEMA CHANGE:** `EveningWrapSnapshot` with included artifact/case ids and omissions/freshness.
- **API CHANGE:** Existing audio APIs can return/link the snapshot.
- **FRONTEND CHANGE:** Today/Timeline show matching text and audio.
- **TESTS:** Full-state coverage, snapshot freeze, saved-item consistency, script/audio source equality, fallback.
- **DEPENDENCIES:** Phases 6–15.
- **RISK:** Long scripts; use an attention-ranked cap while preserving unresolved critical cases.

### Phase 17 — Tomorrow preparation

- **CURRENT STATE:** A deterministic list is hard-coded around HDFC/RBI/Infosys.
- **GAP:** Generate monitoring tasks from upcoming events and carry-forward cases, including check times and interruption conditions.
- **FILES AFFECTED:** tomorrow planner/service/schema, TaskMaster policy, day orchestrator.
- **MODEL/SCHEMA CHANGE:** `TomorrowMonitoringPlan` and `MonitoringTask` with source, scheduled check, comparison, case, and interrupt rule.
- **API CHANGE:** Expanded tomorrow artifact.
- **FRONTEND CHANGE:** Timeline/Tomorrow view shows the plan and carry-forward state.
- **TESTS:** Generic instruments, ranking, case continuity, deterministic interruption conditions, no hard-coded fixture ids.
- **DEPENDENCIES:** Phases 5–6, 10, 14, and 15.
- **RISK:** Market calendars/timezones; integrate a trading-calendar policy before production.

### Phase 18 — Mobile product information architecture — COMPLETE

- **CURRENT STATE:** Today, Portfolio, Copilot, Alerts, alert detail, and Timeline are separate App Router destinations under a persistent responsive shell. The original dashboard remains isolated as a developer presentation fixture.
- **GAP:** None for the route split; future work can generate TypeScript contracts directly from OpenAPI and add component-level Vitest/RTL coverage.
- **FILES AFFECTED:** `frontend/app`, `components/dashboard.tsx`, new destination components, `lib/types.ts`, `lib/api.ts`, CSS.
- **MODEL/SCHEMA CHANGE:** None beyond stable phase artifacts.
- **API CHANGE:** Consume case/artifact endpoints from earlier phases.
- **FRONTEND CHANGE:** Route-level five-destination shell, mobile-first navigation, generic content, accessible loading/error states.
- **TESTS:** Mobile navigation, deep links, context continuity, no long-dashboard regression, accessibility smoke.
- **DEPENDENCIES:** Backend contracts from Phases 1–17.
- **RISK:** Premature redesign would duplicate temporary contracts; this phase deliberately waits.

### Phase 19 — Portfolio visualization

- **CURRENT STATE:** Summary metrics and some allocation/performance shapes exist; canonical time series/contribution/drawdown contracts are incomplete.
- **GAP:** Build charts only from portfolio analytics/provider data.
- **FILES AFFECTED:** portfolio schema/analytics/API, frontend chart components.
- **MODEL/SCHEMA CHANGE:** Value/benchmark time series, allocation/sector/contribution series, holding performance, concentration, drawdown.
- **API CHANGE:** Portfolio analytics endpoint or expanded portfolio response.
- **FRONTEND CHANGE:** Responsive accessible charts with tabular equivalents and freshness/source labels.
- **TESTS:** Series reconciliation, sorting, missing data, chart-table equality, no fixture literals in frontend.
- **DEPENDENCIES:** Phases 1, 13, 14, and 18.
- **RISK:** Visual precision and rounding; API retains exact values and UI formatting is consistent.

### Phase 20 — Alert detail

- **CURRENT STATE:** Dashboard renders a rich but HDFC-specific alert panel with exposure, contribution, facts, and actions.
- **GAP:** A generic case-backed detail must include comparison, deterministic impact, relevance breakdown, uncertainty, sources, and case timeline.
- **FILES AFFECTED:** case/event API schemas, dashboard service, alert route/components.
- **MODEL/SCHEMA CHANGE:** `AlertDetail` projection from `FinancialCase`, assessment, market snapshot, and portfolio snapshot.
- **API CHANGE:** `GET /api/v1/cases/{case_id}` or alert-detail endpoint; safe action endpoints remain.
- **FRONTEND CHANGE:** Generic Explain/Research/Copilot/Advisor/Save actions; never Buy/Sell.
- **TESTS:** Projection integrity, source links, uncertainty, safe actions, generic symbol rendering.
- **DEPENDENCIES:** Phases 3, 6, 13, 18, and 19.
- **RISK:** Estimated impact must state methodology and never imply a forecast.

### Phase 21 — Safety

- **CURRENT STATE:** Agent instructions and UI omit trading actions; advisor sending requires review/confirmation.
- **GAP:** Centralize enforceable capability boundaries and test every action surface.
- **FILES AFFECTED:** TaskMaster/agent instructions, interaction schemas/service, advisor service, API, frontend actions.
- **MODEL/SCHEMA CHANGE:** Structured refusal/safety reason codes where needed.
- **API CHANGE:** Reject trade/order intents and unsupported recommendations consistently.
- **FRONTEND CHANGE:** Preserve information, research, analytics, scenario explanation, and advisor handoff only.
- **TESTS:** Prompt/tool boundary tests, API action allowlist, no autonomous send/trade, recommendation wording regression.
- **DEPENDENCIES:** Cross-cutting; revalidate after every phase.
- **RISK:** Prompt-only controls are insufficient; code-level allowlists remain authoritative.

### Phase 22 — Data consistency

- **CURRENT STATE:** Backend objects are mostly canonical, but static simulated aggregates, duplicate frontend inference, interaction stores, and day-state lists can disagree.
- **GAP:** Define lineage for every visible value and enforce snapshot identity/reconciliation across agents, API, state, media, charts, and chat.
- **FILES AFFECTED:** provider schemas, analytics, day provenance/integrity, dashboard projections, frontend types, test suites.
- **MODEL/SCHEMA CHANGE:** Consistent snapshot/artifact ids, as-of timestamps, provider labels, and calculation version.
- **API CHANGE:** All projections carry provenance/freshness needed for integrity checks.
- **FRONTEND CHANGE:** Never recalculate or fixture financial facts; format API values only.
- **TESTS:** End-to-end integrity matrix, provider-to-dashboard equality, alert exposure equality, media fact equality, chart reconciliation, retained chat context equality.
- **DEPENDENCIES:** Enforced incrementally; final closure after Phases 1–21.
- **RISK:** Cached artifacts intentionally differ over time; compare snapshot ids/as-of values rather than assuming all artifacts are current.

## Dependency-aware implementation order

1. **Guardrails and baseline:** preserve the dirty worktree, record baseline failures, isolate presentation mode, add safety/integrity test helpers (Phases 0, 21, 22 scaffolding).
2. **Canonical data spine:** portfolio domain, market-data provider, generic event stream (Phases 1–3).
3. **Durable operating spine:** full real scheduler, FinancialCase, TaskMaster operator cycle, attention budget (Phases 4, 6, 5, 7).
4. **Opening and monitoring loop:** morning intelligence, portfolio health, market watch (Phases 8–10).
5. **Midday context:** sector deep dive and contextual learning (Phases 11–12).
6. **Close and planning loop:** market close, portfolio intelligence, action queue, evening wrap, tomorrow plan (Phases 13–17).
7. **Stable product surfaces:** mobile IA, canonical visualization, generic alert detail (Phases 18–20).
8. **Final integrity closure:** full cross-surface lineage, resilience, performance, accessibility, and safety acceptance (Phases 21–22).

## Phase delivery rules

For each implementation phase:

1. Add or update the schema/contract first.
2. Add focused contract and invariant tests.
3. Implement behind the provider/service boundary.
4. Run focused tests, then the full backend suite and relevant frontend checks.
5. Record baseline versus new failures; do not “fix” tests by copying obsolete fixture numbers.
6. Preserve working demo behavior through explicit fixture adapters.
7. Do not start the frontend redesign until Phases 1–7 contracts are stable.
