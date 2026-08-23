# Wealth Copilot final UI/UX polish

Date: 2026-08-23

## Before observations

Baseline screenshots were captured before application edits at 390x844, 430x932, 768x1024, and 1440x1000 under `artifacts/ui-ux-final-polish/before/`.

### Global shell and hierarchy

- The floating mobile navigation obscures the performance chart and several timeline rows in the captured viewport. Its active background is visually heavier than the surrounding content and labels become crowded at narrow widths.
- Most surfaces use the same large radius, padding, border, and shadow, so primary information, secondary context, and utilities have similar visual weight.
- Serif typography appears on page headings, card headings, quiet states, chart headings, and functional status summaries. This makes the product feel editorial rather than operational.
- Loading uses a large spinner card instead of preserving the destination layout. Focus styling is inconsistent across links, controls, disclosures, and the composer.

### Today

- The desktop hero consumes roughly one third of the first viewport while communicating only the greeting, attention count, and audio action.
- The portfolio strip is visually lighter than story cards even though portfolio movement is the next most important fact.
- The quiet market state has no supporting monitoring facts. “Since this morning” can become an almost empty card, leaving the desktop right rail visually unfinished.
- Story cards repeat large serif headlines and generous padding, causing supporting reading to compete with genuine alerts.

### Portfolio

- The mobile performance plot sits behind the bottom navigation. Its connected horizon-return points can be mistaken for a time series, while the existing range state is not represented in the UI.
- The top metrics are accurate but split across inconsistent typographic levels.
- Allocation and sector views are useful but their headings and surrounding cards consume unnecessary vertical height.
- Fourteen holdings appear in one repetitive list with no asset-class scanning structure.

### Copilot

- The empty conversation reserves a 68vh panel and centers a non-functional microphone icon in large whitespace.
- Suggested questions sit below or beside that empty region, so the first mobile viewport does not offer an immediate useful action.
- Voice appears actionable even though this release only supports text input.

### Alerts and alert detail

- Four independent filter pills overflow horizontally; “Monitoring” and “Filtered” are clipped at 390px.
- The empty state is accurate but provides no verified scope such as holdings, sectors, or financial-day monitoring status.
- Populated cards and alert detail use serif typography for operational event headings. Raw relevance trace stage names can expose implementation terminology.

### Timeline

- The hero exposes `Mode: real`, which is an implementation detail.
- Every checkpoint uses essentially the same icon treatment, so scheduled checks, event monitoring, learning, closing review, and future preparation are hard to distinguish.
- The long timeline card and bottom navigation collide visually on mobile, and the story card adds another large editorial heading below it.

## Implementation review log

### Iteration 1 — shared system

- Added shared card, quiet-card, radius, shadow, spacing, metric-label, section-heading, focus-ring, and skeleton treatments in the product shell.
- Replaced the large spinner state with a compact layout-matching skeleton. Query screens now retain successful cached data during background failures and surface a non-blocking freshness notice.
- Fixed mobile navigation height and active-state geometry, added safe-area-aware page clearance, and preserved five equal destinations from 320px through 768px.
- Separated semantic workflow states from financial-positive color. `COMPLETE` uses brand green; alert, investigate, monitor, failed, positive, and negative states retain distinct meanings.
- Moved global anchor and button color defaults into the CSS base layer so component text-color utilities are no longer overridden.

### Iteration 2 — destination polish

- **Today:** reduced the hero, promoted the consolidated portfolio strip, made quiet monitoring measurable with holdings/read/checkpoint context, kept stories secondary, and joined the morning activity and next checkpoint into one compact timeline surface.
- **Portfolio:** replaced the misleading connected horizon plot with grouped return bars, wired the existing range store to the 1D/1W/1M/3M/1Y highlight, tightened legends, and grouped holdings from backend `asset_class` into native disclosures. Only Direct equities starts open.
- **Copilot:** removed the oversized empty voice area and non-functional microphone affordance. Context, “Talk about today,” prompts, and the text composer now appear together in the first working surface while Zustand conversation persistence remains intact.
- **Alerts:** replaced clipped pills with a three-option segmented control and a separate Filtered action. The quiet state composes holdings and sectors from cached Portfolio plus monitoring status from cached Timeline. Populated cases prioritize decision, company/event, movement, exposure, reason, time, and action.
- **Alert detail:** flattened the layout, kept movement and exposure dominant, added an accessible intraday summary, retained deterministic-rule disclosure, and translated engine stages such as `EVENT_DETECTED` into customer labels.
- **Timeline:** removed run-mode wording, compacted the progress hero, and categorized checkpoints as scheduled briefings, automatic market checks, portfolio insights, day reviews, daily stories, or future preparation with distinct icon/color treatments.

### Iteration 3 — responsive and accessibility review

- Added `@axe-core/playwright` and `npm run test:e2e:polish` for the final product matrix.
- Audited all five routes at 320, 360, 390, 430, 768, 1024, and 1440px for overflow, five-route navigation, focus visibility, bottom-navigation clearance, and responsive headings.
- Increased audio, transcript, route, composer, filter, disclosure, and navigation controls to at least 44px where they are actionable on mobile.
- Strengthened muted and semantic status contrast after automated checks identified narrow failures. The final WCAG A/AA Axe run reports zero violations on the five destinations plus empty Alerts, populated Alerts, and alert detail.
- Disabled chart animation and verified reduced-motion mode has no running animations. Charts now provide a programmatic name plus hidden value summaries/tables.
- Verified fixed portfolio contract values are rendered unchanged, the fixture decision remains `ALERT`, raw trace stages are absent, and the alert detail deep link resolves.
- Review stopped after this third iteration as required.

## After comparison

The final screenshots are stored under `artifacts/ui-ux-final-polish/after/`. Matching five-route comparisons exist at 390x844, 430x932, 768x1024, and 1440x1000. Additional deterministic captures cover `390-alerts-empty.png`, `390-alerts-populated.png`, and `390-alert-detail.png`.

- Mobile content now reaches a clear end above the fixed navigation. Portfolio labels, disclosures, the final holding groups, and Timeline story content are no longer hidden behind it.
- At 390px the Alerts destinations fit without horizontal scrolling, while the three primary states remain readable and Filtered stays visually secondary.
- Today’s hero and Copilot’s empty state are materially shorter. The first desktop viewport now uses the available width for portfolio/monitoring context instead of decorative emptiness.
- Portfolio communicates “returns by horizon” without implying price history. The selected horizon changes emphasis and the displayed values, but not the underlying API data.
- Functional headings and values now use sans-serif type. Each screen reserves serif for its page-level headline.

## Accessibility and product verification

- Axe rules: WCAG 2 A/AA and WCAG 2.1 A/AA, zero final violations across the tested product states.
- Keyboard: first focus is visible on every route; focus rings use a consistent high-contrast treatment.
- Touch: automated checks found no visible main or navigation action below 44px at 320–430px.
- Responsive: no horizontal overflow at any of the seven widths; no final content overlaps the fixed navigation below the desktop breakpoint.
- PWA: `/manifest.webmanifest` remains linked and `/sw.js` becomes the active production service worker.
- State: Copilot messages survive navigation to Portfolio and back. Empty and populated Alerts are tested with deterministic network fixtures.
- Financial fidelity: portfolio value, day P&L, unrealized P&L, horizon returns, exposure, relevance, and decision labels continue to come directly from existing responses. No frontend return, P&L, exposure, relevance, or decision calculations were added.

## Validation results

- Backend: `146 passed` (`pytest -q`); 33 existing dependency/deprecation warnings.
- Frontend TypeScript: passed.
- ESLint: passed.
- Next.js 16.3.1 production build: passed for all product, fixture, manifest, and offline routes.
- Final polish browser matrix: passed at 320, 360, 390, 430, 768, 1024, and 1440px.
- Existing real-product evaluation: passed at 390x844 and 1440x1000 with no console errors.
- Developer presentation fixture smoke: passed with one shared run and fixture decision/relevance/exposure preserved.

## Deliberate non-changes

- No backend schema, public route, provider, agent, calculation, or financial rule was changed in this polish pass.
- No true historical price series was created. The current performance response remains honestly represented as returns by horizon.
- Voice remains unavailable and is not presented as an input. Existing audio brief and written-transcript behavior remains.
- No settings, advisor workflow, brokerage integration, or new product destination was added.
- The deep green identity, PWA shell, and five-route information architecture remain in place. The former `/dev/presentation` surface was retired when Timeline became the single financial-day runner.

## Focused Copilot conversation addendum

Date: 2026-08-23

The subsequent review reopened only the Copilot/mobile conversation experience. No other destination or visual system was redesigned.

## Financial-day and agentic voice addendum

- Timeline now owns Start, Pause, Resume, and confirmed Restart controls for the full 13-checkpoint schedule. Compatibility clock endpoints remain backend-only aliases.
- Qualifying deterministic events refresh product state and surface one deduplicated in-app alert with a direct path to the retained financial case.
- Copilot now leads with “Talk to your wealth agent,” browser speech transcription, the same persistent text conversation, verified context counts, and a config-gated LiveKit call entry point.
- Voice, call, text, and research requests use the existing Copilot/TaskMaster route. No portfolio calculations, relevance decisions, trading actions, or independent voice reasoning were added to React.
- Without browser speech recognition, microphone permission, LiveKit credentials, or a deployed LiveKit agent, the interface presents a readable fallback and keeps text chat fully usable.
- The LiveKit worker now completes the call pipeline: managed STT, finalized transcript, canonical TaskMaster/Copilot response, managed TTS, and final transcript events returned to the persistent browser conversation. A room is not labeled active until the dispatched agent joins.

### Interaction changes

- Reduced the Copilot hero to a compact `COPILOT / Ask about your portfolio` identity with the existing live context summary immediately below it.
- Replaced the page → giant card → nested bubble hierarchy with a simple context header, chronological message timeline, and composer.
- Kept user turns as compact green bubbles. Assistant turns now sit naturally in the timeline with a small Copilot identity and sans-serif answer typography.
- Added a keyboard-aware composer fixed above mobile navigation. It supports multiline text and Enter-to-send; Shift+Enter creates a new line. The unavailable microphone remains visible but disabled so it is not presented as a working feature.
- Mobile navigation temporarily moves out of the way while the composer has keyboard focus, then returns when focus leaves the input.
- Moved Clear conversation behind a subtle overflow menu and verified clearing resets the persisted conversation lifecycle.
- Before the first message, up to four compact prompts are shown. Once a conversation starts, only two response-provided contextual follow-ups remain near the composer.
- Reduced “Rules determine materiality…” to a small informational note rather than a competing card.

### Long-answer presentation

- The API response and persisted message remain unchanged and complete.
- A local presentation helper removes known internal-sounding lead-ins, presents at most six concise lead sentences, and keeps the remaining supplied text behind progressive disclosures.
- Explicit answer headings are mapped to `Why this matters`, `Verified facts`, `Portfolio impact`, and `Full research`. Unstructured answers receive only evidence-backed sections derived from their existing sentences and bullets; the UI does not invent financial facts.
- Sources remain separately expandable with their original URLs. Long unstructured responses remain accessible through `Full response`.

### Copilot-specific validation

Artifacts are stored under `artifacts/copilot-conversation-pass/` for fresh and long-response states at 360x740, 390x844, and 430x932.

- Fresh page: compact identity, context, prompts, composer, and navigation visible without scrolling.
- One response: chronological user/assistant presentation and two contextual follow-ups.
- Ten messages: readable widths, no horizontal overflow, and composer remains reachable.
- Long research: deterministic 2,689-word response produces a concise lead while research and evidence remain collapsed by default.
- Loading and error: status remains visible without displacing or disabling the prior conversation lifecycle.
- Keyboard focus: composer remains inside the resized viewport and mobile navigation yields to the input.
- Persistence and clear: conversation survives Portfolio → Copilot navigation; Clear conversation returns to a valid fresh state.
- Axe WCAG A/AA checks pass for fresh and long-response states at all three target widths.
