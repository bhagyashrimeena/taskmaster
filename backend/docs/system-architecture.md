# Wealth Copilot System Architecture

This document describes the implementation currently present in the repository. The diagrams use product-facing names where those names are clearer, with the source implementation name shown in parentheses when useful.

## 1. Overall System Architecture

```mermaid
flowchart LR
    user([User])

    subgraph interfaces[User interfaces]
        dashboard[Dashboard]
        chat[Chat / Explain]
        audio[Audio Brief]
        story[Daily Wealth Story]
    end

    taskmaster[Google ADK TaskMaster<br/>root_agent / taskmaster]

    subgraph specialists[Specialists]
        portfolio[Portfolio Agent<br/>portfolio_agent]
        daily[Market Intelligence +<br/>daily brief workflow<br/>market_intelligence_agent + daily_brief_workflow]
        research[Research Agent<br/>research_agent]
        media[Media Agent<br/>media_agent]
    end

    subgraph inputs[Data and tools]
        simulated[(Simulated Portfolio Provider<br/>SimulatedPortfolioProvider)]
        search[(Google Search grounded<br/>live market/news data)]
    end

    subgraph decisions[Decision layer]
        relevance[Deterministic Relevance Engine<br/>RelevanceEngine]
        watcher[Event Watcher<br/>EventDecisionEngine]
    end

    subgraph continuity[State and orchestration]
        daystate[(FinancialDayState<br/>FinancialDayStore)]
        orchestrator[Day Orchestrator<br/>DayOrchestrator]
    end

    advisor[Advisor Handoff<br/>reviewed human layer]

    user --> dashboard & chat & audio & story
    dashboard & chat & audio & story --> taskmaster
    taskmaster --> portfolio & daily & research & media
    portfolio --> simulated
    daily --> search
    daily --> relevance
    taskmaster --> watcher
    watcher --> portfolio
    watcher --> relevance
    taskmaster --> daystate
    orchestrator --> daystate
    orchestrator --> portfolio & watcher & media & story
    chat --> advisor
    dashboard --> advisor
    daystate --> dashboard & audio & story & advisor

    classDef user fill:#185744,color:#fff,stroke:#103f32,stroke-width:2px;
    classDef supervisor fill:#244f77,color:#fff,stroke:#173957,stroke-width:2px;
    classDef state fill:#fff2df,color:#4d3218,stroke:#ad641f,stroke-width:2px;
    classDef deterministic fill:#e8f7f0,color:#14533d,stroke:#6aac8e;
    classDef data fill:#f5f6f3,color:#17211d,stroke:#aab5ad;

    class user user;
    class taskmaster supervisor;
    class daystate,orchestrator state;
    class relevance,watcher deterministic;
    class simulated,search data;
```

The four interfaces share the same TaskMaster and retained underlying context. TaskMaster routes intent and delegates work; it does not replace the deterministic scoring or event-decision code. The active demo portfolio is simulated. Google Search is the live market/news path when configured; it is not a portfolio provider.

## 2. Attention Decision Pipeline

```mermaid
flowchart LR
    observe[Observe market and news]
    filter[Filter noise<br/>normalize and deduplicate]
    match[Match against portfolio<br/>holdings and sectors]
    exposure[Calculate direct and<br/>sector exposure]
    materiality[Assess materiality<br/>event type and movement]
    investigate[Investigate<br/>when a trigger fires]
    score[Calculate relevance score<br/>RelevanceEngine - deterministic]
    decision{Decision}
    ignore[IGNORE]
    monitor[MONITOR]
    investigateOutcome[INVESTIGATE]
    alert[ALERT]
    explain[Explain context<br/>facts, interpretation, unknowns]
    userdecides[User decides what to do]

    observe --> filter --> match --> exposure --> materiality --> investigate --> score --> decision
    decision --> ignore & monitor & investigateOutcome & alert
    ignore & monitor & investigateOutcome & alert --> explain --> userdecides

    note[Attention decisions indicate information priority,<br/>not investment instructions.]
    explain -.-> note

    classDef process fill:#f5f6f3,color:#17211d,stroke:#aab5ad;
    classDef deterministic fill:#e8f7f0,color:#14533d,stroke:#6aac8e;
    classDef outcome fill:#fff2df,color:#4d3218,stroke:#ad641f;
    classDef boundary fill:#eef3f0,color:#30473c,stroke:#9aaea1,stroke-dasharray: 5 5;

    class observe,filter,match,exposure,materiality,investigate,explain,userdecides process;
    class score deterministic;
    class decision,ignore,monitor,investigateOutcome,alert outcome;
    class note boundary;
```

The daily brief uses `RelevanceEngine` to normalize, portfolio-match, score, and rank candidate news. The Event Watcher uses the same relevance engine after its deterministic trigger rules and investigation path. `IGNORE`, `MONITOR`, `INVESTIGATE`, and `ALERT` express attention priority; none is a trade instruction.

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
    clock[Presentation clock<br/>accelerated demo controls]

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
    PA-->>EW: Direct exposure 18.01%<br/>sector exposure ~28%
    EW->>EW: Apply deterministic trigger rules
    EW->>Inv: Investigate triggered event
    Inv-->>EW: Retained development context
    EW->>RE: Calculate relevance from event + portfolio
    RE-->>EW: 94.21 / 100
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

The demonstrated values are the current deterministic HDFC scenario values: HDFCBANK `-5.4%`, sector `-0.8%`, direct exposure `18.01%`, sector exposure approximately `28%`, and relevance `94.21 / 100`. TaskMaster surfaces and explains the retained decision; it does not calculate the deterministic score itself.

## How to explain this in 30 seconds

“Wealth Copilot has one conversational TaskMaster supervising several focused specialists. It reads a simulated portfolio and live Google Search market context, then deterministic code matches stories to holdings, measures exposure, and decides what deserves attention. During the financial day, the same FinancialDayState carries context from Morning Pulse through an event-triggered HDFC alert, market close, Evening Wrap, and the Daily Wealth Story. I can ask for an explanation, launch deeper source-first research, or bring a human advisor into the loop. The system prioritizes information; I still decide what to do.”

## Judge-facing technical highlights

- Google ADK `root_agent` is the TaskMaster supervisor and intent router; specialist agents remain explicit delegates.
- `daily_brief_workflow` parallelizes portfolio and market collection, then applies deterministic relevance and diversity ranking.
- `RelevanceEngine` is explainable deterministic scoring over direct holding, exposure, sector, materiality, freshness, and movement signals.
- `EventDecisionEngine` owns trigger rules, investigation status, relevance evaluation, and `IGNORE` / `MONITOR` / `INVESTIGATE` / `ALERT` decisions without an LLM.
- `FinancialDayState` plus `FinancialDayStore` provide durable continuity across orchestrated checkpoints, event history, audio, advisor, and story outputs.
- The active demo uses `SimulatedPortfolioProvider`; Google Search grounding is the live news path, while Zerodha is an optional provider implementation and is not active in this architecture.