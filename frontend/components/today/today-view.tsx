"use client";

import { ArrowRight, Check, Clock3, Layers3, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AttentionPipeline } from "@/components/attention-pipeline";
import { AudioBriefControl } from "@/components/audio-brief";
import { LikelyScenarios } from "@/components/likely-scenarios";
import { FinancialValue, PercentChange } from "@/components/primitives/financial-value";
import { ErrorState, LoadingState } from "@/components/primitives/states";
import { AttentionCard } from "@/components/today/attention-card";
import { useToday } from "@/hooks/use-product-queries";

export function TodayView() {
  const query = useToday();
  if (query.isLoading) return <LoadingState/>;
  if (!query.data) return <ErrorState title="Today is temporarily unavailable" detail="Your portfolio remains safe. Wealth Copilot will retry automatically."/>;

  const data = query.data;
  const date = new Date(`${data.trading_date}T12:00:00`).toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "short",
  });
  const eventItems = data.attention_items.filter((item) => item.kind === "event");
  const storyItems = data.attention_items.filter((item) => item.kind === "story");

  return (
    <div>
      <header className="mb-4 rounded-[1.6rem] bg-[#12201b] p-6 text-white md:p-7">
        <span className="text-[11px] font-extrabold tracking-[0.14em] text-[#63dbc1] uppercase">{data.greeting}</span>
        <p className="mt-2 text-xs text-white/55">{date} · {data.portfolio.source.label}</p>
        <h1 className="mt-4 max-w-2xl font-display text-[2.7rem] leading-[0.94] tracking-[-0.045em] md:text-[3.75rem]">{data.attention_message}</h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-white/65">
          {eventItems.length ? "A market event crossed your personal alert rules." : storyItems.length ? "Portfolio-relevant reading, without an interruption." : "Nothing material crossed your attention threshold."}
        </p>
        <AudioBriefControl type="morning"/>
      </header>

      {query.isError && <p role="status" className="mb-4 rounded-xl border border-investigate/20 bg-investigate/5 px-4 py-3 text-xs text-muted">Showing the latest saved snapshot while freshness checks recover.</p>}

      <section className="product-card mb-4 grid grid-cols-2 overflow-hidden md:grid-cols-[1.35fr_1fr_1fr]">
        <div className="col-span-2 p-5 md:col-span-1"><span className="metric-label">Portfolio today</span><FinancialValue value={data.portfolio.portfolio_value} className="mt-1 block text-[2rem] font-semibold tracking-tight"/></div>
        <div className="border-t border-line p-4 md:border-t-0 md:border-l"><span className="metric-label">Today</span><div className="mt-1.5 text-sm"><FinancialValue value={data.portfolio.day_pnl ?? 0} change className="mr-2"/><PercentChange value={data.portfolio.day_change_pct}/></div></div>
        <div className="border-t border-l border-line p-4 md:border-t-0"><span className="metric-label">Overall</span><div className="mt-1.5 text-sm"><FinancialValue value={data.portfolio.unrealized_pnl} change className="mr-2"/><PercentChange value={data.portfolio.overall_return_pct}/></div></div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_0.72fr]">
        <div className="grid content-start gap-4">
          {eventItems.length > 0 ? eventItems.map((item) => <AttentionCard key={item.item_id} item={item}/>) : (
            <article className="rounded-[var(--radius-card)] border border-brand/20 bg-brand/5 p-5">
              <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand"><ShieldCheck size={20}/></span><div><span className="section-kicker">Quiet monitoring</span><h2 className="section-title mt-1">No market alert needs you right now</h2></div></div>
              <p className="mt-3 text-sm leading-6 text-muted">Routine movement stayed below your interruption threshold.</p>
              <div className="mt-4 grid grid-cols-3 divide-x divide-brand/15 rounded-xl bg-surface/70 py-3 text-center"><div><strong className="block text-sm">{data.portfolio.holdings_count}</strong><span className="text-[10px] text-muted">holdings</span></div><div><strong className="block text-sm">{storyItems.length}</strong><span className="text-[10px] text-muted">relevant reads</span></div><div><strong className="block text-sm">{data.next_checkpoint?.scheduled_time ?? "Done"}</strong><span className="text-[10px] text-muted">next check</span></div></div>
            </article>
          )}
          {storyItems.slice(0, 2).map((item) => <AttentionCard key={item.item_id} item={item}/>)}
          <AttentionPipeline
            compact
            score={eventItems[0]?.relevance_score ?? storyItems[0]?.relevance_score}
            decision={eventItems[0]?.status ?? (storyItems.length ? "MONITOR" : "IGNORE")}
          />
          <LikelyScenarios scenarios={data.likely_scenarios} watchEvents={data.calendar_watch_events} compact />
        </div>

        <aside className="product-card content-start p-5">
          <section className="mb-5">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand"><Layers3 size={18}/></span>
              <div>
                <span className="section-kicker">Rich portfolio context</span>
                <h2 className="section-title mt-1 text-lg">What the agent knows</h2>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-xl bg-background/80 px-3 py-2">
                <span className="block text-[9px] font-bold uppercase tracking-wider text-muted">Holdings</span>
                <strong>{data.portfolio.holdings_count}</strong>
              </div>
              <div className="rounded-xl bg-background/80 px-3 py-2">
                <span className="block text-[9px] font-bold uppercase tracking-wider text-muted">Sectors</span>
                <strong>{data.portfolio.sector_exposure.length}</strong>
              </div>
              <div className="rounded-xl bg-background/80 px-3 py-2">
                <span className="block text-[9px] font-bold uppercase tracking-wider text-muted">Assets</span>
                <strong>{data.portfolio.asset_allocation.length || "—"}</strong>
              </div>
              <div className="rounded-xl bg-background/80 px-3 py-2">
                <span className="block text-[9px] font-bold uppercase tracking-wider text-muted">Risk profile</span>
                <strong>{data.portfolio.risk_profile ?? "Demo"}</strong>
              </div>
            </div>
          </section>
          <section>
            <div className="flex items-center justify-between"><span className="section-kicker">Since this morning</span><Link href="/timeline" className="inline-flex min-h-11 items-center rounded-lg px-1 text-xs font-bold text-brand">Full timeline</Link></div>
            <div className="mt-4 grid">
              {data.recent_timeline.length ? data.recent_timeline.map((step, index) => <div key={step.step_id} className="relative grid grid-cols-[24px_1fr] gap-3 pb-4 last:pb-0"><span className="z-10 grid size-6 place-items-center rounded-full bg-brand-soft text-brand"><Check size={12}/></span>{index < data.recent_timeline.length - 1 && <i className="absolute top-6 bottom-0 left-[11px] w-px bg-line"/>}<div><strong className="text-sm">{step.label}</strong><p className="mt-0.5 text-xs leading-5 text-muted">{step.detail}</p></div></div>) : <p className="text-sm leading-6 text-muted">The financial day is ready for its first scheduled checkpoint.</p>}
            </div>
          </section>
          <section className="mt-5 border-t border-line pt-4">
            <span className="section-kicker">Next</span>
            {data.next_checkpoint ? <div className="mt-3 flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-background text-brand"><Clock3 size={17}/></span><div><strong className="block text-sm">{data.next_checkpoint.scheduled_time} · {data.next_checkpoint.label}</strong><span className="text-xs text-muted">Updates automatically.</span></div></div> : <div className="mt-3"><strong className="block text-sm">Financial day complete</strong><Link href="/timeline" className="mt-2 inline-flex items-center gap-1 rounded-lg text-xs font-bold text-brand">Replay the day <ArrowRight size={13}/></Link></div>}
          </section>
        </aside>
      </section>
    </div>
  );
}
