# Wealth Copilot System Architecture

This document describes the implementation currently present in the repository. The diagrams use product-facing names where those names are clearer, with the source implementation name shown in parentheses when useful.

## 1. Overall System Architecture

```mermaid
flowchart LR
    subgraph client ["Client"]
        web["Next.js Wealth Copilot"]
    end

    subgraph gateway ["API Gateway"]
        api["FastAPI REST and media API"]
    end

    subgraph service ["Core Runtime"]
        day["Checkpoint Scheduler and Day Orchestrator"]
        taskmaster["ADK TaskMaster"]
        agents["Portfolio, Market, Research, and Media Agents"]
        decisions["Relevance and Event Decision Engines"]
        interaction["Interaction and Advisor Handoff"]
    end

    subgraph datastore ["State and Artifacts"]
        financialDay["Financial Day and Event State"]
        conversations["Conversations and Research Jobs"]
        mediaStore["Stories and Gemini Audio"]
    end

    subgraph external ["External Providers"]
        portfolioSource["Portfolio Provider: simulated active, Zerodha optional"]
        vertex["Vertex AI Gemini via ADC"]
        search["Google Search Grounding"]
        advisor["Human Advisor"]
    end

    subgraph async ["Asynchronous Triggers"]
        checkpoints["Checkpoint Schedule"]
    end

    web -->|"HTTPS and audio"| api
    api -->|"Runs checkpoints"| day
    api -->|"Routes requests"| taskmaster
    api -->|"Handles actions"| interaction
    checkpoints -.->|"Triggers"| day
    day -->|"Coordinates"| taskmaster
    day -->|"Applies rules"| decisions
    day -->|"Writes continuity"| financialDay
    taskmaster -->|"Delegates"| agents
    agents -->|"Supplies signals"| decisions
    agents -->|"Stores media"| mediaStore
    decisions -->|"Records outcomes"| financialDay
    interaction -->|"Stores context"| conversations
    agents -.->|"Portfolio data"| portfolioSource
    agents -.->|"Gemini reasoning"| vertex
    agents -.->|"Grounded research"| search
    interaction -.->|"Sends handoff"| advisor
```

This is a logical runtime architecture rather than a claim that every box is independently deployed. The Next.js experience exposes the dashboard, chat, generated audio, and Daily Wealth Story through the FastAPI boundary. TaskMaster routes intent and delegates specialist work, while deterministic code owns relevance scoring and event decisions. The active demo portfolio is simulated, Zerodha remains an optional provider adapter, and Gemini reasoning and TTS use Vertex AI through Application Default Credentials. Google Search is the grounded market/news path, not a portfolio provider.

## 2. Attention Decision Pipeline

```mermaid
flowchart LR
    observe(["Observe event"])
    normalize["Normalize and deduplicate"]
    match["Match portfolio"]
    exposure["Direct and sector exposure"]
    materiality["Assess materiality"]
    investigate["Grounded search investigation"]
    verify["Verify trusted sources"]
    score["Deterministic relevance score"]
    decision{"Decision engine"}
    ignore["IGNORE: no interruption"]
    monitor["MONITOR: watch queue"]
    investigateOutcome["INVESTIGATE: research brief"]
    alert["ALERT: contextual alert"]
    financialDay[("Financial Day State")]
    explain["Explain why it matters"]
    userAction{"User action"}
    review["Review"]
    deeper["Research deeper"]
    advisor["Advisor handoff"]
    dismiss["Dismiss"]

    observe --> normalize --> match --> exposure --> materiality
    materiality --> investigate --> verify --> score --> decision
    decision --> ignore & monitor & investigateOutcome & alert
    ignore & monitor & investigateOutcome & alert --> financialDay
    monitor -.->|"When reviewed"| explain
    investigateOutcome --> explain
    alert --> explain
    explain --> userAction
    userAction --> review & deeper & advisor & dismiss

    classDef agent fill:#C2E5FF,stroke:#3DADFF;
    classDef deterministic fill:#FFE0C2,stroke:#FF9E42;
    classDef human fill:#CDF4D3,stroke:#66D575;

    class investigate,verify,explain agent;
    class normalize,match,exposure,materiality,score,decision deterministic;
    class userAction,review,deeper,advisor,dismiss human;
```

Blue steps are agent-assisted investigation and explanation. Orange steps are deterministic matching, exposure calculation, materiality assessment, scoring, and triage. Every outcome is persisted with provenance; only material `MONITOR`, `INVESTIGATE`, or `ALERT` items reach the explanation and user-action path. `IGNORE`, `MONITOR`, `INVESTIGATE`, and `ALERT` express attention priority, never a trade instruction.

## 3. Autonomous Financial Day

```mermaid
flowchart TB
    state[(FinancialDayState<br/>continuity layer / source of truth)]

    subgraph time[Time-triggered work]
        pulse[07:00<br/>Morning Pulse]
        health[08:00<br/>Portfolio Health]
        close[15:30<br/>Market Close Review]
        wrap[20:00<br/>Evening Wealth Wrap]
        tomorrow[21:00<br/>Tomorrow Prep]
        wealthstory[21:01<br/>Daily Wealth Story]
    end

    subgraph event[Event-triggered work]
        watcher[Market Hours<br/>Event Watcher]
        hdfc[12:17 HDFC move<br/>-5.4% vs sector -0.8%]
        alert[Decision path<br/>exposure -> investigation -> relevance -> ALERT]
    end

    orchestrator[DayOrchestrator<br/>known checkpoint operations]
    scheduler[DayScheduler<br/>real-time schedule when enabled]
    clock[Financial-day clock<br/>Timeline start / pause / restart]

    scheduler --> pulse & health & close & wrap & tomorrow & wealthstory
    clock --> orchestrator
    pulse --> orchestrator
    health --> orchestrator
    close --> orchestrator
    wrap --> orchestrator
    tomorrow --> orchestrator
    wealthstory --> orchestrator
    hdfc --> watcher --> alert --> orchestrator
    orchestrator --> state
    state -. shared continuity .-> pulse & health & watcher & close & wrap & tomorrow & wealthstory

    classDef timeTriggered fill:#eef3f0,color:#17211d,stroke:#7c9788;
    classDef eventTriggered fill:#fff2df,color:#4d3218,stroke:#ad641f;
    classDef stateStyle fill:#244f77,color:#fff,stroke:#173957,stroke-width:2px;
    classDef control fill:#f5f6f3,color:#17211d,stroke:#aab5ad;

    class pulse,health,close,wrap,tomorrow,wealthstory timeTriggered;
    class watcher,hdfc,alert eventTriggered;
    class state,orchestrator stateStyle;
    class scheduler,clock control;
```

`FinancialDayState` carries the shared `day_id`, `run_id`, timeline, event assessments, portfolio snapshots, audio identifiers, market-close review, advisor interactions, tomorrow items, and Daily Wealth Story identity. The HDFC event is not a scheduled checkpoint: it enters the Event Watcher when its market trigger occurs during market hours.

### Live voice call path

```mermaid
flowchart LR
    browser[Copilot call UI] --> token[POST /api/v1/copilot/voice/session]
    token --> room[Short-lived LiveKit room]
    room --> stt[LiveKit Inference STT]
    stt --> worker[TaskMasterVoiceAgent]
    worker --> copilot[Canonical InteractionService]
    copilot --> taskmaster[Google ADK TaskMaster]
    taskmaster --> copilot --> worker
    worker --> tts[LiveKit Inference TTS]
    tts --> room --> browser
    room -. final transcripts .-> browser
```

The worker supplies no independent financial reasoning model. Its LiveKit LLM slot is a non-callable sentinel, and `llm_node` delegates to `InteractionService` with `mode=call`; any bypass fails explicitly. The room is dispatched by the short-lived token to the configured `wealth-copilot` worker.

## 4. HDFC Hero Event Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Market as Market event fixture / market signal
    participant EW as Event Watcher<br/>EventDecisionEngine
    participant PA as Portfolio Agent<br/>get_portfolio_summary
    participant RE as RelevanceEngine<br/>deterministic
    participant Inv as Event Investigator
    participant Day as DayOrchestrator<br/>FinancialDayState
    participant TM as TaskMaster<br/>root_agent
    participant User
    participant Advisor as Advisor Handoff

    Market->>EW: HDFCBANK move detected<br/>-5.4% vs sector -0.8%
    EW->>PA: Check active portfolio exposure
    PA-->>EW: Direct exposure 17.21%<br/>sector exposure 27.26%
    EW->>EW: Apply deterministic trigger rules
    EW->>Inv: Investigate triggered event
    Inv-->>EW: Retained development context
    EW->>RE: Calculate relevance from event + portfolio
    RE-->>EW: 93.11 / 100
    EW->>EW: Decision = ALERT
    EW->>Day: Record assessment, trace, and notification_required
    Day-->>TM: Retained event context available
    TM-->>User: Surface proactive HDFC alert
    User->>TM: Explain: why does this matter to me?
    TM-->>User: Facts, exposure, interpretation, and uncertainty
    User->>TM: Research deeper
    TM->>Inv: Delegate explicit source-first research
    Inv-->>User: Concise research with sources and unknowns
    opt User requests human perspective
        User->>Advisor: Prepare and review advisor packet
        Advisor-->>User: Optional attributed advisor response
    end
    Day->>Day: Carry event into Market Close Review
    Day->>Day: Carry retained context into Evening Wealth Wrap

    Note over EW,User: Attention priority, not an investment instruction.
```

The demonstrated values are the current deterministic HDFC scenario values: HDFCBANK `-5.4%`, sector `-0.8%`, direct exposure `17.21%`, sector exposure `27.26%`, and relevance `93.11 / 100`. TaskMaster surfaces and explains the retained decision; it does not calculate the deterministic score itself.

## How to explain this in 30 seconds

“Wealth Copilot has one conversational TaskMaster supervising several focused specialists. It reads a simulated portfolio and live Google Search market context, then deterministic code matches stories to holdings, measures exposure, and decides what deserves attention. During the financial day, the same FinancialDayState carries context from Morning Pulse through an event-triggered HDFC alert, market close, Evening Wrap, and the Daily Wealth Story. I can ask for an explanation, launch deeper source-first research, or bring a human advisor into the loop. The system prioritizes information; I still decide what to do.”

## Judge-facing technical highlights

- Google ADK `root_agent` is the TaskMaster supervisor and intent router; specialist agents remain explicit delegates.
- `daily_brief_workflow` parallelizes portfolio and market collection, then applies deterministic relevance and diversity ranking.
- `RelevanceEngine` is explainable deterministic scoring over direct holding, exposure, sector, materiality, freshness, and movement signals.
- `EventDecisionEngine` owns trigger rules, investigation status, relevance evaluation, and `IGNORE` / `MONITOR` / `INVESTIGATE` / `ALERT` decisions without an LLM.
- `FinancialDayState` plus `FinancialDayStore` provide durable continuity across orchestrated checkpoints, event history, audio, advisor, and story outputs.
- The active demo uses `SimulatedPortfolioProvider`; Google Search grounding is the live news path, while Zerodha is an optional provider implementation and is not active in this architecture.
