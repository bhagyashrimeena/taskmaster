"use client";

import { ArrowRight, BellRing, Filter, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/primitives/page-header";
import { ErrorState, LoadingState } from "@/components/primitives/states";
import { StatusBadge } from "@/components/primitives/status-badge";
import { useAlerts, usePortfolio, useTimeline } from "@/hooks/use-product-queries";
import { cn } from "@/lib/cn";
import type { AlertCategory } from "@/lib/product-types";
import { useUiStore } from "@/stores/ui-store";

const primaryFilters: Array<{ value: AlertCategory; label: string }> = [
  { value: "attention", label: "Attention" },
  { value: "investigating", label: "Investigating" },
  { value: "monitoring", label: "Monitoring" },
];

export function AlertsView() {
  const filter = useUiStore((state) => state.alertFilter);
  const setFilter = useUiStore((state) => state.setAlertFilter);
  const query = useAlerts(filter);
  const portfolioQuery = usePortfolio();
  const timelineQuery = useTimeline();
  const portfolio = portfolioQuery.data?.portfolio;
  const day = timelineQuery.data;

  return (
    <div>
      <PageHeader eyebrow="Proactive alerts" title="What crossed the threshold" description="A quiet event inbox ranked by portfolio exposure and explicit attention rules."/>
      <div className="mb-4 flex items-center gap-2">
        <div className="grid min-w-0 flex-1 grid-cols-3 rounded-xl bg-[#e8ece7] p-1" role="tablist" aria-label="Alert filters">
          {primaryFilters.map((item) => <button role="tab" aria-selected={filter === item.value} key={item.value} onClick={() => setFilter(item.value)} className={cn("min-h-11 min-w-0 rounded-lg px-1 text-[10px] font-bold leading-tight text-muted transition-colors min-[360px]:text-xs", filter === item.value && "bg-surface text-brand shadow-sm")}><span className="block truncate">{item.label}</span><span className="text-[9px] font-semibold opacity-65">{query.data?.counts[item.value] ?? 0}</span></button>)}
        </div>
        <button type="button" aria-pressed={filter === "ignored"} onClick={() => setFilter("ignored")} className={cn("grid size-11 shrink-0 place-items-center rounded-xl border border-line bg-surface text-muted", filter === "ignored" && "border-brand bg-brand text-white")} aria-label={`Filtered events: ${query.data?.counts.ignored ?? 0}`} title="Filtered events"><Filter size={16}/></button>
      </div>

      {query.isLoading ? <LoadingState label="Checking your event inbox"/> : !query.data ? <ErrorState title="Latest market context temporarily unavailable" detail="Your portfolio remains available. We’ll retry the alert inbox automatically."/> : query.data.items.length === 0 ? (
        <section className="product-card overflow-hidden">
          <div className="p-5 md:p-6"><span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand"><ShieldCheck size={20}/></span><h2 className="section-title mt-4 text-xl">{filter === "attention" ? "Nothing material needs your attention right now" : filter === "ignored" ? "No filtered events" : filter === "investigating" ? "No events are being investigated" : "No events need ongoing monitoring"}</h2><p className="mt-2 max-w-xl text-sm leading-6 text-muted">{filter === "attention" ? "Signals remain under review, while routine movement stays out of your way." : "Cases will appear here only when their rules reach this state."}</p></div>
          {filter === "attention" && <div className="grid grid-cols-3 divide-x divide-line border-t border-line bg-background/70 py-4 text-center"><div><strong className="block text-sm">{portfolio?.holdings_count ?? "—"}</strong><span className="text-[10px] text-muted">holdings</span></div><div><strong className="block text-sm">{portfolio?.sector_exposure.length ?? "—"}</strong><span className="text-[10px] text-muted">sectors</span></div><div><strong className="block text-sm capitalize">{day?.status ?? "Checking"}</strong><span className="text-[10px] text-muted">day monitoring</span></div></div>}
        </section>
      ) : <div className="grid gap-3">{query.data.items.map((item) => <article className={cn("product-card border-l-4 p-5", item.category === "attention" ? "border-l-alert" : item.category === "investigating" ? "border-l-investigate" : "border-l-monitor")} key={item.event_id}>
        <header className="flex items-start justify-between gap-4"><div className="min-w-0"><span className="flex items-center gap-2 text-[10px] font-bold tracking-wider text-muted uppercase">{item.category === "attention" ? <BellRing size={14} className="text-alert"/> : item.category === "investigating" ? <Search size={14} className="text-investigate"/> : <ShieldCheck size={14} className="text-monitor"/>}{item.decision}</span><h2 className="mt-2 truncate text-xl font-bold tracking-[-0.02em]">{item.company ?? item.instrument ?? "Market event"}</h2></div><StatusBadge status={item.status}/></header>
        <p className="mt-2 text-sm leading-6 text-muted">{item.headline}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div className="rounded-xl bg-background px-3 py-2"><span className="block text-[9px] font-bold tracking-wider text-muted uppercase">Movement</span><strong className={(item.price_change_pct ?? 0) < 0 ? "text-negative" : "text-positive"}>{item.price_change_pct === null ? "Unavailable" : `${item.price_change_pct > 0 ? "+" : ""}${item.price_change_pct.toFixed(1)}%`}</strong><span className="ml-1 text-muted">vs sector {item.sector_change_pct?.toFixed(1) ?? "—"}%</span></div><div className="rounded-xl bg-background px-3 py-2"><span className="block text-[9px] font-bold tracking-wider text-muted uppercase">Your exposure</span><strong>{item.direct_exposure_pct.toFixed(1)}% direct</strong></div></div>
        <p className="mt-3 text-sm leading-6 text-ink">{item.reason}</p>
        <footer className="mt-4 flex min-h-11 items-center justify-between gap-3 border-t border-line pt-3"><time className="text-xs text-muted">{new Date(item.occurred_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</time>{item.case_id && <Link className="inline-flex min-h-11 items-center gap-2 rounded-lg text-xs font-extrabold text-brand" href={`/alerts/${item.case_id}`}>Open case <ArrowRight size={14}/></Link>}</footer>
      </article>)}</div>}
      {query.isError && query.data && <span className="mt-3 block text-right text-[10px] text-muted" role="status">Showing saved alert state while freshness checks recover.</span>}
      {query.isFetching && !query.isLoading && <span className="mt-3 block text-right text-[10px] text-muted" role="status">Refreshing alert state…</span>}
    </div>
  );
}
