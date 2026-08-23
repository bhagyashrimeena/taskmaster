"use client";

import { ChevronDown, ShieldCheck } from "lucide-react";

import { AllocationDonut, ContributionBars, PortfolioHorizonChart, SectorBars } from "@/components/charts/portfolio-charts";
import { FinancialValue, PercentChange } from "@/components/primitives/financial-value";
import { PageHeader } from "@/components/primitives/page-header";
import { ErrorState, LoadingState } from "@/components/primitives/states";
import { usePortfolio } from "@/hooks/use-product-queries";
import type { PortfolioData } from "@/lib/product-types";
import { useUiStore } from "@/stores/ui-store";

function ChartCard({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return <section className="product-card p-4 md:p-5"><span className="section-kicker">{eyebrow}</span><h2 className="section-title mt-1.5">{title}</h2><div className="mt-4">{children}</div></section>;
}

type Holding = PortfolioData["largest_holdings"][number];

function holdingGroup(assetClass: string | null) {
  const normalized = assetClass?.toLowerCase() ?? "";
  if (normalized.includes("equity")) return "equities";
  if (normalized.includes("mutual")) return "funds";
  return "defensive";
}

function HoldingsGroup({ title, holdings, open = false }: { title: string; holdings: Holding[]; open?: boolean }) {
  if (!holdings.length) return null;
  return (
    <details className="group border-t border-line first:border-t-0" open={open}>
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 py-3 text-sm font-bold marker:content-none"><span>{title} <small className="ml-1 font-medium text-muted">{holdings.length}</small></span><ChevronDown size={16} className="text-muted transition-transform group-open:rotate-180"/></summary>
      <div className="divide-y divide-line pb-2">{holdings.map((holding) => <div className="grid grid-cols-[1fr_auto] gap-3 py-3" key={holding.symbol}><div className="min-w-0"><strong className="block truncate text-sm">{holding.symbol}</strong><span className="block truncate text-xs text-muted">{holding.name}</span></div><div className="text-right"><FinancialValue value={holding.market_value} className="block text-sm"/><span className="mt-0.5 flex justify-end gap-2 text-xs"><span className="text-muted">{holding.portfolio_weight.toFixed(1)}%</span><FinancialValue value={holding.day_pnl ?? 0} change/></span></div></div>)}</div>
    </details>
  );
}

export function PortfolioView() {
  const query = usePortfolio();
  const range = useUiStore((state) => state.portfolioRange);
  const setRange = useUiStore((state) => state.setPortfolioRange);
  if (query.isLoading) return <LoadingState label="Loading your portfolio"/>;
  if (!query.data) return <ErrorState title="Portfolio connection unavailable" detail="We’ll keep showing the last successful snapshot when one is available."/>;
  const portfolio = query.data.portfolio;
  const equities = portfolio.largest_holdings.filter((holding) => holdingGroup(holding.asset_class) === "equities");
  const funds = portfolio.largest_holdings.filter((holding) => holdingGroup(holding.asset_class) === "funds");
  const defensive = portfolio.largest_holdings.filter((holding) => holdingGroup(holding.asset_class) === "defensive");

  return (
    <div>
      <PageHeader eyebrow="Portfolio" title="Your money, in context" description="Performance, allocation, exposure and the holdings that moved your wealth." meta={<span className="inline-flex items-center gap-2 rounded-xl bg-brand-soft px-3 py-2 text-xs font-bold text-brand"><ShieldCheck size={14}/>{portfolio.source.label}</span>}/>
      {query.isError && <p role="status" className="mb-4 rounded-xl border border-investigate/20 bg-investigate/5 px-4 py-3 text-xs text-muted">Showing the latest saved snapshot while freshness checks recover.</p>}
      <section className="product-card mb-4 grid grid-cols-2 gap-0 overflow-hidden sm:grid-cols-[1.35fr_1fr_1fr]">
        <div className="col-span-2 p-5 sm:col-span-1"><span className="metric-label">Portfolio value</span><FinancialValue value={portfolio.portfolio_value} className="mt-1.5 block text-4xl font-semibold tracking-tight md:text-[2.7rem]"/><span className="mt-1 block text-xs text-muted">As of {new Date(portfolio.as_of).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</span></div>
        <div className="border-t border-line p-4 sm:border-t-0 sm:border-l sm:p-5"><span className="metric-label">Today</span><FinancialValue value={portfolio.day_pnl ?? 0} change className="mt-2 block text-lg"/><div className="mt-1 text-sm"><PercentChange value={portfolio.day_change_pct}/></div></div>
        <div className="border-t border-l border-line p-4 sm:border-t-0 sm:p-5"><span className="metric-label">Overall</span><FinancialValue value={portfolio.unrealized_pnl} change className="mt-2 block text-lg"/><div className="mt-1 text-sm"><PercentChange value={portfolio.overall_return_pct}/></div></div>
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="lg:col-span-2"><ChartCard eyebrow="Performance" title="Returns by horizon"><PortfolioHorizonChart portfolio={portfolio} activePeriod={range} onPeriodChange={setRange}/></ChartCard></div>
        <ChartCard eyebrow="Allocation" title="Where it is invested"><AllocationDonut portfolio={portfolio}/></ChartCard>
        <ChartCard eyebrow="Exposure" title="By sector"><SectorBars portfolio={portfolio}/></ChartCard>
        <div className="lg:col-span-2"><ChartCard eyebrow="Today’s contribution" title="What moved your money"><ContributionBars portfolio={portfolio}/></ChartCard></div>
      </div>
      <section className="product-card mt-4 px-5 py-4"><span className="section-kicker">Holdings</span><h2 className="section-title mt-1.5">Explore by asset type</h2><div className="mt-3"><HoldingsGroup title="Direct equities" holdings={equities} open/><HoldingsGroup title="Mutual funds" holdings={funds}/><HoldingsGroup title="Debt, gold and cash" holdings={defensive}/></div></section>
    </div>
  );
}
