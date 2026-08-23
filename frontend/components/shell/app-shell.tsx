"use client";

import { BellRing, Bot, Clock3, Home, PieChart, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAlerts, useTimeline } from "@/hooks/use-product-queries";
import { cn } from "@/lib/cn";

const destinations = [
  { href: "/", label: "Today", icon: Home },
  { href: "/portfolio", label: "Portfolio", icon: PieChart },
  { href: "/copilot", label: "Copilot", icon: Bot },
  { href: "/alerts", label: "Alerts", icon: BellRing },
  { href: "/timeline", label: "Timeline", icon: Clock3 },
];

function activePath(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const timeline = useTimeline();
  const alerts = useAlerts();
  const day = timeline.data;
  const alertCount = (alerts.data?.counts.attention ?? 0) + (alerts.data?.counts.investigating ?? 0);

  return (
    <div className="min-h-screen bg-background text-ink">
      <header className="sticky top-0 z-40 border-b border-line/80 bg-background/90 backdrop-blur-xl md:hidden">
        <div className="flex h-15 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2 rounded-lg font-bold tracking-tight">
            <span className="grid size-8 place-items-center rounded-xl bg-brand text-white"><Sparkles size={16}/></span>
            Wealth Copilot
          </Link>
          <span className="text-right text-[10px] leading-4 text-muted">
            {day ? new Date(day.trading_date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }) : "Today"}
            <strong className="block text-brand">{day?.status === "complete" ? "Day complete" : day?.status === "running" ? "Updating" : "Monitoring"}</strong>
          </span>
        </div>
      </header>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-line bg-surface px-4 py-6 md:flex md:flex-col">
        <Link href="/" className="flex items-center gap-3 rounded-xl px-2 text-lg font-bold tracking-tight">
          <span className="grid size-10 place-items-center rounded-2xl bg-brand text-white shadow-lg shadow-brand/15"><Sparkles size={19}/></span>
          Wealth Copilot
        </Link>
        <nav className="mt-10 grid gap-2" aria-label="Primary navigation">
          {destinations.map(({ href, label, icon: Icon }) => {
            const active = activePath(pathname, href);
            return (
              <Link key={href} href={href} className={cn(
                "flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-muted transition-colors",
                active && "bg-brand-soft text-brand",
              )} aria-current={active ? "page" : undefined}>
                <Icon size={18}/>{label}
                {href === "/alerts" && alertCount > 0 && <span className="ml-auto grid min-w-5 place-items-center rounded-full bg-negative px-1.5 py-0.5 text-[10px] font-bold text-white" aria-label={`${alertCount} alerts need attention`}>{alertCount}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-2xl border border-line bg-background p-4 text-xs leading-5 text-muted">
          <strong className="block text-ink">{day?.completed_count ?? 0}/{day?.total_count ?? 13} checkpoints</strong>
          Financial truth stays in the backend.
        </div>
      </aside>

      <main className="w-full px-4 pt-6 pb-[calc(7.25rem+env(safe-area-inset-bottom))] md:ml-60 md:w-[calc(100%-15rem)] md:px-8 md:pt-9 md:pb-12 lg:px-12">
        <div className="mx-auto w-full max-w-6xl">{children}</div>
      </main>

      <nav data-mobile-nav className="fixed right-2 bottom-[calc(.5rem+env(safe-area-inset-bottom))] left-2 z-50 grid h-[4.25rem] grid-cols-5 rounded-[1.35rem] border border-white/10 bg-[#12201b]/96 p-1 text-white shadow-2xl backdrop-blur-xl md:hidden" aria-label="Primary navigation">
        {destinations.map(({ href, label, icon: Icon }) => {
          const active = activePath(pathname, href);
          return (
            <Link key={href} href={href} className={cn(
              "flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-[1rem] text-[9px] leading-none text-white/60 transition-colors min-[360px]:text-[10px]",
              active && "bg-brand text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,.08)]",
            )} aria-current={active ? "page" : undefined}>
              <span className="relative">
                <Icon size={href === "/copilot" ? 21 : 18}/>
                {href === "/alerts" && alertCount > 0 && <span className="absolute -top-1.5 -right-2 grid min-w-4 place-items-center rounded-full bg-[#ff826f] px-1 py-0.5 text-[8px] font-bold text-[#12201b]" aria-label={`${alertCount} alerts need attention`}>{alertCount}</span>}
              </span>{label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
