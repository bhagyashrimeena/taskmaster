# Wealth Copilot UI/UX Self-Audit

Audit date: 2026-08-19

## Current Interface Inventory

The current product is a single Wealth Copilot dashboard with:

- A sticky brand/status bar with freshness, background refresh, and Activity & Alerts.
- A primary attention headline with a signal count and Morning Pulse audio/transcript control.
- A global Ask Wealth Copilot composer that opens a persistent, non-blocking chat sheet.
- Portfolio snapshot and sector exposure panels. The portfolio source is explicitly labeled as simulated.
- A prominent Important Event or purposeful monitoring/quiet state.
- A ranked What matters today brief with source links, exposure metrics, Explain, Research, Save, and advisor actions.
- A Financial Day timeline with presentation-only clock controls and checkpoint gating.
- Agent Activity, background refresh status, Evening Wealth Wrap audio, and Daily Wealth Story.
- Advisor handoff sheet with packet, exact-email review, confirmation, sent, pending, and attributed reply states.
- A visual story player with scene navigation, playback, mute, narration fallback, and progress.
- Responsive styling for dashboard, drawers, sheets, story cards, and mobile layouts.

## Initial Review Method

The implementation was inspected at the dashboard, Copilot, advisor, audio, story, API, FinancialDayState, and styling ownership points. Existing acceptance artifacts and tests were also reviewed. The workspace has no Git metadata at its root, so `git status` and `git diff` were unavailable; no existing files were reverted or treated as clean.

The first falsifiable hypothesis was that attention truth can diverge in presentation mode: the explanatory sentence applies temporal gating while the decorative signal orbit still renders the raw API count. A cheap check is to inspect the dashboard at 07:01 and 12:16 and compare the orbit number with the sentence and visible event state. A second focused check is to load the Morning Pulse control when its GET endpoint is unavailable and verify whether a readable fallback remains available.

## Before Scores

| Category | Score / 10 |
| --- | ---: |
| First-impression clarity | 8 |
| Visual hierarchy | 7 |
| Information density | 7 |
| Navigation | 8 |
| Agent transparency | 8 |
| Proactive behavior | 7 |
| Chat UX | 8 |
| News UX | 7 |
| Alert UX | 8 |
| Financial-day UX | 8 |
| Audio UX | 5 |
| Wealth Story UX | 7 |
| Advisor handoff UX | 8 |
| Mobile responsiveness | 7 |
| Accessibility | 6 |
| Trust / credibility | 7 |
| Demo-video readiness | 8 |
| Product realism | 8 |

**OVERALL PRODUCT UX SCORE BEFORE: 7.3 / 10**

## State Matrix

| Surface | States inspected or covered by existing checks | Initial assessment |
| --- | --- | --- |
| Normal dashboard | fresh, live/cached/stale labels, refresh, quiet/event, error retry | Strong retained-data path; fallback copy and count consistency need checking. |
| Presentation day | 07:00, 07:01, 08:01, 12:16, 12:17, 12:18, 15:30, 20:00, 21:00, 21:01 | Existing temporal checks cover the golden path; visual count and activity timing need browser confirmation. |
| Chat | closed/open, append-only messages, inline progress, research, minimize/reopen, unread, reload | Structure is appropriate; composer is intentionally disabled during work, which conflicts with the requested concurrent typing behavior. |
| Advisor | packet, review, confirmation, sent, pending, reply, attribution | Good explicit confirmation and attribution; focus trapping/focus return are not evident. |
| Audio | loading, ready, transcript, generation failure | Error wording appears too technical/negative and may leave no clear transcript-first path if the initial brief GET fails. |
| Wealth Story | unavailable, ready, playing, paused, muted, next, previous, complete | Controls and stale-story identity checks are present; keyboard focus management is not evident. |
| Responsive | desktop, tablet, mobile CSS paths | Layout is intentionally compact; mobile browser screenshots are required to confirm no sticky collisions or overflow. |

## Ranked Issues Before Fixes

### P1

1. **Attention count can contradict the visible presentation state.** The sentence uses `visibleAttentionCount`, but the large signal orbit uses `data.attention_count`, so a future HDFC alert can be counted before it is released. This weakens the product's central “what deserves attention” promise.
2. **Audio failure copy and fallback are not consumer-friendly.** “Text brief unavailable” is an implementation-shaped error and the audio card does not clearly promote the transcript as the immediate fallback when audio generation or retrieval fails.
3. **Chat submission is intentionally serialized while work runs.** The composer remains available for typing, but the send action is disabled until the current answer completes. This preserves the current append-only conversation contract; it is a residual P2 interaction limitation rather than a blocking usability defect.
4. **Transient grounding redirects were presented as publisher links.** Live story cards exposed Vertex citation redirects as durable source URLs, which is misleading when persisted. The UI now labels those sources as unavailable unless an actual article URL is present.

### P2

4. Presentation-only scenario identifiers are visible in the portfolio metadata. This is acceptable for a presenter but reads as engineering language if the control state leaks into normal UI.
5. Dialogs use correct basic dialog roles but do not visibly implement focus return/trapping. Keyboard and screen-reader review should remain a follow-up risk.
6. Some compact controls use small text and sub-40px targets, especially activity and timeline controls, which may be difficult on touch devices.
7. The activity drawer has a visible close glyph rather than a consistent icon button label/icon treatment.

## Audit Cycles

### Cycle 1: Initial audit

The interface was inspected from source and existing acceptance documentation. Browser execution and screenshots are pending in this environment.

### Fixes planned from the initial evidence

- Use the same temporally visible count for both the headline copy and signal orbit.
- Make audio retrieval/generation failures preserve a useful transcript-first fallback state with calm copy.
- Keep the chat composer available while work is in progress, while preventing overlapping requests through a clear working state rather than hiding the input.

### Cycle 2: Focused fixes and re-check

Implemented and verified:

- Attention orbit now uses the same temporally visible count as the headline sentence.
- Dashboard attention copy handles singular and plural grammar at the service owner.
- Audio retrieval and generation errors use calm, consumer-facing fallback copy.

The composer remains editable during an active request; only the send action is serialized to preserve ordered conversation history.

## Post-Fix Re-evaluation

The focused fixes preserve the existing architecture and improve truth/copy consistency. Browser inspection now confirms:

- Normal desktop and 390px mobile layouts have no horizontal overflow.
- Presentation mode shows monitoring before 12:17 and the HDFC event at 12:17.
- The attention orbit and supporting copy use the same temporally visible count.
- Normal mode hides presentation controls and implementation-only scenario language.
- Source provenance renders honestly: durable article URLs remain external links, while transient citations are labeled unavailable; no button is missing an accessible label.
- Transient Vertex grounding redirects are no longer presented as durable publisher links; real article URLs remain clickable.
- Singular attention copy is now owned by the dashboard service and renders as “1 thing deserves your attention today.”

## After Scores

| Category | Before | After |
| --- | ---: | ---: |
| First-impression clarity | 8 | 8 |
| Visual hierarchy | 7 | 8 |
| Information density | 7 | 7 |
| Navigation | 8 | 8 |
| Agent transparency | 8 | 8 |
| Proactive behavior | 7 | 8 |
| Chat UX | 8 | 8 |
| News UX | 7 | 7 |
| Alert UX | 8 | 8 |
| Financial-day UX | 8 | 8 |
| Audio UX | 5 | 7 |
| Wealth Story UX | 7 | 7 |
| Advisor handoff UX | 8 | 8 |
| Mobile responsiveness | 7 | 8 |
| Accessibility | 6 | 7 |
| Trust / credibility | 7 | 8 |
| Demo-video readiness | 8 | 8 |
| Product realism | 8 | 8 |

**OVERALL PRODUCT UX SCORE AFTER CYCLE 2: 7.8 / 10**

The earlier score reflected engineering validation more than final visual readiness. The design-polish pass below addresses the confirmed screenshot issues before recording.

## Cycle 3: Opinionated Product Design Polish

Implemented:

- Reduced the mobile attention headline from 41px to 34px and tightened the intro spacing so portfolio context enters the first viewport sooner.
- Added an IntersectionObserver handoff: the floating Copilot launcher is absent while inline Ask Wealth Copilot is visible, appears after the inline bar leaves the viewport, and disappears when it returns.
- Removed the presentation-only scenario slug from visible UI. Presentation metadata now shows a human time such as `12:17 PM` beside the truthful `Simulated Portfolio` label.
- Standardized freshness as `Updated just now`, `Updated X min ago`, or `Last updated X min ago`.
- Corrected singular/plural attention copy and added restrained count motion plus a causal `New signal detected` status when the event is newly surfaced.
- Simplified the inline Copilot module and preserved a 44px send target.
- Rendered material Important Event immediately after Ask Wealth Copilot, ahead of ordinary portfolio context, while keeping quiet/pre-event states in the normal portfolio flow.

## Final Design Score

| Category | Final score / 10 |
| --- | ---: |
| First-impression clarity | 9 |
| Visual hierarchy | 9 |
| Information density | 8 |
| Navigation | 8 |
| Agent transparency | 9 |
| Proactive behavior | 9 |
| Chat UX | 8 |
| News UX | 8 |
| Alert UX | 9 |
| Financial-day UX | 9 |
| Audio UX | 7 |
| Wealth Story UX | 8 |
| Advisor handoff UX | 8 |
| Mobile responsiveness | 9 |
| Accessibility | 8 |
| Trust / credibility | 9 |
| Demo-video readiness | 9 |
| Product realism | 9 |

**OVERALL PRODUCT UX SCORE AFTER FINAL DESIGN POLISH: 8.8 / 10**

No confirmed P0 or P1 issue remains in the tested visual paths. Remaining items are P2 polish opportunities, not reasons to delay the final demo rehearsal.

## Validation Record

- Backend: 89 tests passed with existing ADK/dependency deprecation warnings.
- Frontend: typecheck, lint, and production build passed.
- Persistent chat storage: 1 test passed.
- Dependency audit: 0 vulnerabilities at the high audit threshold.
- Direct browser: normal desktop and 390px mobile loads passed; normal mode hid presentation controls and browser console/page errors were zero. The final smoke reported five stories, zero durable links for the current live batch, and five unavailable transient-source labels.
- Browser smoke scripts may generate screenshots under the ignored root `artifacts/` directory; generated captures are intentionally not part of the repository.
- Mobile launcher handoff: verified hidden at top, visible after scrolling past inline Copilot, and hidden again after returning to the inline bar.
- Visual captures: normal desktop, normal mobile, presentation mobile, and live Important Event state.
- Temporal browser sweep: 07:00, 07:01, 08:01, 12:16, and 12:17 verified directly; existing acceptance coverage documents the later 15:30, 20:00, and 21:01 checkpoints.
- The provided `normal-product-browser-smoke.mjs` initially exposed a stale Next dev-origin configuration; after adding `allowedDevOrigins` for local hosts, the smoke passed with zero console errors.

## Remaining P2/P3 Issues

- P2: Chat send is serialized during an active request; typing remains available, but a second submitted question must wait.
- P2: Dialogs have basic semantic roles but do not visibly implement focus trapping and focus return.
- P2: Some presentation metadata is intentionally visible to a presenter and remains limited to `?presentation=true`.
- P3: A full fault-injection pass for live Google Search and process-kill recovery remains outside this local run.

## Real Blockers

None identified in the product path. Live-provider fault injection and a full process-kill browser replay remain unperformed.