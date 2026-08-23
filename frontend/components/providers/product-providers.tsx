"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { BellRing, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getAlerts, productEventStreamUrl } from "@/lib/api/product";
import type { ProductEvent } from "@/lib/product-types";
import { productKeys } from "@/lib/queries/keys";
import { useUiStore } from "@/stores/ui-store";

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
  const showProactiveAlert = useUiStore((state) => state.showProactiveAlert);

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
              if (!item) return;
              showProactiveAlert({
                eventId: item.event_id,
                caseId: item.case_id,
                title: item.company ?? item.instrument ?? "Portfolio event",
                summary: item.reason,
              });
            }).catch(() => undefined);
          }
        }
      } else if (event.event_type === "AUDIO_READY") {
        void queryClient.invalidateQueries({ queryKey: productKeys.today });
      }
    };
    ["SNAPSHOT", "CHECKPOINT_COMPLETED", "EVENT_ALERT_CREATED", "FINANCIAL_CASE_UPDATED", "AUDIO_READY"].forEach(
      (name) => source.addEventListener(name, refresh as EventListener),
    );
    return () => source.close();
  }, [queryClient, showProactiveAlert]);

  return null;
}

function ProactiveAlertToast() {
  const router = useRouter();
  const notice = useUiStore((state) => state.proactiveAlert);
  const dismiss = useUiStore((state) => state.dismissProactiveAlert);
  if (!notice) return null;
  const view = () => {
    dismiss();
    router.push(notice.caseId ? `/alerts/${notice.caseId}` : "/alerts");
  };
  return (
    <aside className="fixed right-3 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] left-3 z-[70] mx-auto max-w-md rounded-2xl border border-[#8ed3bd]/30 bg-[#102c24] p-4 text-white shadow-2xl md:right-6 md:bottom-6 md:left-auto" role="alert" aria-label="New proactive portfolio alert" data-testid="proactive-alert-toast">
      <div className="grid grid-cols-[36px_1fr_44px] gap-3">
        <span className="grid size-9 place-items-center rounded-xl bg-[#63dbc1]/15 text-[#63dbc1]"><BellRing size={17} aria-hidden="true" /></span>
        <div className="min-w-0">
          <p className="text-[10px] font-bold tracking-wider text-[#63dbc1] uppercase">New proactive alert</p>
          <strong className="mt-1 block text-sm">{notice.title}</strong>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-white/65">{notice.summary}</p>
          <button className="mt-2 min-h-11 rounded-xl bg-white px-4 text-xs font-bold text-[#12382e]" type="button" onClick={view}>View alert</button>
        </div>
        <button className="grid size-11 place-items-center rounded-xl text-white/65 hover:bg-white/10" type="button" onClick={dismiss} aria-label="Dismiss proactive alert"><X size={17} aria-hidden="true" /></button>
      </div>
    </aside>
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
      <ServiceWorkerRegistrar />
      {children}
      <ProactiveAlertToast />
    </QueryClientProvider>
  );
}
