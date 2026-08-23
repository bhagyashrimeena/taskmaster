import Link from "next/link";
import { WifiOff } from "lucide-react";

export default function OfflinePage() {
  return (
    <section className="mx-auto grid min-h-[55vh] max-w-xl place-items-center text-center">
      <div className="rounded-3xl border border-line bg-surface p-8 shadow-sm">
        <WifiOff className="mx-auto mb-4 text-muted" />
        <h1 className="font-display text-3xl">You are offline</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Wealth Copilot needs a connection to verify your latest portfolio and market state. No cached value is presented as current.
        </p>
        <Link href="/" className="mt-6 inline-flex rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white">
          Try again
        </Link>
      </div>
    </section>
  );
}
