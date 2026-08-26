"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { BellRing, CheckCircle2, Info, Volume2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getAlerts, productEventStreamUrl } from "@/lib/api/product";
import type { ProductEvent } from "@/lib/product-types";
import type { FinancialDayClockState } from "@/lib/types";
import { productKeys } from "@/lib/queries/keys";
import { useUiStore } from "@/stores/ui-store";
import { useFinancialDayClock } from "@/hooks/use-product-queries";

const checkpointNotices: Record<string, {
  title: string;
  detail: string;
  actionLabel: string;
  actionHref: string;
}> = {
  morning: { title: "Morning brief is ready", detail: "Your portfolio-aware morning briefing is ready to review.", actionLabel: "View Today", actionHref: "/" },
  health: { title: "Portfolio health check is ready", detail: "Your latest exposure and concentration check is ready.", actionLabel: "View Portfolio", actionHref: "/portfolio" },
  open: { title: "Market open update is ready", detail: "See how the market open affected your holdings.", actionLabel: "View Today", actionHref: "/" },
  watch: { title: "Market watch updated", detail: "Your latest portfolio-relevant market scan is ready.", actionLabel: "View Timeline", actionHref: "/timeline" },
  sector: { title: "Sector exposure insight is ready", detail: "Your sector concentration view has been refreshed.", actionLabel: "View Portfolio", actionHref: "/portfolio" },
  learning: { title: "Portfolio learning is ready", detail: "A new insight based on your holdings is ready.", actionLabel: "View Portfolio", actionHref: "/portfolio" },
  close: { title: "Market close review is ready", detail: "See what changed across your portfolio today.", actionLabel: "View Today", actionHref: "/" },
  intelligence: { title: "Portfolio insight is ready", detail: "Your portfolio intelligence summary has been refreshed.", actionLabel: "View Portfolio", actionHref: "/portfolio" },
  actions: { title: "Action list is ready", detail: "Review what may deserve your attention next.", actionLabel: "View Timeline", actionHref: "/timeline" },
  evening: { title: "Evening wealth wrap is ready", detail: "Your end-of-day portfolio summary is ready.", actionLabel: "View Today", actionHref: "/" },
  tomorrow: { title: "Tomorrow’s watchlist is ready", detail: "Review events that could affect your holdings tomorrow.", actionLabel: "View Timeline", actionHref: "/timeline" },
  story: { title: "Daily wealth story is ready", detail: "Replay the events that shaped your portfolio today.", actionLabel: "View recap", actionHref: "/timeline" },
};

const seenAlertKey = "wealth-copilot-seen-alerts-v1";

function seenAlerts() {
  try {
    return new Set<string>(JSON.parse(sessionStorage.getItem(seenAlertKey) ?? "[]"));
  } catch {
    return new Set<string>();
  }
}

function rememberAlert(id: string) {
  try {
    const seen = seenAlerts();
    seen.add(id);
    sessionStorage.setItem(seenAlertKey, JSON.stringify([...seen].slice(-100)));
  } catch {
    // Query invalidation still works when session storage is unavailable.
  }
}

function ProductEventBridge() {
  const queryClient = useQueryClient();
  const showActivityToast = useUiStore((state) => state.showActivityToast);

  useEffect(() => {
    const source = new EventSource(productEventStreamUrl);
    const refresh = (raw: MessageEvent<string>) => {
      let event: ProductEvent;
      try {
        event = JSON.parse(raw.data) as ProductEvent;
      } catch {
        return;
      }
      if (event.event_type === "SNAPSHOT") {
        const ids = Array.isArray(event.data.alert_event_ids) ? event.data.alert_event_ids : [];
        ids.forEach((id) => {
          if (typeof id === "string") rememberAlert(`${event.run_id}:${id}`);
        });
      } else if (event.event_type === "CHECKPOINT_COMPLETED") {
        void queryClient.invalidateQueries({ queryKey: productKeys.timeline });
        void queryClient.invalidateQueries({ queryKey: productKeys.today });
      } else if (event.event_type === "EVENT_ALERT_CREATED" || event.event_type === "FINANCIAL_CASE_UPDATED") {
        void queryClient.invalidateQueries({ queryKey: productKeys.all });
        if (event.event_type === "EVENT_ALERT_CREATED" && event.entity_id) {
          const seenId = `${event.run_id}:${event.entity_id}`;
          if (!seenAlerts().has(seenId)) {
            rememberAlert(seenId);
            void getAlerts().then((inbox) => {
              const item = inbox.items.find((candidate) => candidate.event_id === event.entity_id);
              showActivityToast({
                id: `${event.run_id}:alert-created:${event.entity_id}`,
                tone: "alert",
                title: item ? `${item.company ?? item.instrument ?? "Portfolio"} needs attention` : "Portfolio alert needs attention",
                detail: item?.reason ?? "A portfolio-relevant event crossed your attention rules.",
                actionLabel: "Review alert",
                actionHref: item?.case_id ? `/alerts/${item.case_id}` : "/alerts",
                durationMs: 12_000,
              });
            }).catch(() => showActivityToast({
              id: `${event.run_id}:alert-created:${event.entity_id}`,
              tone: "alert",
              title: "Portfolio alert needs attention",
              detail: "A portfolio-relevant event crossed your attention rules.",
              actionLabel: "Review alerts",
              actionHref: "/alerts",
              durationMs: 12_000,
            }));
          }
        }
      } else if (event.event_type === "AUDIO_READY") {
        void queryClient.invalidateQueries({ queryKey: productKeys.today });
        showActivityToast({
          id: `${event.run_id}:audio-ready:${event.entity_id ?? "brief"}`,
          tone: "success",
          title: "Audio brief ready",
          detail: "A generated audio recap is available on Today.",
          actionLabel: "Open Today",
          actionHref: "/",
          durationMs: 7_000,
        });
      }
    };
    ["SNAPSHOT", "CHECKPOINT_COMPLETED", "EVENT_ALERT_CREATED", "FINANCIAL_CASE_UPDATED", "AUDIO_READY"].forEach(
      (name) => source.addEventListener(name, refresh as EventListener),
    );
    return () => source.close();
  }, [queryClient, showActivityToast]);

  return null;
}

function clockToastForStatus(previous: FinancialDayClockState | null, current: FinancialDayClockState) {
  if (!previous) return null;
  if (previous.status === current.status) return null;
  if (current.status === "failed") {
    return {
      id: `${current.trading_date}:clock-failed:${current.current_time}`,
      tone: "alert" as const,
      title: "Financial day paused safely",
      detail: current.message,
      actionLabel: "Check Timeline",
      actionHref: "/timeline",
    };
  }
  return null;
}

function ClockActivityNotifier() {
  const clock = useFinancialDayClock();
  const showActivityToast = useUiStore((state) => state.showActivityToast);
  const previous = useRef<FinancialDayClockState | null>(null);

  useEffect(() => {
    const current = clock.data;
    if (!current) return;
    const statusToast = clockToastForStatus(previous.current, current);
    if (statusToast) showActivityToast(statusToast);
    if (previous.current) {
      const priorCompleted = new Set(previous.current.completed_checkpoint_ids);
      for (const stepId of current.completed_checkpoint_ids) {
        if (priorCompleted.has(stepId) || stepId === "event") continue;
        const notice = checkpointNotices[stepId];
        if (!notice) continue;
        showActivityToast({
          id: `${current.trading_date}:checkpoint-complete:${stepId}`,
          tone: "success",
          ...notice,
          durationMs: 6_000,
        });
      }
    }
    previous.current = current;
  }, [clock.data, showActivityToast]);

  return null;
}

function ActivityToastStack() {
  const router = useRouter();
  const toast = useUiStore((state) => state.activityToast);
  const dismiss = useUiStore((state) => state.dismissActivityToast);

  useEffect(() => {
    if (!toast || toast.durationMs === null) return;
    const timer = window.setTimeout(() => dismiss(toast.id), toast.durationMs ?? 6_000);
    return () => window.clearTimeout(timer);
  }, [dismiss, toast]);

  if (!toast) return null;
  const tone = toast.tone ?? "info";
  const Icon = tone === "alert" ? BellRing : tone === "success" ? CheckCircle2 : toast.title.toLowerCase().includes("audio") ? Volume2 : Info;
  return (
    <section className="activity-toast-stack" aria-live="polite" aria-label="Wealth Copilot activity notifications">
      <article className={`activity-toast activity-toast--${tone}`} key={toast.id} role={tone === "alert" ? "alert" : "status"} data-testid="activity-toast">
        <span className="activity-toast__icon"><Icon size={17} aria-hidden="true" /></span>
        <div className="min-w-0">
          <strong>{toast.title}</strong>
          {toast.detail && <p>{toast.detail}</p>}
          {toast.actionHref && toast.actionLabel && (
            <button
              type="button"
              onClick={() => {
                dismiss(toast.id);
                router.push(toast.actionHref!);
              }}
            >
              {toast.actionLabel}
            </button>
          )}
        </div>
        <button className="activity-toast__close" type="button" onClick={() => dismiss(toast.id)} aria-label={`Dismiss ${toast.title}`}>
          <X size={15} aria-hidden="true" />
        </button>
      </article>
    </section>
  );
}

function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      void navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" });
    }
  }, []);

  return null;
}

export function ProductProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, gcTime: 10 * 60_000, retry: 2 },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      <ProductEventBridge />
      <ClockActivityNotifier />
      <ServiceWorkerRegistrar />
      {children}
      <ActivityToastStack />
    </QueryClientProvider>
  );
}
