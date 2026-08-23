import Link from "next/link";

import { EmptyState } from "@/components/primitives/states";

export default function NotFound() {
  return (
    <div className="space-y-4">
      <EmptyState title="That view is not available" detail="Return to Today to see what deserves your attention next." />
      <Link href="/" className="inline-flex rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white">
        Go to Today
      </Link>
    </div>
  );
}
