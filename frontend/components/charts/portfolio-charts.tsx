"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PortfolioData } from "@/lib/product-types";

const colors = ["#185744", "#4d8972", "#83ad91", "#c3a35f", "#2f6ea4", "#8e6e9e"];

function tooltipStyle() {
  return { borderRadius: 14, border: "1px solid #e4e8e1", fontSize: 11 };
}

export function PortfolioHorizonChart({
  portfolio,
  activePeriod,
  onPeriodChange,
}: {
  portfolio: PortfolioData;
  activePeriod: "1D" | "1W" | "1M" | "3M" | "1Y";
  onPeriodChange: (period: "1D" | "1W" | "1M" | "3M" | "1Y") => void;
}) {
  const selected = portfolio.performance.find((point) => point.period === activePeriod);
  return (
    <figure aria-labelledby="portfolio-horizon-title">
      <figcaption id="portfolio-horizon-title" className="sr-only">Portfolio and Nifty 50 returns by investment horizon</figcaption>
      <div className="mb-4 grid grid-cols-5 rounded-xl bg-background p-1" aria-label="Return horizon">
        {portfolio.performance.map((point) => <button key={point.period} type="button" aria-pressed={activePeriod === point.period} onClick={() => onPeriodChange(point.period as typeof activePeriod)} className={`min-h-11 rounded-lg text-xs font-bold transition-colors ${activePeriod === point.period ? "bg-surface text-brand shadow-sm" : "text-muted hover:text-ink"}`}>{point.period}</button>)}
      </div>
      {selected && <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-xs"><span><strong className="text-ink">Portfolio</strong> <span className={selected.portfolio_return_pct < 0 ? "text-negative" : "text-positive"}>{selected.portfolio_return_pct > 0 ? "+" : ""}{selected.portfolio_return_pct.toFixed(2)}%</span></span><span><strong className="text-ink">{selected.benchmark_label ?? "Nifty 50"}</strong> <span className="text-muted">{selected.benchmark_return_pct === null ? "Unavailable" : `${selected.benchmark_return_pct > 0 ? "+" : ""}${selected.benchmark_return_pct.toFixed(2)}%`}</span></span></div>}
      <div className="h-56 w-full" role="img" aria-label="Grouped bars compare portfolio and benchmark returns for 1 day, 1 week, 1 month, 3 months, and 1 year">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={portfolio.performance} margin={{ top: 12, right: 8, left: -22, bottom: 0 }}>
            <CartesianGrid stroke="#e8ece6" vertical={false}/>
            <XAxis dataKey="period" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#657169" }}/>
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#657169" }} unit="%"/>
            <Tooltip contentStyle={tooltipStyle()} formatter={(value) => [`${Number(value).toFixed(2)}%`]}/>
            <Legend wrapperStyle={{ fontSize: 11 }}/>
            <Bar isAnimationActive={false} name="Portfolio" dataKey="portfolio_return_pct" fill="#185744" radius={[5, 5, 0, 0]}>{portfolio.performance.map((point) => <Cell key={`portfolio-${point.period}`} fill="#185744" fillOpacity={point.period === activePeriod ? 1 : .48}/>)}</Bar>
            <Bar isAnimationActive={false} name="Nifty 50" dataKey="benchmark_return_pct" fill="#9aa69e" radius={[5, 5, 0, 0]}>{portfolio.performance.map((point) => <Cell key={`benchmark-${point.period}`} fill="#9aa69e" fillOpacity={point.period === activePeriod ? .9 : .35}/>)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only"><caption>Return values by horizon</caption><thead><tr><th>Period</th><th>Portfolio</th><th>Benchmark</th></tr></thead><tbody>{portfolio.performance.map((point) => <tr key={point.period}><th>{point.period}</th><td>{point.portfolio_return_pct}%</td><td>{point.benchmark_return_pct === null ? "Unavailable" : `${point.benchmark_return_pct}%`}</td></tr>)}</tbody></table>
    </figure>
  );
}

export function AllocationDonut({ portfolio }: { portfolio: PortfolioData }) {
  return (
    <figure className="grid items-center gap-2 sm:grid-cols-[168px_1fr]" aria-label="Portfolio allocation by asset class">
      <div className="h-44 min-w-0 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie isAnimationActive={false} data={portfolio.asset_allocation} dataKey="portfolio_weight" nameKey="label" innerRadius={48} outerRadius={72} paddingAngle={2}>
              {portfolio.asset_allocation.map((item, index) => <Cell key={item.label} fill={colors[index % colors.length]}/>)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle()} formatter={(value) => [`${Number(value).toFixed(1)}%`]}/>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="grid gap-2">
        {portfolio.asset_allocation.map((item, index) => <div key={item.label} className="grid grid-cols-[10px_1fr_auto] items-center gap-2 text-xs"><i className="size-2.5 rounded-full" style={{ background: colors[index % colors.length] }}/><span className="text-muted">{item.label}</span><strong>{item.portfolio_weight.toFixed(1)}%</strong></div>)}
      </div>
    </figure>
  );
}

export function SectorBars({ portfolio }: { portfolio: PortfolioData }) {
  const data = portfolio.sector_exposure.slice(0, 7);
  return (
    <figure className="h-64" aria-label="Portfolio exposure by sector">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 22, left: 22, bottom: 0 }}>
          <CartesianGrid stroke="#eef1ed" horizontal={false}/>
          <XAxis type="number" hide/>
          <YAxis type="category" dataKey="sector" width={105} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#657169" }}/>
          <Tooltip contentStyle={tooltipStyle()} formatter={(value) => [`${Number(value).toFixed(1)}%`, "Exposure"]}/>
          <Bar isAnimationActive={false} dataKey="portfolio_weight" fill="#185744" radius={[0, 8, 8, 0]}/>
        </BarChart>
      </ResponsiveContainer>
      <ul className="sr-only">{data.map((item) => <li key={item.sector}>{item.sector}: {item.portfolio_weight.toFixed(1)}%</li>)}</ul>
    </figure>
  );
}

export function ContributionBars({ portfolio }: { portfolio: PortfolioData }) {
  const data = portfolio.largest_holdings
    .filter((item) => item.day_pnl !== null)
    .sort((a, b) => Math.abs(b.day_pnl ?? 0) - Math.abs(a.day_pnl ?? 0))
    .slice(0, 6);
  return (
    <figure className="h-56" aria-label="Holding contribution to today's portfolio movement">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 10, left: -8, bottom: 0 }}>
          <CartesianGrid stroke="#eef1ed" vertical={false}/>
          <XAxis dataKey="symbol" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#657169" }}/>
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: "#657169" }} tickFormatter={(value) => `₹${Number(value).toLocaleString("en-IN")}`}/>
          <Tooltip contentStyle={tooltipStyle()} formatter={(value) => [new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value)), "Contribution"]}/>
          <Bar isAnimationActive={false} dataKey="day_pnl" radius={[7, 7, 0, 0]}>{data.map((item) => <Cell key={item.symbol} fill={(item.day_pnl ?? 0) < 0 ? "#b84b45" : "#20725a"}/>)}</Bar>
        </BarChart>
      </ResponsiveContainer>
      <ul className="sr-only">{data.map((item) => <li key={item.symbol}>{item.symbol}: {item.day_pnl ?? 0} Indian rupees</li>)}</ul>
    </figure>
  );
}
