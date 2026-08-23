import { AlertCircle } from "lucide-react";

export function LoadingState({ label = "Loading your financial day" }: { label?: string }) {
  return (
    <div className="space-y-4" role="status" aria-live="polite" aria-label={label}>
      <span className="sr-only">{label}</span>
      <div className="skeleton-sheen h-5 w-28 rounded-full" />
      <div className="skeleton-sheen h-11 w-3/4 max-w-xl rounded-xl" />
      <div className="skeleton-sheen h-4 w-full max-w-2xl rounded-full" />
      <div className="grid gap-4 pt-3 md:grid-cols-2">
        <div className="product-card p-5"><div className="skeleton-sheen h-40 rounded-2xl" /></div>
        <div className="product-card p-5"><div className="skeleton-sheen h-40 rounded-2xl" /></div>
      </div>
    </div>
  );
}

export function ErrorState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-monitor/20 bg-monitor/5 p-5" role="alert">
      <AlertCircle className="mb-3 text-monitor"/>
      <h2 className="section-title">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted">{detail}</p>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="product-card p-6 text-center md:p-7">
      <h2 className="section-title text-xl">{title}</h2>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">{detail}</p>
    </div>
  );
}
