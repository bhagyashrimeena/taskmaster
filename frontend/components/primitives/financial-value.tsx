import { cn } from "@/lib/cn";

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

export function FinancialValue({
  value,
  change,
  className,
}: {
  value: number;
  change?: boolean;
  className?: string;
}) {
  return (
    <span className={cn(
      "font-semibold tabular-nums",
      change && value > 0 && "text-positive",
      change && value < 0 && "text-negative",
      change && value === 0 && "text-muted",
      className,
    )}>
      {change && value > 0 ? "+" : ""}{inr.format(value)}
    </span>
  );
}

export function PercentChange({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">No move yet</span>;
  return (
    <span className={cn(
      "font-semibold tabular-nums",
      value > 0 ? "text-positive" : value < 0 ? "text-negative" : "text-muted",
    )}>
      {value > 0 ? "+" : ""}{value.toFixed(2)}%
    </span>
  );
}
