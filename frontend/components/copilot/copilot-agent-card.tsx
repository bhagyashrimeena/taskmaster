import { Mic, MicOff, Phone, PhoneOff, Sparkles, Volume2 } from "lucide-react";
import type { KeyboardEvent, PointerEvent } from "react";

import { VoiceStateIndicator } from "@/components/copilot/voice-state-indicator";
import type { VoiceAgentState } from "@/hooks/use-voice-input";

interface CopilotAgentCardProps {
  state: VoiceAgentState;
  voiceSupported: boolean;
  listening: boolean;
  callEnabled: boolean;
  callActive: boolean;
  callConnecting: boolean;
  callMuted: boolean;
  statusMessages: string[];
  onStartVoice: () => void;
  onStopVoice: () => void;
  onCancelVoice: () => void;
  onStartCall: () => void;
  onEndCall: () => void;
  onToggleMute: () => void;
}

export function CopilotAgentCard(props: CopilotAgentCardProps) {
  const badgeLabel = props.callActive ? "ON CALL" : props.callConnecting ? "CONNECTING" : props.callEnabled ? "CALL AVAILABLE" : "TEXT READY";
  const callLabel = props.callConnecting ? "Connecting..." : props.callEnabled ? "Live call" : "Call setup needed";
  const callDetail = props.callEnabled ? "Talk to the agent now" : "LiveKit is not configured";

  const holdStart = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    props.onStartVoice();
  };

  const holdEnd = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    props.onStopVoice();
  };

  const keyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      props.onStartVoice();
    }
  };

  const keyUp = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      props.onStopVoice();
    }
  };

  return (
    <section className="copilot-agent-card" aria-labelledby="agent-card-title">
      <header className="copilot-agent-card__header">
        <span className="copilot-agent-card__avatar"><Sparkles size={26} aria-hidden="true" /></span>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="agent-card-title">Wealth Copilot</h2>
            <span className={`copilot-live-badge ${props.callActive || props.callConnecting ? "is-live" : ""}`}>
              <i /> {badgeLabel}
            </span>
          </div>
          <p>Voice draft or live call — same Copilot brain</p>
        </div>
        <span className="copilot-agent-card__signal"><Volume2 size={19} aria-hidden="true" /></span>
      </header>

      <div className="copilot-agent-card__voice">
        <VoiceStateIndicator state={props.state} />
        <button
          className={`copilot-agent-card__mic ${props.listening ? "is-listening" : ""}`}
          type="button"
          onClick={props.listening ? props.onStopVoice : props.onStartVoice}
          disabled={!props.voiceSupported || props.callActive}
          aria-label={props.listening ? "Stop voice input" : "Start voice input"}
          aria-pressed={props.listening}
        >
          {props.listening ? <MicOff size={21} aria-hidden="true" /> : <Mic size={21} aria-hidden="true" />}
        </button>
      </div>

      {props.callActive ? (
        <div className="copilot-agent-card__actions">
          <button className="is-primary" type="button" onClick={props.onToggleMute} aria-label={props.callMuted ? "Unmute call" : "Mute call"}>
            {props.callMuted ? <MicOff size={19} aria-hidden="true" /> : <Mic size={19} aria-hidden="true" />}
            <span className="copilot-agent-card__button-copy"><strong>{props.callMuted ? "Unmute" : "Mute"}</strong><small>Live call audio</small></span>
          </button>
          <button type="button" onClick={props.onEndCall} aria-label="End call">
            <PhoneOff size={19} aria-hidden="true" />
            <span className="copilot-agent-card__button-copy"><strong>End call</strong><small>Return to text</small></span>
          </button>
        </div>
      ) : (
        <div className="copilot-agent-card__actions">
          <button className="is-primary" type="button" onClick={props.onStartCall} disabled={!props.callEnabled || props.callConnecting} aria-label="Call your wealth agent" title={props.callEnabled ? "Start a secure voice call" : "Live call is not configured yet"}>
            <Phone size={19} aria-hidden="true" />
            <span className="copilot-agent-card__button-copy"><strong>{callLabel}</strong><small>{callDetail}</small></span>
          </button>
          <button
            type="button"
            disabled={!props.voiceSupported || props.callConnecting}
            onPointerDown={holdStart}
            onPointerUp={holdEnd}
            onPointerCancel={props.onCancelVoice}
            onKeyDown={keyDown}
            onKeyUp={keyUp}
            aria-label="Hold to dictate a prompt"
          >
            <Mic size={18} aria-hidden="true" />
            <span className="copilot-agent-card__button-copy"><strong>Voice draft</strong><small>Hold, then review</small></span>
          </button>
        </div>
      )}

      <div className="copilot-agent-card__mode-note" aria-label="Voice and call behavior">
        <span><Mic size={13} aria-hidden="true" /> Voice draft fills the box</span>
        <span><Phone size={13} aria-hidden="true" /> Live call starts after connect</span>
      </div>

      <div className="copilot-agent-card__trust">
        <span><i /> Uses today&apos;s portfolio context</span>
        <span>Secure &amp; private</span>
      </div>
      <p className="copilot-agent-card__boundary">Score calculated by rules. Explanation generated by AI. You decide.</p>
      {props.statusMessages.length > 0 && (
        <div className="copilot-agent-card__notices" role="status" aria-live="polite">
          {props.statusMessages.map((message) => <p className="copilot-agent-card__notice" key={message}>{message}</p>)}
        </div>
      )}
    </section>
  );
}
