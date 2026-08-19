# Phase 6 — Financial Day Orchestrator

Phase 6 adds a deterministic operations layer over the existing portfolio,
daily brief, Event Watcher, interaction, and media capabilities. It does not
add an LLM router or make investment decisions.

## Day continuity

`FinancialDayState` is stored atomically in `.cache/days/YYYY-MM-DD.json`.
Each write is validated and replaces the previous snapshot only after the new
file is complete. An unreadable file is preserved for diagnosis and returned
as a safe empty state with an error marker.

The state retains:

- morning and evening brief IDs;
- open and close portfolio snapshots;
- portfolio health and concentration flags;
- considered news and top story IDs;
- detected, alerted, and ignored events;
- user saves and questions;
- market-close attribution;
- ranked events for tomorrow; and
- status and trace details for every scheduled checkpoint.

## Operations

`DayOrchestrator` runs six fixed operations:

1. `run_morning_pulse()`
2. `run_portfolio_health()`
3. `handle_market_event()`
4. `run_market_close()`
5. `run_evening_wrap()`
6. `prepare_tomorrow()`

Demo close attribution uses explicit simulated daily returns. Contribution is
calculated as `portfolio_weight × daily_return / 100`, expressed in portfolio
percentage points. HDFCBANK's 18.01% weight and -5.4% return therefore produce
approximately -0.97 percentage points.

## API

- `GET /api/v1/day` — current durable state
- `GET /api/v1/day/{YYYY-MM-DD}` — a specific day
- `POST /api/v1/day/demo` — start the non-blocking 60–90 second demo
- `POST /api/v1/day/steps/{step}` — run one checkpoint manually

Valid manual steps are `morning`, `health`, `event`, `close`, `evening`, and
`tomorrow`.

## Scheduling

Set `DAY_SCHEDULE_MODE=real` to enable the application clock scheduler. It
uses `DAY_SCHEDULE_TIMEZONE` and runs Morning Pulse at 07:00, Portfolio Health
at 08:00, Market Close at 15:30, Evening Wrap at 20:00, and Tomorrow Prep at
21:00. Market events remain event-driven.

The default is `disabled`, which is safer for local development. Demo Day is
always started explicitly from the dashboard or API and defaults to 72 seconds.

Every demo checkpoint has a bounded timeout (`DEMO_STEP_TIMEOUT_SECONDS`, 45
seconds by default). An interrupted API process resumes from the first
unfinished checkpoint on startup. A timed-out or cancelled checkpoint becomes
a visible, retryable failure instead of remaining in `running` indefinitely.

All output explains relevance and portfolio impact. It does not provide Buy,
Sell, Hold, rebalance, or execution instructions.
