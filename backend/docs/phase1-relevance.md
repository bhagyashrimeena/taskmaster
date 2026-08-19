# Phase 1 personalized-news contract

## Boundary

Phase 1 answers **“What matters to me today?”** It does not watch continuously,
send alerts, recommend trades, execute orders, or implement a UI. The
`notification_required` field is calculated but inert; Phase 2 may consume it
later.

## Execution flow

```text
TaskMaster
  └─ DailyBriefWorkflow (SequentialAgent)
       ├─ ParallelAgent
       │    ├─ Portfolio snapshot agent → normalized provider data
       │    └─ Cached market fetch → Market Agent only on cache miss
       ├─ deterministic rank agent
       │    └─ normalize → match → relevance → utility/diversity → top 5
       └─ Gemini explanation agent → final response
```

The Market Intelligence Agent is deliberately isolated. In live mode it has
Google Search as its only tool; in demo mode it has only the fixture tool. The
standard daily path does not invoke a conversational Relevance Agent. A custom
ADK agent calls the deterministic engine directly, and Gemini is used once at
the end to explain the already-selected result. TaskMaster calls the workflow
through one `AgentTool` with `skip_summarization=True`, avoiding another final
TaskMaster model turn.

Portfolio and market collection start concurrently. The portfolio branch uses
the same provider contract as the conversational Portfolio Agent but needs no
LLM reasoning for a structured snapshot.

ADK 2.5 currently emits a deprecation notice for the `ParallelAgent` and
`SequentialAgent` templates in favor of its newer graph `Workflow`. The graph
API cannot yet be used as an `LlmAgent` sub-agent, so the requested templates
are isolated in `daily_brief_workflow.py` for a later mechanical migration.

## Candidate contract

Every accepted candidate contains:

- `id`, `headline`, and `summary`;
- `source_name` and an HTTP(S), article-specific `source_url`;
- timezone-aware `published_at`;
- `companies[]`, `sectors[]`, `event_type`, and optional `market_move_pct`.

Normalization strips common tracking parameters, rejects malformed or homepage
sources, and removes duplicate URLs and near-duplicate headlines. One rejected
row does not fail the remaining batch.

## Deterministic score

The relevance engine is ordinary Python and makes no model calls. Its components
sum to a maximum of 100:

| Signal | Maximum | Rule |
| --- | ---: | --- |
| Direct holding | 35 | Full points when a named company matches a holding |
| Exposure magnitude | 20 | Direct portfolio weight, capped at 20 |
| Sector exposure | 12 | Sector weight scaled against 30%, capped at 12 |
| Event materiality | 15 | Fixed lookup by event type |
| Freshness | 10 | 10/8/5/2/0 for ≤6/24/48/72/>72 hours |
| Market movement | 8 | Twice the largest absolute related move, capped at 8 |

Company and sector aliases are normalized before matching. Direct exposure is
the sum of weights of explicitly affected holdings. Sector exposure is the sum
of all holdings in the candidate’s matched sectors.

The engine sets `notification_required=true` only when the score is at least 85
and materiality is high or critical. Nothing sends that notification.

The explanation agent may explain the relationship in plain language, but it
must preserve the engine’s scores, exposures, source fields, and ordering.
The feed also carries `news_is_live`, separately from `portfolio_source`, so a
simulated portfolio with live Google Search news cannot be mislabeled as scenario news.

## Final utility and diversity

Portfolio relevance is not the final presentation order. Selection is greedy
and deterministic, using a second 0–100 utility score:

| Component | Range |
| --- | ---: |
| 75% of relevance score | 0–75 |
| Event materiality | 0–8 |
| Freshness | 0–5 |
| Source authority | 0/2/5/8 |
| Novelty | 0/2/4 |
| Event/headline similarity penalty | 0 to −12 |
| Company saturation penalty | −10 per prior selected company story |

Source tiers are: exchange/regulator/company primary material, established
financial reporting, secondary analysis/aggregators, and other. Selection
normally allows at most two stories about one company. A third must be both
critical and dissimilar to the selected stories.

## Candidate cache and latency

The latest candidate batch is cached in-process for 15 minutes by default.
Repeated briefs still refresh the portfolio and rerun all deterministic code,
but skip Google Search. Asking TaskMaster to refresh news calls `refresh_news()`
before the workflow. This is deliberately not a scheduler or Phase 2 watcher.

Measured locally on 2026-08-17:

- previous fully agentic live path: about 204 seconds;
- hybrid cold path with live Search: 112.27 seconds;
- hybrid warm path with cached candidates: 14.94 seconds.

## Provider independence

`PORTFOLIO_PROVIDER=simulated` produces the provider-neutral portfolio schema.
News normalization and relevance code depend only on that contract, so a future
authorized portfolio-data provider can be added without changing the workflow.
