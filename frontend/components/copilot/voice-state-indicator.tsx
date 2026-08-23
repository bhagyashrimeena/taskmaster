import { Sparkles } from "lucide-react";

import type { VoiceAgentState } from "@/hooks/use-voice-input";

const labels: Record<VoiceAgentState, string> = {
  idle: "Ready to talk",
  ready: "Ready to talk",
  listening: "I’m listening…",
  processing: "Checking your portfolio…",
  researching: "Researching sources…",
  speaking: "Speaking…",
  callConnecting: "Connecting to your wealth agent…",
  callActive: "Live call active",
  callEnded: "Call ended",
  callUnavailable: "Voice call unavailable",
  error: "Something went wrong. You can still type your question.",
};

export function VoiceStateIndicator({ state }: { state: VoiceAgentState }) {
  const animated = state === "listening" || state === "speaking";
  return (
    <div className="voice-state-indicator" aria-live="polite" aria-atomic="true">
      <span>{labels[state]}</span>
      <div className={`voice-waveform ${animated ? "voice-waveform--active" : ""}`} aria-hidden="true">
        {Array.from({ length: 20 }, (_, index) => <i key={index} style={{ animationDelay: `${(index % 6) * 70}ms` }} />)}
      </div>
      <Sparkles size={16} aria-hidden="true" />
    </div>
  );
}
