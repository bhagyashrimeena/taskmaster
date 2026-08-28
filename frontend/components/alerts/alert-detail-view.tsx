"use client";

import { ArrowLeft, Bot, ExternalLink, FileText, Send, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AdvisorSheet, type AdvisorTarget } from "@/components/advisor-sheet";
import { AttentionPipeline } from "@/components/attention-pipeline";
import { LikelyScenarios } from "@/components/likely-scenarios";
import { PageHeader } from "@/components/primitives/page-header";
import { ErrorState, LoadingState } from "@/components/primitives/states";
import { StatusBadge } from "@/components/primitives/status-badge";
import { useAlert } from "@/hooks/use-product-queries";

const TRACE_LABELS: Record<string, string> = {
  EVENT_DETECTED: "Market movement detected",
  PORTFOLIO_CHECK: "Your exposure checked",
  MARKET_INVESTIGATION: "Market context reviewed",
  RELEVANCE: "Portfolio relevance assessed",
  DECISION: "Attention level decided",
  MONITORING: "Ongoing monitoring confirmed",
};

function traceLabel(stage: string) {
  return TRACE_LABELS[stage] ?? "Rule check completed";
}

function signedPercent(value: number | string | null | undefined, digits = 1) {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(digits)}%`;
}

export function AlertDetailView() {
  const params = useParams<{ caseId: string }>();
  const [advisorTarget, setAdvisorTarget] = useState<AdvisorTarget | null>(null);
  const query = useAlert(params.caseId);
  if (query.isLoading) return <LoadingState label="Loading the retained case" />;
  if (!query.data) {
    return <ErrorState title="This case is unavailable" detail="It may have been closed or belongs to another financial day." />;
  }

  const { item, intraday, benchmark, sector, assessment } = query.data;
  const chart = intraday.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
    price: Number(point.price),
  }));
  const firstPrice = chart[0]?.price;
  const lastPrice = chart.at(-1)?.price;
  const chartSummary = chart.length
    ? `${item.company ?? item.instrument ?? "The instrument"} moved from ${firstPrice} to ${lastPrice} across ${chart.length} intraday observations.`
    : "No intraday price observations are available for this case.";

  return (
    <div>
      <Link href="/alerts" className="mb-4 inline-flex min-h-11 items-center gap-2 rounded-lg px-2 text-xs font-bold text-brand">
        <ArrowLeft size={14} aria-hidden="true" />
        Back to alerts
      </Link>
      <PageHeader
        eyebrow="Financial case"
        title={item.company ?? item.instrument ?? "Market event"}
        description={item.headline}
        meta={<StatusBadge status={item.status} />}
      />
      {query.isError && (
        <p role="status" className="mb-4 rounded-xl border border-investigate/20 bg-investigate/5 px-4 py-3 text-xs text-muted">
          Showing the most recent saved case while freshness checks recover.
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <section className="product-card p-5 md:p-6" aria-labelledby="movement-heading">
          <p className="section-kicker">Event movement</p>
          <h2 id="movement-heading" className="sr-only">Financial movement and portfolio exposure</h2>
          <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-2">
            <strong className={`text-5xl font-semibold tracking-tight tabular-nums ${(item.price_change_pct ?? 0) < 0 ? "text-negative" : "text-positive"}`}>
              {signedPercent(item.price_change_pct)}
            </strong>
            <p className="pb-1 text-xs leading-5 text-muted">
              {sector?.sector ?? "Sector"} {signedPercent(sector?.change_pct)}
              <br />
              {benchmark?.index_name ?? "Nifty 50"} {signedPercent(benchmark?.change_pct)}
            </p>
          </div>

          <figure className="mt-5" aria-labelledby="intraday-caption">
            <figcaption id="intraday-caption" className="mb-2 text-xs font-semibold text-ink">Intraday price movement</figcaption>
            <p className="sr-only">{chartSummary}</p>
            {chart.length > 0 ? (
              <div className="h-52" role="img" aria-label={chartSummary}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chart} margin={{ top: 8, right: 10, left: -15, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#edf0ec" />
                    <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
                    <YAxis domain={["auto", "auto"]} axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
                    <Tooltip contentStyle={{ borderRadius: 12, fontSize: 11 }} />
                    <Line type="monotone" dataKey="price" stroke="#185744" strokeWidth={3} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="rounded-xl bg-background px-4 py-5 text-sm text-muted">Intraday observations are not available yet.</p>
            )}
          </figure>

          <div className="mt-5 grid grid-cols-3 divide-x divide-line border-t border-line pt-4">
            <div className="pr-3">
              <span className="metric-label">Direct holding</span>
              <strong className="mt-1 block text-lg tabular-nums">{item.direct_exposure_pct.toFixed(1)}%</strong>
            </div>
            <div className="px-3">
              <span className="metric-label">Sector total</span>
              <strong className="mt-1 block text-lg tabular-nums">{item.sector_exposure_pct.toFixed(1)}%</strong>
            </div>
            <div className="pl-3">
              <span className="metric-label">Portfolio impact</span>
              <strong className={`mt-1 block text-lg tabular-nums ${(item.portfolio_impact_pct ?? 0) < 0 ? "text-negative" : "text-positive"}`}>
                {item.portfolio_impact_pct === null ? "—" : `${item.portfolio_impact_pct > 0 ? "+" : ""}${item.portfolio_impact_pct.toFixed(2)} pp`}
              </strong>
            </div>
          </div>
        </section>

        <aside className="grid content-start gap-4">
          <section className="product-card p-5 md:p-6" aria-labelledby="case-lifecycle-heading">
            <p className="section-kicker">Active case</p>
            <h2 id="case-lifecycle-heading" className="section-title mt-2">Carried through the financial day</h2>
            <ol className="mt-4 grid gap-3">
              {[
                ["Detected", `${item.company ?? item.instrument ?? "Event"} crossed movement rules.`],
                ["Investigated", `${item.direct_exposure_pct.toFixed(1)}% direct and ${item.sector_exposure_pct.toFixed(1)}% sector exposure checked.`],
                ["Alerted", `Decision: ${item.decision}. Relevance ${item.relevance_score.toFixed(1)}/100.`],
                ["Ready for follow-up", "Ask Copilot, research deeper, or send a packet to your advisor."],
              ].map(([label, detail], index) => (
                <li className="grid grid-cols-[28px_1fr] gap-3 text-xs" key={label}>
                  <span className="grid size-7 place-items-center rounded-full bg-brand-soft font-bold text-brand">{index + 1}</span>
                  <div>
                    <strong className="block text-sm text-ink">{label}</strong>
                    <span className="mt-0.5 block leading-5 text-muted">{detail}</span>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="product-card p-5 md:p-6" aria-labelledby="relevance-heading">
            <p className="section-kicker">Why this reached you</p>
            <h2 id="relevance-heading" className="section-title mt-2">Relevance {item.relevance_score.toFixed(0)}</h2>
            <p className="mt-3 text-sm leading-6 text-muted">{item.reason}</p>
            {assessment && (
              <ol className="mt-5 grid gap-3 border-t border-line pt-4">
                {assessment.trace.slice(0, 5).map((step, index) => (
                  <li className="grid grid-cols-[24px_1fr] gap-3 text-xs" key={`${step.stage}-${index}`}>
                    <span className="grid size-6 place-items-center rounded-full bg-brand/8 font-bold text-brand" aria-hidden="true">{index + 1}</span>
                    <div>
                      <strong className="font-semibold text-ink">{traceLabel(step.stage)}</strong>
                      <p className="mt-0.5 leading-5 text-muted">{step.outcome.replaceAll("_", " ")}</p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
            <p className="mt-5 border-t border-line pt-4 text-xs font-semibold leading-5 text-muted">
              Relevance and attention are determined by rules. AI helps explain the result; you make the decision.
            </p>
          </section>

          <section className="rounded-[var(--radius-card)] bg-[#12201b] p-5 text-white shadow-[var(--shadow-card)]">
            <Bot className="text-[#63dbc1]" aria-hidden="true" />
            <h2 className="mt-3 text-xl font-semibold tracking-tight">Work this case</h2>
            <p className="mt-2 text-sm leading-6 text-white/65">Same retained portfolio context can explain, research, or package this for a human advisor.</p>
            <div className="mt-4 grid gap-2">
              <Link href="/copilot" className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#63dbc1] px-4 py-3 text-xs font-bold text-[#12201b]">
                Explain with Copilot <ExternalLink size={14} aria-hidden="true" />
              </Link>
              <Link href="/copilot" className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-white/15 px-4 py-3 text-xs font-bold text-white">
                Research deeper <FileText size={14} aria-hidden="true" />
              </Link>
              <button
                type="button"
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-white/15 px-4 py-3 text-xs font-bold text-white"
                onClick={() => setAdvisorTarget({ type: "event", id: item.event_id, title: item.headline })}
              >
                Send case to advisor <Send size={14} aria-hidden="true" />
              </button>
            </div>
            <p className="mt-3 flex items-center gap-2 text-[11px] text-white/55"><UserRoundCheck size={13} /> Human-in-the-loop, no trade command.</p>
          </section>
        </aside>
      </div>
      <div className="mt-4">
        <AttentionPipeline trace={assessment?.trace} score={item.relevance_score} decision={item.decision} />
      </div>
      <div className="mt-4">
        <LikelyScenarios scenarios={query.data.likely_scenarios} watchEvents={query.data.calendar_watch_events} />
      </div>
      <AdvisorSheet target={advisorTarget} onClose={() => setAdvisorTarget(null)} />
    </div>
  );
}
