"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/primitives/states";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="space-y-4">
      <ErrorState
        title="This view is temporarily unavailable"
        detail="Your financial state is unchanged. Retry this view while Wealth Copilot keeps monitoring in the background."
      />
      <button
        type="button"
        onClick={reset}
        className="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white"
      >
        Try again
      </button>
    </div>
  );
}
