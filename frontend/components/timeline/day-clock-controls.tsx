"use client";

import { ArrowRight, Clock3, Pause, Play, RotateCcw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useFinancialDayClock, useFinancialDayClockControls, useTimeline } from "@/hooks/use-product-queries";
import { useUiStore } from "@/stores/ui-store";

export function DayClockControls() {
  const clock = useFinancialDayClock();
  const timeline = useTimeline();
  const controls = useFinancialDayClockControls();
  const [confirmingRestart, setConfirmingRestart] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const showActivityToast = useUiStore((store) => store.showActivityToast);
  const state = clock.data;
  const hasProgress = Boolean(state?.completed_checkpoint_ids.length);
  const running = state?.status === "running";
  const complete = state?.status === "complete";
  const failed = state?.status === "failed";
  const upcoming = timeline.data?.next_checkpoint;
  const error = clock.isError || controls.start.isError || controls.pause.isError || controls.restart.isError || controls.advance.isError;

  useEffect(() => {
    if (!confirmingRestart) return;
    closeRef.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setConfirmingRestart(false);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [confirmingRestart]);

  const togglePlayback = () => {
    if (running) {
      controls.pause.mutate(undefined, {
        onSuccess: (next) => showActivityToast({
          id: `${next.trading_date}:control-paused:${next.current_time}`,
          tone: "info",
          title: "Financial day paused",
          detail: next.message,
          durationMs: 4_500,
          replaceCurrent: true,
        }),
      });
      return;
    }
    controls.start.mutate(undefined, {
      onSuccess: (next) => showActivityToast({
        id: `${next.trading_date}:control-started:${next.current_time}`,
        tone: "info",
        title: hasProgress || failed ? "Playing remaining updates" : "Financial day started",
        detail: "Updates will continue automatically until you pause.",
        durationMs: 4_500,
        replaceCurrent: true,
      }),
    });
  };

  const confirmRestart = () => {
    setConfirmingRestart(false);
    controls.restart.mutate(undefined, {
      onSuccess: (next) => showActivityToast({
        id: `${next.trading_date}:control-restarted:${next.current_time}`,
        tone: "info",
        title: "Financial day restarted",
        detail: "Ready at 07:00. Run each update when you are ready.",
        durationMs: 5_000,
        replaceCurrent: true,
      }),
    });
  };

  return (
    <div className="mt-5 border-t border-white/10 pt-4" data-testid="day-clock-controls">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-xs text-white/70" aria-live="polite">
          <Clock3 className="shrink-0 text-[#63dbc1]" size={16} aria-hidden="true" />
          <span>
            <strong className="font-semibold text-white">{state?.current_time ?? "07:00"}</strong>
            <span className="mx-1.5 text-white/30">·</span>
            {state?.message ?? "Ready to begin your financial day."}
          </span>
        </div>
        <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
          <button
            className="col-span-2 inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-white px-4 text-xs font-bold text-[#12382e] transition-colors hover:bg-[#eef8f3] disabled:cursor-wait disabled:opacity-60 sm:col-span-1 sm:flex-none"
            type="button"
            onClick={() => controls.advance.mutate()}
            disabled={controls.pending || clock.isLoading || running || complete || !state?.next_checkpoint}
            aria-label={upcoming ? `Run next update: ${upcoming.label} at ${upcoming.scheduled_time}` : "Run next financial-day update"}
          >
            <ArrowRight size={16} aria-hidden="true" />
            {running ? "Update running…" : complete ? "Day complete" : "Run next update"}
          </button>
          <button
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border border-white/20 px-4 text-xs font-bold text-white transition-colors hover:bg-white/8 disabled:cursor-wait disabled:opacity-60 sm:flex-none"
            type="button"
            onClick={togglePlayback}
            disabled={controls.pending || clock.isLoading || complete}
          >
            {running ? <Pause size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}
            {running ? "Pause" : "Play all"}
          </button>
          {(hasProgress || complete || failed) && (
            <button
              className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border border-white/20 px-4 text-xs font-bold text-white transition-colors hover:bg-white/8 disabled:cursor-wait disabled:opacity-60 sm:flex-none"
              type="button"
              onClick={() => setConfirmingRestart(true)}
              disabled={controls.pending}
            >
              <RotateCcw size={15} aria-hidden="true" /> Restart
            </button>
          )}
        </div>
      </div>
      <p className="mt-3 text-[11px] leading-5 text-white/60">
        {upcoming
          ? <>Next: <strong className="font-semibold text-white">{upcoming.scheduled_time} · {upcoming.label}</strong></>
          : complete
            ? "All of today’s updates are complete."
            : "Preparing the next financial update."}
      </p>
      {error && (
        <p className="mt-2 rounded-lg bg-white/8 px-3 py-2 text-xs text-[#ffd9a1]" role="alert">
          The day control could not update. Your saved updates are intact; try again.
        </p>
      )}

      {confirmingRestart && (
        <div className="fixed inset-0 z-[80] grid place-items-center bg-[#07130f]/55 p-4 backdrop-blur-sm" role="presentation" onMouseDown={(event) => {
          if (event.currentTarget === event.target) setConfirmingRestart(false);
        }}>
          <section className="w-full max-w-sm rounded-[var(--radius-card)] border border-line bg-surface p-5 text-ink shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="restart-day-title" aria-describedby="restart-day-detail">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="section-kicker">Financial day</p>
                <h2 id="restart-day-title" className="mt-2 text-xl font-semibold tracking-tight">Restart at 07:00?</h2>
              </div>
              <button ref={closeRef} className="grid size-11 shrink-0 place-items-center rounded-xl text-muted hover:bg-background" type="button" onClick={() => setConfirmingRestart(false)} aria-label="Close restart confirmation">
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <p id="restart-day-detail" className="mt-3 text-sm leading-6 text-muted">This clears today’s simulated progress and pauses at 07:00. You can then run each update one at a time.</p>
            <div className="mt-5 grid grid-cols-2 gap-2">
              <button className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold" type="button" onClick={() => setConfirmingRestart(false)}>Keep current day</button>
              <button className="min-h-11 rounded-xl bg-brand px-4 text-sm font-semibold text-white" type="button" onClick={confirmRestart}>Restart at 07:00</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
