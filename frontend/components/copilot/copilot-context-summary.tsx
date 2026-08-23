import { BriefcaseBusiness, FileText, FolderOpen, ShieldCheck } from "lucide-react";

function metric(value: number | undefined) {
  return value === undefined ? "—" : value.toLocaleString("en-IN");
}

export function CopilotContextSummary({
  holdings,
  stories,
  cases,
}: {
  holdings?: number;
  stories?: number;
  cases?: number;
}) {
  const metrics = [
    { label: "Holdings", value: holdings, icon: BriefcaseBusiness },
    { label: "Relevant stories", value: stories, icon: FileText },
    { label: "Active cases", value: cases, icon: FolderOpen },
  ];
  return (
    <section className="copilot-context-card" aria-labelledby="copilot-context-heading">
      <div className="copilot-context-card__heading">
        <p id="copilot-context-heading" className="section-kicker">Today’s context</p>
        <span><ShieldCheck size={14} aria-hidden="true" /> The agent already has today’s context.</span>
      </div>
      <dl>
        {metrics.map(({ label, value, icon: Icon }) => (
          <div key={label}>
            <dt><span><Icon size={17} aria-hidden="true" /></span><span>{label}</span></dt>
            <dd>{metric(value)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
