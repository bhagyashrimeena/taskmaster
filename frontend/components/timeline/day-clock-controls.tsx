"use client";

import { Clock3, Pause, Play, RotateCcw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useFinancialDayClock, useFinancialDayClockControls } from "@/hooks/use-product-queries";

export function DayClockControls() {
  const clock = useFinancialDayClock();
  const controls = useFinancialDayClockControls();
  const [confirmingRestart, setConfirmingRestart] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const state = clock.data;
  const hasProgress = Boolean(state?.completed_checkpoint_ids.length);
  const running = state?.status === "running";
  const complete = state?.status === "complete";
  const failed = state?.status === "failed";
  const error = clock.isError || controls.start.isError || controls.pause.isError || controls.restart.isError;

  useEffect(() => {
    if (!confirmingRestart) return;
    closeRef.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setConfirmingRestart(false);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [confirmingRestart]);

  const primaryLabel = complete
    ? "Restart the day"
    : running
      ? "Pause the day"
      : hasProgress || failed
        ? "Resume the day"
        : "Start the day";

  const activatePrimary = () => {
    if (complete) {
      setConfirmingRestart(true);
    } else if (running) {
      controls.pause.mutate();
    } else {
      controls.start.mutate();
    }
  };

  const confirmRestart = () => {
    setConfirmingRestart(false);
    controls.restart.mutate();
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
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <button
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-white px-4 text-xs font-bold text-[#12382e] transition-colors hover:bg-[#eef8f3] disabled:cursor-wait disabled:opacity-60 sm:flex-none"
            type="button"
            onClick={activatePrimary}
            disabled={controls.pending || clock.isLoading}
          >
            {running ? <Pause size={15} aria-hidden="true" /> : complete ? <RotateCcw size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}
            {primaryLabel}
          </button>
          {hasProgress && !complete && (
            <button
              className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border border-white/20 px-4 text-xs font-bold text-white transition-colors hover:bg-white/8 disabled:cursor-wait disabled:opacity-60 sm:flex-none"
              type="button"
              onClick={() => setConfirmingRestart(true)}
              disabled={controls.pending}
            >
              <RotateCcw size={15} aria-hidden="true" /> Restart the day
            </button>
          )}
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-5 text-white/50">Portfolio-relevant alerts appear automatically when an event crosses your rules.</p>
      {error && (
        <p className="mt-2 rounded-lg bg-white/8 px-3 py-2 text-xs text-[#ffd9a1]" role="alert">
          The day control could not update. Your saved checkpoints are intact; try again.
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
                <h2 id="restart-day-title" className="mt-2 text-xl font-semibold tracking-tight">Restart the day?</h2>
              </div>
              <button ref={closeRef} className="grid size-11 shrink-0 place-items-center rounded-xl text-muted hover:bg-background" type="button" onClick={() => setConfirmingRestart(false)} aria-label="Close restart confirmation">
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <p id="restart-day-detail" className="mt-3 text-sm leading-6 text-muted">This clears today’s simulated progress, returns the clock to 07:00, and starts all checkpoints again.</p>
            <div className="mt-5 grid grid-cols-2 gap-2">
              <button className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold" type="button" onClick={() => setConfirmingRestart(false)}>Keep current day</button>
              <button className="min-h-11 rounded-xl bg-brand px-4 text-sm font-semibold text-white" type="button" onClick={confirmRestart}>Restart and start</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
