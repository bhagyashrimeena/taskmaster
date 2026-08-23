import { cn } from "@/lib/cn";

const statusStyles: Record<string, string> = {
  ALERT: "border-alert/25 bg-alert/10 text-alert",
  ALERTED: "border-alert/25 bg-alert/10 text-alert",
  ATTENTION: "border-alert/25 bg-alert/10 text-alert",
  INVESTIGATE: "border-investigate/25 bg-investigate/10 text-investigate",
  INVESTIGATING: "border-investigate/25 bg-investigate/10 text-investigate",
  MONITOR: "border-monitor/25 bg-monitor/10 text-monitor",
  MONITORING: "border-monitor/25 bg-monitor/10 text-monitor",
  WATCH: "border-monitor/25 bg-monitor/10 text-monitor",
  IGNORE: "border-line bg-background text-muted",
  IGNORED: "border-line bg-background text-muted",
  COMPLETE: "border-brand/20 bg-brand-soft text-brand",
  RUNNING: "border-investigate/25 bg-investigate/10 text-investigate",
  PENDING: "border-line bg-background text-muted",
  FAILED: "border-negative/25 bg-negative/10 text-negative",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const key = status.toUpperCase();
  return (
    <span className={cn(
      "inline-flex min-h-6 items-center rounded-full border px-2.5 py-1 text-[10px] font-extrabold tracking-[0.08em] uppercase",
      statusStyles[key] ?? "border-line bg-background text-muted",
      className,
    )}>
      {status.replaceAll("_", " ")}
    </span>
  );
}
