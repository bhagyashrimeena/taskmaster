import { ArrowUpRight, BellRing, Newspaper } from "lucide-react";
import Link from "next/link";

import type { AttentionItem } from "@/lib/product-types";
import { StatusBadge } from "@/components/primitives/status-badge";

export function AttentionCard({ item }: { item: AttentionItem }) {
  const event = item.kind === "event";
  return (
    <article className={`product-card p-5 ${event ? "border-alert/30" : ""}`}>
      <header className="flex items-start justify-between gap-4">
        <span className="flex items-center gap-2 text-[10px] font-extrabold tracking-[0.12em] text-brand uppercase">
          {event ? <BellRing size={15}/> : <Newspaper size={15}/>}
          {event ? "High priority" : "Worth reading"}
        </span>
        <StatusBadge status={item.status}/>
      </header>
      <h2 className={`mt-4 font-bold leading-tight tracking-[-0.025em] ${event ? "text-2xl md:text-3xl" : "text-xl md:text-2xl"}`}>{item.title}</h2>
      {event && (
        <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold">
          <span className="rounded-xl bg-alert/10 px-3 py-2 text-alert">{item.direct_exposure_pct.toFixed(1)}% direct exposure</span>
          <span className="rounded-xl bg-background px-3 py-2 text-muted">Relevance {item.relevance_score.toFixed(0)}</span>
        </div>
      )}
      <p className="mt-3 text-sm leading-6 text-muted">{item.summary}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-xs font-bold text-white" href={event ? "/alerts" : "/copilot"}>
          {event ? "Open case" : "Explain"}<ArrowUpRight size={14}/>
        </Link>
        <Link className="rounded-xl border border-line px-4 py-2.5 text-xs font-bold" href="/copilot">Ask Copilot</Link>
      </div>
    </article>
  );
}
