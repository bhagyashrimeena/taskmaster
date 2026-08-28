"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Bot, LoaderCircle, MessageCircle, Mic, MoreHorizontal, Phone, Search, Send, Square, Trash2 } from "lucide-react";

import { AssistantMessage } from "@/components/copilot/assistant-message";
import { CopilotAgentCard } from "@/components/copilot/copilot-agent-card";
import { CopilotContextSummary } from "@/components/copilot/copilot-context-summary";
import { CopilotSuggestedPrompts } from "@/components/copilot/copilot-suggested-prompts";
import { useLiveKitSession } from "@/hooks/use-livekit-session";
import { useCopilotBootstrap } from "@/hooks/use-product-queries";
import { useVoiceInput, type VoiceAgentState } from "@/hooks/use-voice-input";
import type { InteractionMode } from "@/lib/types";
import { useCopilotStore } from "@/stores/copilot-store";

const defaultSuggestions = [
  "Why does the latest alert matter?",
  "What deserves my attention right now?",
  "Summarize my biggest exposures",
  "What changed since morning?",
];

type ComposerMode = "text" | "voice" | "call" | "research";

const subscribeToHydration = () => () => undefined;

export function CopilotView() {
  const [draft, setDraft] = useState("");
  const [composerMode, setComposerMode] = useState<ComposerMode>("text");
  const [agentState, setAgentState] = useState<VoiceAgentState>("idle");
  const hydrated = useSyncExternalStore(subscribeToHydration, () => true, () => false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const previousMessageCount = useRef(0);
  const conversationId = useCopilotStore((state) => state.conversationId);
  const messages = useCopilotStore((state) => state.messages);
  const pending = useCopilotStore((state) => state.pending);
  const error = useCopilotStore((state) => state.error);
  const send = useCopilotStore((state) => state.send);
  const adoptConversation = useCopilotStore((state) => state.adoptConversation);
  const appendCallTranscript = useCopilotStore((state) => state.appendCallTranscript);
  const clear = useCopilotStore((state) => state.clear);
  const bootstrap = useCopilotBootstrap(conversationId);
  const empty = messages.length === 0;
  const suggestions = bootstrap.data?.suggested_questions.length ? bootstrap.data.suggested_questions : defaultSuggestions;
  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const followUps = latestAssistant?.suggestedQuestions?.length
    ? latestAssistant.suggestedQuestions.slice(0, 2)
    : bootstrap.data?.active_case_count
      ? ["Why does this alert matter?", "Research this event deeper"]
      : ["What should I monitor today?", "Summarize my portfolio health"];

  const handleTranscript = useCallback((transcript: string) => {
    setDraft(transcript);
    setComposerMode("voice");
  }, []);
  const handleCallTranscript = useCallback((message: { id: string; role: "user" | "assistant"; text: string }) => {
    appendCallTranscript({ ...message, sources: [], suggestedQuestions: [], mode: "call" });
  }, [appendCallTranscript]);
  const voice = useVoiceInput({ onTranscript: handleTranscript, onStateChange: setAgentState });
  const call = useLiveKitSession({
    conversationId,
    enabled: Boolean(bootstrap.data?.voice_call_enabled),
    onStateChange: setAgentState,
    onConversationId: adoptConversation,
    onTranscript: handleCallTranscript,
  });

  useEffect(() => {
    if (messages.length > previousMessageCount.current && previousMessageCount.current > 0) {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      endRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "end" });
    }
    previousMessageCount.current = messages.length;
  }, [messages.length]);

  const resetComposerHeight = () => {
    if (textareaRef.current) textareaRef.current.style.height = "44px";
  };

  const sendAgentMessage = async (message: string, mode: InteractionMode = composerMode) => {
    const trimmed = message.trim();
    if (!trimmed || pending) return;
    setAgentState(mode === "research" ? "researching" : "processing");
    await send(trimmed, mode);
    const failed = Boolean(useCopilotStore.getState().error);
    setAgentState(failed ? "error" : call.active ? "callActive" : voice.supported ? "ready" : "idle");
  };

  const submitMessage = () => {
    const message = draft.trim();
    if (!message || pending) return;
    setDraft("");
    resetComposerHeight();
    void sendAgentMessage(message);
    setComposerMode("text");
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    submitMessage();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage();
    }
  };

  const resizeComposer = (value: string) => {
    setDraft(value);
    if (composerMode === "voice") setComposerMode("text");
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "44px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
  };

  const chooseMode = (mode: ComposerMode) => {
    setComposerMode(mode);
    if (mode === "voice") voice.start();
    else if (mode === "call") void call.start();
    else textareaRef.current?.focus();
  };

  const statusMessages = [
    voice.message,
    call.message,
    !voice.supported ? "Voice input is not available in this browser. You can still type your question." : null,
    !bootstrap.data?.voice_call_enabled ? bootstrap.data?.voice_call_reason ?? null : null,
  ].filter((message): message is string => Boolean(message));

  return (
    <div className="copilot-page mx-auto w-full max-w-5xl">
      <header className="copilot-page-hero">
        <div>
          <p className="section-kicker">Copilot</p>
          <h1>Talk to your wealth agent</h1>
          <p>Your AI agent monitors your portfolio, explains what changed, and guides what matters today.</p>
        </div>
        <div className="copilot-hero-orb" aria-hidden="true"><Bot size={33} /></div>
      </header>

      <CopilotAgentCard
        state={pending && agentState !== "researching" ? "processing" : agentState}
        voiceSupported={voice.supported}
        listening={voice.listening}
        callEnabled={Boolean(bootstrap.data?.voice_call_enabled)}
        callActive={call.active}
        callConnecting={call.connecting}
        callMuted={call.muted}
        statusMessages={statusMessages}
        onStartVoice={voice.start}
        onStopVoice={voice.stop}
        onCancelVoice={voice.cancel}
        onStartCall={() => void call.start()}
        onEndCall={() => void call.end()}
        onToggleMute={() => void call.toggleMute()}
      />

      <div className="copilot-context-block mt-5 grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <CopilotSuggestedPrompts prompts={empty ? suggestions : followUps} pending={pending} onSelect={(prompt) => void sendAgentMessage(prompt, prompt.toLowerCase().includes("research") ? "research" : "text")} />
        <CopilotContextSummary
          holdings={bootstrap.data?.holdings_count}
          stories={bootstrap.data?.relevant_story_count}
          cases={bootstrap.data?.active_case_count}
          scenarios={bootstrap.data?.likely_scenario_count}
          watchEvents={bootstrap.data?.watch_event_count}
        />
      </div>

      <nav className="copilot-mode-switch" aria-label="Copilot interaction mode">
        {([
          ["text", "Ask", MessageCircle],
          ["voice", "Voice", Mic],
          ["call", "Call", Phone],
          ["research", "Research", Search],
        ] as const).map(([mode, label, Icon]) => (
          <button type="button" key={mode} className={composerMode === mode ? "is-active" : ""} onClick={() => chooseMode(mode)} aria-pressed={composerMode === mode} disabled={mode === "call" && !bootstrap.data?.voice_call_enabled}>
            <Icon size={16} aria-hidden="true" /> {label}
          </button>
        ))}
      </nav>

      {!empty && (
        <section className="copilot-conversation product-card mt-4" aria-label="Wealth Copilot conversation">
          <header className="flex min-h-14 items-center justify-between gap-3 border-b border-line px-4 py-2">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand"><Bot size={16} aria-hidden="true" /></span>
              <div className="min-w-0"><strong className="block text-sm font-semibold">Your conversation</strong><span className="block text-[10px] text-muted">Same portfolio context across text and voice</span></div>
            </div>
            <details className="relative">
              <summary className="grid size-11 cursor-pointer list-none place-items-center rounded-xl text-muted hover:bg-background marker:content-none" aria-label="Conversation actions"><MoreHorizontal size={18} aria-hidden="true" /></summary>
              <div className="absolute top-12 right-0 z-20 w-48 rounded-xl border border-line bg-surface p-1.5 shadow-xl">
                <button className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-left text-xs font-semibold text-negative hover:bg-negative/5" onClick={clear} type="button"><Trash2 size={14} aria-hidden="true" /> Clear conversation</button>
              </div>
            </details>
          </header>
          <div className="copilot-message-timeline px-4 py-5" role="log" aria-live="polite" aria-relevant="additions text">
            <div className="grid gap-6">
              {messages.map((message) => message.role === "user" ? (
                <article className="ml-auto max-w-[86%]" key={message.id} aria-label="You"><span className="mb-1 block text-right text-[10px] font-bold tracking-wider text-muted uppercase">You</span><p className="rounded-2xl rounded-tr-md bg-brand px-4 py-3 text-sm leading-6 text-white">{message.text}</p></article>
              ) : (
                <article className="grid min-w-0 grid-cols-[32px_1fr] gap-3" key={message.id} aria-label="Wealth Copilot"><span className="grid size-8 place-items-center rounded-xl bg-brand-soft text-brand"><Bot size={15} aria-hidden="true" /></span><div className="min-w-0"><span className="mb-1.5 block text-[10px] font-bold tracking-wider text-brand uppercase">Wealth Copilot</span><AssistantMessage message={message} /></div></article>
              ))}
            </div>
            {pending && <div className="mt-5 flex items-center gap-3 text-xs text-muted" role="status"><LoaderCircle className="animate-spin text-brand" size={17} aria-hidden="true" />{agentState === "researching" ? "Researching verified sources…" : "Checking your portfolio and today’s context…"}</div>}
            {error && <p className="mt-4 rounded-xl bg-monitor/10 px-3 py-2 text-xs text-monitor" role="alert">{error} Your draft and previous messages are still here.</p>}
            <div ref={endRef} aria-hidden="true" />
          </div>
        </section>
      )}

      {bootstrap.isError && <p className="mt-4 rounded-xl border border-monitor/20 bg-monitor/5 px-4 py-3 text-xs text-monitor" role="status">Today’s context is reconnecting. Your current conversation remains available.</p>}

      <div className="copilot-composer-dock">
        {!empty && <div className="mb-2 flex gap-2 overflow-x-auto pb-0.5" aria-label="Suggested follow-ups">{followUps.map((question) => <button className="min-h-11 shrink-0 rounded-full border border-line bg-surface px-3 text-xs font-semibold text-brand shadow-sm disabled:opacity-50" key={question} onClick={() => void sendAgentMessage(question, question.toLowerCase().includes("research") ? "research" : "text")} disabled={pending} type="button">{question}</button>)}</div>}
        <form className="grid grid-cols-[1fr_44px_44px] items-end gap-1.5 rounded-2xl border border-line bg-surface p-2 shadow-[0_12px_35px_rgba(18,39,30,.16)]" onSubmit={submit}>
          <textarea ref={textareaRef} rows={1} className="copilot-composer-textarea min-h-11 max-h-[120px] min-w-0 resize-none rounded-xl bg-background px-3 py-3 text-sm leading-5 outline-none placeholder:text-muted/75 focus:bg-surface" value={draft} onChange={(event) => resizeComposer(event.target.value)} onKeyDown={handleKeyDown} placeholder={composerMode === "research" ? "Research with Wealth Copilot…" : "Ask Wealth Copilot…"} aria-label="Ask Wealth Copilot" />
          <button className={`grid size-11 place-items-center rounded-xl text-muted ${voice.listening ? "bg-negative/10 text-negative" : ""}`} type="button" onClick={voice.listening ? voice.stop : voice.start} disabled={!hydrated || !voice.supported || pending || call.active} aria-label={voice.listening ? "Stop voice input" : "Start voice input"} title={voice.supported ? "Use voice input" : "Voice input is not available in this browser"}>{voice.listening ? <Square size={15} aria-hidden="true" /> : <Mic size={17} aria-hidden="true" />}</button>
          <button className="grid size-11 place-items-center rounded-xl bg-brand text-white disabled:cursor-not-allowed disabled:opacity-40" type="button" onClick={submitMessage} disabled={!hydrated || !draft.trim() || pending} aria-label="Send"><Send size={17} aria-hidden="true" /></button>
        </form>
      </div>
    </div>
  );
}
