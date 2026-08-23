import { ArrowUpRight, BellRing, ChartNoAxesCombined, Crosshair, PieChart } from "lucide-react";

const icons = [BellRing, Crosshair, PieChart, ChartNoAxesCombined];

export function CopilotSuggestedPrompts({
  prompts,
  pending,
  onSelect,
}: {
  prompts: string[];
  pending: boolean;
  onSelect: (prompt: string) => void;
}) {
  return (
    <section aria-labelledby="copilot-prompts-heading">
      <p id="copilot-prompts-heading" className="section-kicker">Suggested prompts</p>
      <div className="copilot-prompt-grid" aria-label="Suggested prompts">
        {prompts.slice(0, 4).map((prompt, index) => {
          const Icon = icons[index % icons.length];
          return (
            <button type="button" key={prompt} onClick={() => onSelect(prompt)} disabled={pending}>
              <span><Icon size={17} aria-hidden="true" /></span>
              <strong>{prompt}</strong>
              <ArrowUpRight size={16} aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </section>
  );
}
