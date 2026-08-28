"use client";

import { CalendarPlus, Check, Sparkles } from "lucide-react";
import { useState } from "react";

import { createWatchEvent } from "@/lib/api/product";
import type { CalendarWatchEvent, LikelyScenario } from "@/lib/product-types";

const tone: Record<string, string> = {
  bullish: "border-positive/20 bg-positive/8 text-positive",
  neutral: "border-investigate/20 bg-investigate/8 text-investigate",
  risk: "border-alert/20 bg-alert/8 text-alert",
};

export function LikelyScenarios({
  scenarios,
  watchEvents = [],
  compact = false,
}: {
  scenarios: LikelyScenario[];
  watchEvents?: CalendarWatchEvent[];
  compact?: boolean;
}) {
  const [added, setAdded] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const visible = scenarios.filter((scenario) => scenario.status === "active").slice(0, compact ? 3 : 6);
  if (!visible.length) return null;

  const addWatch = async (scenario: LikelyScenario) => {
    setBusy(scenario.scenario_id);
    try {
      const response = await createWatchEvent({
        title: `Review ${scenario.symbol ?? "portfolio"} ${scenario.title.toLowerCase()}`,
        description: `${scenario.what_to_monitor} ${scenario.portfolio_relevance}`,
        symbol: scenario.symbol,
        story_id: scenario.story_id,
        case_id: scenario.case_id,
        scenario_id: scenario.scenario_id,
        trigger_type: "news_followup",
      });
      setAdded((current) => ({ ...current, [scenario.scenario_id]: response.message }));
    } catch {
      setAdded((current) => ({ ...current, [scenario.scenario_id]: "Could not add the watch event. Try again." }));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="product-card p-4 md:p-5" aria-labelledby="likely-scenarios-title">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="section-kicker">Likely scenarios</p>
          <h2 id="likely-scenarios-title" className="section-title mt-1.5">What the agent will monitor next</h2>
        </div>
        <span className="grid size-9 place-items-center rounded-xl bg-brand-soft text-brand">
          <Sparkles size={16} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-2 rounded-2xl border border-monitor/20 bg-monitor/8 px-3 py-2 text-xs leading-5 text-muted">
        Not a prediction — scenarios to monitor from the latest 5-minute news window and portfolio exposure.
      </p>
      <div className="mt-4 grid gap-3">
        {visible.map((scenario) => {
          const alreadyScheduled = watchEvents.some((event) => event.scenario_id === scenario.scenario_id);
          return (
            <article className="rounded-2xl border border-line bg-background/70 p-3" key={scenario.scenario_id}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={`rounded-full border px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider ${tone[scenario.scenario_type] ?? "border-line bg-surface text-muted"}`}>
                  {scenario.scenario_type}
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                  {scenario.likelihood_label} · {scenario.confidence} confidence
                </span>
              </div>
              <h3 className="mt-3 text-sm font-bold text-ink">{scenario.symbol ? `${scenario.symbol}: ` : ""}{scenario.title}</h3>
              <p className="mt-2 text-xs leading-5 text-muted">{scenario.why_it_could_happen}</p>
              <p className="mt-2 text-xs leading-5 text-muted"><strong className="text-ink">Monitor:</strong> {scenario.what_to_monitor}</p>
              <button
                type="button"
                className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-xs font-bold text-brand disabled:opacity-60"
                disabled={busy === scenario.scenario_id || alreadyScheduled}
                onClick={() => void addWatch(scenario)}
                aria-label={`Add internal watch event for ${scenario.title}`}
              >
                {alreadyScheduled || added[scenario.scenario_id] ? <Check size={14} aria-hidden="true" /> : <CalendarPlus size={14} aria-hidden="true" />}
                {alreadyScheduled ? "Watch event scheduled" : busy === scenario.scenario_id ? "Adding..." : "Add internal watch event"}
              </button>
              {added[scenario.scenario_id] && <p className="mt-2 text-[11px] leading-4 text-muted" role="status">{added[scenario.scenario_id]}</p>}
            </article>
          );
        })}
      </div>
      <p className="mt-3 text-[11px] leading-4 text-muted">Scenarios are not predictions or investment advice.</p>
    </section>
  );
}
