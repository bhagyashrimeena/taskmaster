import { BellRing, Eye, Filter, Gauge, Layers3, Link2, Percent, SearchCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { TraceStep } from "@/lib/types";

type PipelineStage = {
  key: string;
  label: string;
  short: string;
  icon: LucideIcon;
};

const stages: PipelineStage[] = [
  { key: "observe", label: "Observe", short: "market + portfolio", icon: Eye },
  { key: "filter", label: "Filter", short: "dedupe noise", icon: Filter },
  { key: "match", label: "Match", short: "holdings + sectors", icon: Link2 },
  { key: "exposure", label: "Exposure", short: "direct + sector", icon: Layers3 },
  { key: "materiality", label: "Materiality", short: "move + event", icon: Percent },
  { key: "score", label: "Score", short: "rules decide", icon: Gauge },
  { key: "outcome", label: "Outcome", short: "ignore → alert", icon: BellRing },
  { key: "surface", label: "Surface", short: "explain + act", icon: SearchCheck },
];

function stageOutcome(trace: TraceStep[] | undefined, stage: PipelineStage) {
  if (!trace?.length) return stage.short;
  const lower = stage.key.toLowerCase();
  const match = trace.find((step) => step.stage.toLowerCase().includes(lower));
  if (!match) return stage.short;
  return match.outcome.replaceAll("_", " ").toLowerCase();
}

export function AttentionPipeline({
  trace,
  score,
  decision,
  compact = false,
}: {
  trace?: TraceStep[];
  score?: number;
  decision?: string;
  compact?: boolean;
}) {
  return (
    <section className="product-card p-4 md:p-5" aria-labelledby="attention-pipeline-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="section-kicker">Attention pipeline</p>
          <h2 id="attention-pipeline-title" className="section-title mt-1.5">
            Observe → Filter → Match → Score → Surface
          </h2>
        </div>
        {(score !== undefined || decision) && (
          <div className="rounded-2xl border border-brand/20 bg-brand/8 px-3 py-2 text-right">
            <span className="block text-[10px] font-bold uppercase tracking-wider text-muted">Outcome</span>
            <strong className="text-sm text-brand">
              {score !== undefined ? `${score.toFixed(1)}/100` : ""} {decision ? `· ${decision}` : ""}
            </strong>
          </div>
        )}
      </div>
      <ol className={`mt-4 grid gap-2 ${compact ? "grid-cols-2 min-[420px]:grid-cols-4" : "grid-cols-2 md:grid-cols-4"}`}>
        {stages.map((stage) => {
          const Icon = stage.icon;
          return (
            <li key={stage.key} className="rounded-2xl border border-line bg-background/70 p-3">
              <span className="grid size-8 place-items-center rounded-xl bg-brand-soft text-brand">
                <Icon size={15} aria-hidden="true" />
              </span>
              <strong className="mt-2 block text-xs font-extrabold uppercase tracking-[0.12em] text-ink">{stage.label}</strong>
              <span className="mt-1 block text-[11px] leading-4 text-muted">{stageOutcome(trace, stage)}</span>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-xs leading-5 text-muted">
        Deterministic engines decide attention priority. The AI explains the result and helps research; it does not issue trade instructions.
      </p>
    </section>
  );
}
