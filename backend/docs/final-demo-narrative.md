# Wealth Copilot: final judge narrative

This is the single golden path for the submission video and live judging. Use the
`hdfc-company-shock` scenario and open the dashboard with `?presentation=true`.
The portfolio and event feed are deterministic; the normal market-news path remains
Google Search grounded.

## Preflight

With both services running, click **Restart** once and leave the presentation
paused at 07:00. From `frontend/`, run `npm run demo:prewarm`. Continue only when
it reports `ready`; keep that run and begin with **Next** rather than restarting
again. This prewarms live news and Morning Pulse audio without advancing the
financial-day clock.

## 2–3 minute script

**Opening — 10 seconds**

> Wealth Copilot runs the user's financial day autonomously. It combines a
> provider-neutral portfolio, grounded market intelligence, deterministic relevance,
> and TaskMaster orchestration. For this presentation, I am accelerating the market
> clock; the underlying checkpoints are the same ones used by the real scheduler.

**07:00 Morning Pulse — 20 seconds**

Press **Play** or **Next**. Let Morning Pulse finish without manually invoking a
feature.

> At 7 AM, Wealth Copilot scans the market. It reduces roughly 14–15 candidate
> stories to five that match this portfolio, then highlights the three signals that
> deserve more attention. The dashboard was already usable before this refresh began.

**08:00 Portfolio Health — 10 seconds**

Press **Next**.

> At 8 AM, it checks portfolio concentration and overnight context. This is an
> attention classification, not an investment recommendation.

**12:17 proactive event — 35 seconds**

Press **Next**, then pause and let the alert appear before speaking.

> I did not ask Wealth Copilot a question here. It detected HDFC Bank falling 5.4%
> while the broader banking sector moved only 0.8%. It checked my 17.21% direct
> exposure, investigated the market context, calculated 93.11 relevance, and decided
> this deserved an alert.

Click **View**, then **Explain**. Ask: “What caused this?” Continue with **Learn more**
to show the Research Agent, then **Ask advisor** to prepare the human handoff packet.

> The system stays inside its boundary: it explains facts and uncertainty, preserves
> sources, and can ask a human for perspective. It does not say buy, sell, hold, or
> rebalance.

**15:30 Market Close — 20 seconds**

Press **Next**.

> At the close, Wealth Copilot explains what moved the portfolio and links the result
> back to the event it surfaced at 12:17. The same FinancialDayState carries context
> across the entire day.

**20:00–21:01 wrap and story — 25 seconds**

Advance through Evening Wealth Wrap, Tomorrow Prep, and Daily Wealth Story.

> In the evening, it prepares an audio wrap using the events, questions, saves, and
> advisor interactions from today. It then ranks tomorrow's relevant events and turns
> the day into a short visual story.

**Close — 10 seconds**

> Wealth Copilot is not another financial-news dashboard. It is an autonomous
> attention system: it watches the user's financial day, interrupts only when a signal
> matters to their portfolio, and explains why.

## Architecture explanation

```text
User surfaces: Dashboard / Chat / Audio
                    |
               TaskMaster (ADK)
                    |
    +---------------+----------------+
    |               |                |
Portfolio Agent  Market Agent   Research Agent
    |               |                |
Provider contract  Search grounding  Sources
    +-------+-------+                |
            v                        v
   deterministic relevance + Event Watcher
                    |
             FinancialDayState
                    |
       +------------+-------------+
       |            |             |
   Media/TTS   Advisor handoff  Day Orchestrator
                                  |
                    real scheduler / presentation clock
```

Agents are used where judgment, search, or explanation is required. Known transitions,
matching, scoring, diversity, scheduled checkpoints, and replay idempotency remain
deterministic.

## Evidence to cite

- Five portfolio-relevant stories selected from roughly 14–15 candidates.
- Three signals elevated for attention in the golden path.
- HDFC Bank direct exposure: **17.21%**.
- HDFC Bank sector exposure: **27.26%**.
- HDFC Bank event relevance: **93.11/100**.
- HDFC Bank contribution at close: approximately **-0.97 percentage points**.
- **133 backend tests** plus frontend lint, typecheck, production build, and browser smoke tests.
- Browser-verified presentation flow: one event, one shared run ID, no duplicate
  checkpoints, no console errors, and presentation controls hidden in normal mode.

## Voice decision

Voice is not required for the judging path. If a realtime AI call becomes necessary,
LiveKit remains the appropriate branch. Google Meet belongs to the human-advisor branch,
not as a substitute for realtime AI voice.
