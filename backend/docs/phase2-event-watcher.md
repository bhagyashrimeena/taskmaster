# Phase 2: Event Watcher

Phase 2 answers: **“Something happened—does it matter enough to interrupt me?”**
It is separate from Phase 1's user-requested daily brief.

## Execution path

```text
MarketEvent fixture
  -> deterministic trigger rules
  -> portfolio exposure
  -> fixture Market investigation (offline)
  -> existing RelevanceEngine
  -> IGNORE / MONITOR / INVESTIGATE / ALERT
  -> internal alert object + event trace + daily state
```

No notification is sent. `notification_required=true` creates only an internal
alert decision for the future UI/notification layer.

## Trigger rules

- direct holding move of at least 3%;
- high-priority direct holding move of at least 5%;
- at least 2 percentage points of stock-versus-sector divergence;
- at least 100% volume increase for a direct holding;
- earnings, corporate, regulatory, or other material direct news;
- macro event affecting at least 15% portfolio sector exposure.

The decision engine distinguishes a small sector-aligned move from a
company-specific move before deciding whether to investigate or alert.

## Deterministic fixtures

Ten fixtures cover all four outcomes. The hero fixture is
`hdfc-bank-sudden-fall`: HDFCBANK -5.4%, banking sector -0.8%, 18.01% direct
portfolio exposure, 28.01% financial-sector exposure, two investigated
developments, relevance 94.21, decision `ALERT`.

## Run

In ADK:

```text
Run the HDFC Bank hero Event Watcher scenario.
```

Or run the real TaskMaster acceptance route:

```powershell
python scripts\phase2_acceptance.py
```

The core engine and fixtures run offline. Only the TaskMaster's conversational
rendering uses Gemini.

