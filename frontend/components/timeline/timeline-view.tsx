"use client";

import { Activity, BookOpenText, CalendarClock, ListChecks, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/primitives/page-header";
import { ErrorState, LoadingState } from "@/components/primitives/states";
import { StatusBadge } from "@/components/primitives/status-badge";
import { WealthStoryControl } from "@/components/wealth-story";
import { DayClockControls } from "@/components/timeline/day-clock-controls";
import { useTimeline } from "@/hooks/use-product-queries";

type CheckpointDisplay = {
  label: string;
  icon: LucideIcon;
  iconClass: string;
};

const CHECKPOINT_DISPLAYS: Record<string, CheckpointDisplay> = {
  morning: { label: "Scheduled briefing", icon: CalendarClock, iconClass: "border-brand/20 bg-brand/8 text-brand" },
  health: { label: "Scheduled portfolio check", icon: ListChecks, iconClass: "border-brand/20 bg-brand/8 text-brand" },
  open: { label: "Automatic market check", icon: Activity, iconClass: "border-investigate/25 bg-investigate/8 text-investigate" },
  event: { label: "Automatic event review", icon: Activity, iconClass: "border-investigate/25 bg-investigate/8 text-investigate" },
  watch: { label: "Automatic market check", icon: Activity, iconClass: "border-investigate/25 bg-investigate/8 text-investigate" },
  sector: { label: "Portfolio insight", icon: BookOpenText, iconClass: "border-[#5576a7]/25 bg-[#5576a7]/8 text-[#5576a7]" },
  learning: { label: "Portfolio insight", icon: BookOpenText, iconClass: "border-[#5576a7]/25 bg-[#5576a7]/8 text-[#5576a7]" },
  intelligence: { label: "Portfolio insight", icon: BookOpenText, iconClass: "border-[#5576a7]/25 bg-[#5576a7]/8 text-[#5576a7]" },
  close: { label: "Day review", icon: ListChecks, iconClass: "border-positive/20 bg-positive/8 text-positive" },
  evening: { label: "Day review", icon: ListChecks, iconClass: "border-positive/20 bg-positive/8 text-positive" },
  story: { label: "Daily story", icon: Sparkles, iconClass: "border-positive/20 bg-positive/8 text-positive" },
  actions: { label: "Future preparation", icon: CalendarClock, iconClass: "border-[#8067a8]/25 bg-[#8067a8]/8 text-[#8067a8]" },
  tomorrow: { label: "Future preparation", icon: CalendarClock, iconClass: "border-[#8067a8]/25 bg-[#8067a8]/8 text-[#8067a8]" },
};

const DEFAULT_DISPLAY: CheckpointDisplay = {
  label: "Scheduled checkpoint",
  icon: CalendarClock,
  iconClass: "border-line bg-background text-muted",
};

export function TimelineView() {
  const query = useTimeline();
  if (query.isLoading) return <LoadingState label="Loading your financial timeline" />;
  if (!query.data) {
    return <ErrorState title="Timeline temporarily unavailable" detail="Your completed checkpoints remain stored and will reappear when the connection recovers." />;
  }

  const data = query.data;
  return (
    <div>
      <PageHeader
        eyebrow="Financial day"
        title="Context that compounds all day"
        description="Morning intelligence, proactive events, research, close and recap remain one continuous story."
        meta={<StatusBadge status={data.status} />}
      />
      {query.isError && (
        <p role="status" className="mb-4 rounded-xl border border-investigate/20 bg-investigate/5 px-4 py-3 text-xs text-muted">
          Showing your saved timeline while freshness checks recover.
        </p>
      )}
      <section className="mb-4 rounded-[var(--radius-card)] bg-[#12201b] p-5 text-white shadow-[var(--shadow-card)] md:p-6" aria-labelledby="timeline-progress">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="section-kicker section-kicker--dark">Today</p>
            <h2 id="timeline-progress" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">
              {data.completed_count} of {data.total_count} checkpoints complete
            </h2>
            <p className="mt-2 text-sm text-white/65">Your financial day updates automatically as each checkpoint finishes.</p>
          </div>
          {data.next_checkpoint && (
            <div className="min-w-48 rounded-xl border border-white/10 bg-white/7 px-4 py-3 text-sm">
              <span className="block text-[10px] font-bold tracking-wider text-white/50 uppercase">Next checkpoint</span>
              <strong className="mt-1 block">{data.next_checkpoint.scheduled_time} · {data.next_checkpoint.label}</strong>
            </div>
          )}
        </div>
        <DayClockControls />
      </section>

      <div className="grid gap-4 lg:grid-cols-[1fr_0.72fr]">
        <section className="product-card p-5 md:p-6" aria-labelledby="checkpoints-heading">
          <h2 id="checkpoints-heading" className="section-title mb-5">Today’s checkpoints</h2>
          <ol className="relative grid gap-0">
            {data.timeline.map((step, index) => {
              const display = CHECKPOINT_DISPLAYS[step.step_id] ?? DEFAULT_DISPLAY;
              const Icon = display.icon;
              return (
                <li className="relative grid grid-cols-[44px_32px_1fr] gap-3 pb-6 last:pb-0" key={step.step_id}>
                  <time className="pt-2 text-[10px] font-medium tabular-nums text-muted" dateTime={`${data.trading_date}T${step.scheduled_time}`}>
                    {step.scheduled_time}
                  </time>
                  <div className="relative flex justify-center">
                    <span className={`z-10 grid size-8 place-items-center rounded-full border ${display.iconClass}`}>
                      <Icon size={14} aria-hidden="true" />
                    </span>
                    {index < data.timeline.length - 1 && <span aria-hidden="true" className="absolute top-8 bottom-[-24px] w-px bg-line" />}
                  </div>
                  <div className="min-w-0 pt-0.5">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <span className="block text-[10px] font-bold tracking-wider text-muted uppercase">{display.label}</span>
                        <strong className="mt-0.5 block text-sm font-semibold text-ink">{step.label}</strong>
                      </div>
                      <StatusBadge status={step.status} />
                    </div>
                    <p className="mt-1.5 text-xs leading-5 text-muted">{step.detail}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>

        <aside className="grid content-start gap-4">
          <section className="product-card p-5" aria-labelledby="story-heading">
            <p className="section-kicker">Daily Wealth Story</p>
            <h2 id="story-heading" className="section-title mt-2">
              {data.status === "complete" ? "Your day is ready to replay" : "Built when the day finishes"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted">A short recap of what shaped your portfolio, based on this exact timeline.</p>
            <WealthStoryControl story={data.financial_day.daily_story} ready={data.status === "complete"} />
          </section>
          {data.financial_day.tomorrow_events.length > 0 && (
            <section className="product-card p-5" aria-labelledby="tomorrow-heading">
              <p className="section-kicker">Tomorrow</p>
              <h2 id="tomorrow-heading" className="sr-only">Tomorrow’s relevant events</h2>
              <div className="mt-3 divide-y divide-line">
                {data.financial_day.tomorrow_events.map((item) => (
                  <div className="py-3 first:pt-0 last:pb-0" key={item.event_id}>
                    <strong className="block text-sm font-semibold">{item.title}</strong>
                    <span className="mt-1 block text-xs text-muted">{item.portfolio_exposure_pct.toFixed(1)}% relevant exposure</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
