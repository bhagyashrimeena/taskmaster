import { ChevronRight, ExternalLink } from "lucide-react";

import type { CopilotMessage } from "@/stores/copilot-store";

const INTERNAL_LEAD = /^(?:based on (?:the )?(?:current )?(?:dashboard data|available data|portfolio data|financial-day context)(?: and (?:the )?system state)?|from the current dashboard data and system state)[^.!?]*[.!?]\s*/i;
const SECTION_HEADING = /^(why this matters|verified facts|the facts|portfolio impact|portfolio status|evidence|full research|research)\s*:?[\s]*$/i;

function cleanAnswer(value: string) {
  const withoutLead = value.trim().replace(/\r/g, "").replace(INTERNAL_LEAD, "");
  return withoutLead
    .replace(/^\s*(?:the facts|portfolio status)\s*[•:\-]\s*/i, "")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function conciseLead(answer: string) {
  const summaryText = answer
    .split("\n")
    .filter((line) => !SECTION_HEADING.test(line.trim()) && !line.trim().startsWith("•"))
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  const sentences = summaryText.match(/[^.!?]+(?:[.!?]+|$)/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [];
  const selected: string[] = [];
  for (const sentence of sentences) {
    if (selected.length === 6) break;
    if (selected.length >= 3 && selected.join(" ").length + sentence.length > 520) break;
    selected.push(sentence);
  }
  const joined = selected.join(" ");
  if (joined.length <= 560) return joined || answer.slice(0, 560);
  const clipped = joined.slice(0, 540).replace(/\s+\S*$/, "");
  return `${clipped}…`;
}

function headedSections(answer: string) {
  const lines = answer.split("\n");
  const sections: Array<{ label: string; text: string }> = [];
  let active: { label: string; lines: string[] } | null = null;
  const labels: Record<string, string> = {
    "why this matters": "Why this matters",
    "verified facts": "Verified facts",
    "the facts": "Verified facts",
    "portfolio impact": "Portfolio impact",
    "portfolio status": "Portfolio impact",
    evidence: "Verified facts",
    "full research": "Full research",
    research: "Full research",
  };

  for (const line of lines) {
    const heading = line.trim().match(SECTION_HEADING)?.[1]?.toLowerCase();
    if (heading) {
      if (active?.lines.join("\n").trim()) sections.push({ label: active.label, text: active.lines.join("\n").trim() });
      active = { label: labels[heading], lines: [] };
    } else if (active) {
      active.lines.push(line);
    }
  }
  if (active?.lines.join("\n").trim()) sections.push({ label: active.label, text: active.lines.join("\n").trim() });
  return sections;
}

function inferredSections(answer: string) {
  const bullets = answer.split("\n").filter((line) => line.trim().startsWith("•")).map((line) => line.trim());
  const sentences = (answer.match(/[^.!?]+(?:[.!?]+|$)/g) ?? []).map((sentence) => sentence.trim());
  const why = sentences
    .filter((sentence) => /because|worth|matters|relevant|attention/i.test(sentence))
    .slice(0, 2)
    .join(" ");
  const impact = sentences
    .filter((sentence) => /portfolio|holding|exposure|sector|allocation|%|₹/i.test(sentence))
    .slice(0, 3)
    .join(" ");
  return [
    why ? { label: "Why this matters", text: why } : null,
    bullets.length ? { label: "Verified facts", text: bullets.join("\n") } : null,
    impact ? { label: "Portfolio impact", text: impact } : null,
  ].filter((section): section is { label: string; text: string } => Boolean(section));
}

export function AssistantMessage({ message }: { message: CopilotMessage }) {
  const answer = cleanAnswer(message.text);
  const lead = conciseLead(answer);
  const sections = headedSections(answer);
  const disclosures = sections.length ? sections : inferredSections(answer);
  const showFullResponse = answer.length > lead.length + 80 && !sections.some((section) => section.label === "Full research");

  return (
    <div className="min-w-0">
      <p data-copilot-answer-lead className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{lead}</p>
      {(disclosures.length > 0 || message.sources.length > 0 || showFullResponse) && (
        <div className="mt-3 divide-y divide-line border-y border-line">
          {disclosures.map((section, index) => (
            <details className="group" key={`${section.label}-${index}`}>
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 py-2.5 text-sm font-semibold marker:content-none">
                {section.label}<ChevronRight size={15} className="shrink-0 text-muted transition-transform group-open:rotate-90" aria-hidden="true" />
              </summary>
              <p className="pb-3 whitespace-pre-wrap text-sm leading-6 text-muted">{section.text}</p>
            </details>
          ))}
          {message.sources.length > 0 && (
            <details className="group">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 py-2.5 text-sm font-semibold marker:content-none">
                Sources · {message.sources.length}<ChevronRight size={15} className="shrink-0 text-muted transition-transform group-open:rotate-90" aria-hidden="true" />
              </summary>
              <div className="grid gap-1 pb-3">
                {message.sources.map((source) => (
                  <a className="inline-flex min-h-11 items-center gap-2 rounded-lg text-sm font-semibold text-brand underline decoration-brand/30 underline-offset-4" href={source.canonical_url ?? source.url} target="_blank" rel="noreferrer" key={`${source.name}-${source.url}`}>
                    {source.name}<ExternalLink size={12} aria-hidden="true" />
                  </a>
                ))}
              </div>
            </details>
          )}
          {showFullResponse && (
            <details className="group">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 py-2.5 text-sm font-semibold marker:content-none">
                Full response<ChevronRight size={15} className="shrink-0 text-muted transition-transform group-open:rotate-90" aria-hidden="true" />
              </summary>
              <p className="pb-4 whitespace-pre-wrap text-sm leading-6 text-muted">{answer}</p>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
