"use client";

import {
  ArrowUpRight,
  BookOpenText,
  Check,
  LoaderCircle,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Minus,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import { askTaskMaster, getResearch, recordFeedback, startResearch } from "@/lib/api";
import { readStoredThread, writeStoredThread } from "@/lib/chat-storage.js";
import type { ConversationResponse, InteractionMode } from "@/lib/types";

export interface CopilotTarget {
  type: "story" | "event" | "dashboard";
  id?: string;
  title: string;
}

export interface CopilotRequest {
  key: number;
  target: CopilotTarget;
  mode: InteractionMode;
  message?: string;
}

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "progress";
  text: string;
  response?: ConversationResponse;
  status?: "working" | "error";
};

function targetFields(target: CopilotTarget) {
  return {
    active_story_id: target.type === "story" ? target.id : undefined,
    active_event_id: target.type === "event" ? target.id : undefined,
  };
}

function messageId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function storedMessages(): ChatMessage[] {
  return (readStoredThread()?.messages ?? []).map((message, index) => ({
    id: `${message.role}-${index}`,
    role: message.role === "assistant" ? "assistant" : message.role === "progress" ? "progress" : "user",
    text: message.text,
    response: "response" in message ? message.response as ConversationResponse : undefined,
    status: "status" in message ? message.status as ChatMessage["status"] : undefined,
  }));
}

function sourceKey(source: ConversationResponse["sources"][number]) {
  return source.canonical_url || source.url || source.name;
}

function uniqueSources(response: ConversationResponse) {
  const seen = new Set<string>();
  return response.sources.filter((source) => {
    const key = sourceKey(source);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function CopilotSheet({ request, onClose }: { request: CopilotRequest | null; onClose: () => void }) {
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [isMinimized, setIsMinimized] = useState(false);
  const [showNewResponse, setShowNewResponse] = useState(false);
  const handledKey = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const minimizedRef = useRef(false);
  const operationRef = useRef(0);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const nearBottomRef = useRef(true);
  const messagesRef = useRef<ChatMessage[]>([]);
  const latestResponse = [...messages].reverse().find((item) => item.role === "assistant")?.response ?? null;

  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  useEffect(() => {
    const body = document.body.style;
    const html = document.documentElement.style;
    const previous = {
      bodyOverflow: body.overflow,
      bodyTouchAction: body.touchAction,
      bodyOverscrollBehavior: body.overscrollBehavior,
      htmlOverflow: html.overflow,
      htmlTouchAction: html.touchAction,
      htmlOverscrollBehavior: html.overscrollBehavior,
    };
    body.overflow = "hidden";
    body.touchAction = "none";
    body.overscrollBehavior = "none";
    html.overflow = "hidden";
    html.touchAction = "none";
    html.overscrollBehavior = "none";
    return () => {
      body.overflow = previous.bodyOverflow;
      body.touchAction = previous.bodyTouchAction;
      body.overscrollBehavior = previous.bodyOverscrollBehavior;
      html.overflow = previous.htmlOverflow;
      html.touchAction = previous.htmlTouchAction;
      html.overscrollBehavior = previous.htmlOverscrollBehavior;
    };
  }, []);

  useEffect(() => {
    window.queueMicrotask(() => {
      const stored = readStoredThread();
      if (!stored) return;
      setConversationId(stored.conversation_id);
      const restored = storedMessages();
      messagesRef.current = restored;
      setMessages(restored);
      if (stored.unread_count) writeStoredThread({ ...stored, unread_count: 0 });
    });
  }, []);

  const persist = (nextMessages: ChatMessage[], target: CopilotTarget, response?: ConversationResponse, unread = false) => {
    const stored = readStoredThread();
    writeStoredThread({
      conversation_id: response?.conversation_id ?? conversationId,
      target,
      title: target.title,
      messages: nextMessages,
      latest_response: response ?? stored?.latest_response,
      unread_count: unread ? 1 : 0,
      updated_at: new Date().toISOString(),
    });
  };

  const replaceMessage = (id: string, replacement: ChatMessage) => {
    messagesRef.current = messagesRef.current.map((item) => item.id === id ? replacement : item);
    setMessages(messagesRef.current);
  };

  const scrollToLatest = () => {
    const body = bodyRef.current;
    if (!body) return;
    body.scrollTo({ top: body.scrollHeight, behavior: "smooth" });
    nearBottomRef.current = true;
    setShowNewResponse(false);
  };

  useEffect(() => {
    if (nearBottomRef.current) scrollToLatest();
    else setShowNewResponse(true);
  }, [messages]);

  const minimize = () => {
    minimizedRef.current = true;
    setIsMinimized(true);
  };

  const restore = () => {
    minimizedRef.current = false;
    setIsMinimized(false);
  };

  const submitMessage = async (message: string, mode: InteractionMode = "chat", target = request?.target) => {
    if (!target) return;
    const operationId = operationRef.current + 1;
    operationRef.current = operationId;
    const userMessage: ChatMessage = { id: messageId("user"), role: "user", text: message };
    const progressMessage: ChatMessage = {
      id: messageId("progress"),
      role: "progress",
      text: mode === "research" ? "Research Agent\nSearching current sources..." : "TaskMaster\nChecking the event and your portfolio context...",
      status: "working",
    };
    const nextMessages = [...messagesRef.current, userMessage, progressMessage];
    messagesRef.current = nextMessages;
    setMessages(nextMessages);
    setLoading(true);
    setFeedback(null);
    persist(nextMessages, target);

    try {
      if (mode === "research") {
        const job = await startResearch({ conversation_id: conversationId, message, ...targetFields(target) });
        for (let attempt = 0; attempt < 70; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
          const current = await getResearch(job.job_id);
          if (operationRef.current !== operationId) return;
          replaceMessage(progressMessage.id, { ...progressMessage, text: `Research Agent\n${current.message}` });
          if (["complete", "fallback"].includes(current.status) && current.result) {
            const assistant: ChatMessage = { id: current.result.message_id, role: "assistant", text: current.result.answer, response: current.result };
            replaceMessage(progressMessage.id, assistant);
            setConversationId(current.result.conversation_id);
            const finished = nextMessages.map((item) => item.id === progressMessage.id ? assistant : item);
            persist(finished, target, current.result, !mountedRef.current || minimizedRef.current);
            return;
          }
          if (current.status === "failed") throw new Error(current.message);
        }
        throw new Error("The research pass is taking longer than expected, but your dashboard context remains available.");
      }

      const response = await askTaskMaster({ conversation_id: conversationId, message, mode, ...targetFields(target) });
      if (operationRef.current !== operationId) return;
      const assistant: ChatMessage = { id: response.message_id, role: "assistant", text: response.answer, response };
      replaceMessage(progressMessage.id, assistant);
      setConversationId(response.conversation_id);
      const finished = nextMessages.map((item) => item.id === progressMessage.id ? assistant : item);
      persist(finished, target, response, !mountedRef.current || minimizedRef.current);
    } catch (caught) {
      if (operationRef.current !== operationId) return;
      const errorMessage: ChatMessage = {
        id: messageId("error"),
        role: "progress",
        text: caught instanceof Error ? caught.message : "Wealth Copilot is temporarily unavailable.",
        status: "error",
      };
      replaceMessage(progressMessage.id, errorMessage);
      const failed = nextMessages.map((item) => item.id === progressMessage.id ? errorMessage : item);
      persist(failed, target, undefined, !mountedRef.current || minimizedRef.current);
    } finally {
      if (operationRef.current === operationId) setLoading(false);
    }
  };

  useEffect(() => {
    if (!request || handledKey.current === request.key) return;
    handledKey.current = request.key;
    window.queueMicrotask(() => {
      if (request.message) void submitMessage(request.message, request.mode, request.target);
    });
    // request.key intentionally represents a new interaction.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.key]);

  useEffect(() => {
    if (!request) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, request]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const message = question.trim();
    if (!message || loading) return;
    setQuestion("");
    void submitMessage(message);
  };

  const sendFeedback = async (value: "useful" | "not_relevant") => {
    if (!request || !latestResponse) return;
    await recordFeedback({
      target_type: request.target.type === "dashboard" ? "conversation" : request.target.type,
      target_id: request.target.id || latestResponse.message_id,
      value,
      conversation_id: latestResponse.conversation_id,
    });
    setFeedback(value);
  };

  const renderAssistant = (message: ChatMessage) => {
    const response = message.response;
    if (!response) return <p>{message.text}</p>;
    const answer = response.answer.length > 900 ? `${response.answer.slice(0, 900).trimEnd()}…` : response.answer;
    const remainder = response.answer.length > 900 ? response.answer.slice(900).trim() : "";
    const sources = uniqueSources(response);
    return (
      <>
        <p>{answer}</p>
        {remainder && <details className="answer-details"><summary>Full answer</summary><p>{remainder}</p></details>}
        <details className="copilot-details"><summary>Verified facts</summary><section className="evidence-panel">{response.context.facts.map((fact) => <p key={fact}><Check size={13} />{fact}</p>)}</section></details>
        <details className="copilot-details"><summary>Why this matters to you</summary><section className="evidence-panel"><p>{response.context.interpretation.join(" ")}</p></section></details>
        {!!response.context.unknowns.length && <details className="copilot-details"><summary>What remains uncertain</summary><section className="evidence-panel"><p>{response.context.unknowns.join(" ")}</p></section></details>}
        {!!sources.length && <details className="copilot-details"><summary>Sources · {sources.length}</summary><section className="source-list">{sources.map((source) => source.canonical_url ? <a href={source.canonical_url} target="_blank" rel="noreferrer" key={sourceKey(source)}><div><strong>{source.title || source.name}</strong><span>{source.publisher || source.authority.replaceAll("_", " ")}</span></div><ArrowUpRight size={14} /></a> : <div className="source-list__unavailable" key={sourceKey(source)}><div><strong>{source.title || source.name}</strong><span>{source.publisher || source.authority.replaceAll("_", " ")} · source link unavailable</span></div></div>)}</section></details>}
      </>
    );
  };

  if (!request) return null;
  const titleText = request.target.title || "Wealth Copilot";

  if (isMinimized) {
    return (
      <div className="copilot-dock" role="dialog" aria-label="Wealth Copilot">
        <aside className="copilot-sheet copilot-sheet--minimized" data-testid="copilot-sheet">
          <div className="copilot-sheet__header"><div className="copilot-sheet__identity"><span className="brand-mark"><Sparkles size={16} /></span><div><span className="eyebrow">Wealth Copilot</span><strong>{loading ? "Working alongside you" : titleText}</strong></div></div><div className="copilot-sheet__tools"><button className="icon-button" aria-label="Restore Wealth Copilot" onClick={restore}><Sparkles size={15} /></button><button className="icon-button" aria-label="Close Wealth Copilot" onClick={onClose}><X size={17} /></button></div></div>
        </aside>
      </div>
    );
  }

  return (
    <div className="copilot-dock" role="presentation">
      <aside className="copilot-sheet" role="dialog" aria-labelledby="copilot-title" data-testid="copilot-sheet">
        <div className="copilot-sheet__header"><div className="copilot-sheet__identity"><span className="brand-mark"><Sparkles size={16} /></span><div><span className="eyebrow">Wealth Copilot</span><strong id="copilot-title">{titleText}</strong></div></div><div className="copilot-sheet__tools"><button className="icon-button" aria-label="Minimize Wealth Copilot" title="Minimize" onClick={minimize}><Minus size={17} /></button><button className="icon-button" aria-label="Close Wealth Copilot" onClick={onClose}><X size={17} /></button></div></div>
        <div className="copilot-sheet__body" ref={bodyRef} onScroll={(event) => { const element = event.currentTarget; nearBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80; if (nearBottomRef.current) setShowNewResponse(false); }}>
          <div className="copilot-thread">
            {messages.length === 0 && <div className="copilot-empty"><Sparkles size={22} /><p>Ask about your portfolio, a story, or what deserves attention.</p></div>}
            {messages.map((message) => message.role === "user" ? (
              <article className="chat-message chat-message--user" key={message.id}><span className="chat-message__author">You</span><p>{message.text}</p></article>
            ) : message.role === "progress" ? (
              <article className={`chat-message chat-message--progress ${message.status === "error" ? "is-error" : ""}`} key={message.id}><span className="chat-message__author">{message.status === "error" ? "Wealth Copilot" : message.text.split("\n")[0]}</span><p>{message.text.split("\n").slice(1).join("\n") || message.text}</p>{message.status !== "error" && <LoaderCircle className="spin" size={14} />}</article>
            ) : (
              <article className="chat-message chat-message--assistant" key={message.id}><span className="chat-message__author"><Sparkles size={13} /> Wealth Copilot <small>{message.response?.route?.replaceAll("_", " ")}</small></span>{renderAssistant(message)}{message.response && <div className="response-actions"><button className="secondary-button" onClick={() => void submitMessage("Research this more deeply.", "research")} disabled={loading}><BookOpenText size={15} /> Research deeper</button><span>Was this useful?</span><button className={`feedback-button ${feedback === "useful" ? "is-active" : ""}`} aria-label="Useful" onClick={() => void sendFeedback("useful")}><ThumbsUp size={14} /></button><button className={`feedback-button ${feedback === "not_relevant" ? "is-active" : ""}`} aria-label="Not relevant" onClick={() => void sendFeedback("not_relevant")}><ThumbsDown size={14} /></button></div>}</article>
            ))}
          </div>
          {showNewResponse && <button className="copilot-new-response" onClick={scrollToLatest}>↓ New response</button>}
        </div>
        <form className="copilot-composer" onSubmit={submit}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={loading ? "Waiting for current response…" : "Ask a follow-up…"} aria-label="Ask a follow-up" /><button type="submit" aria-label="Send question" disabled={!question.trim() || loading}><Send size={16} /></button></form>
        <p className="copilot-boundary">We explain relevance and evidence. You remain in control of every financial decision.</p>
      </aside>
    </div>
  );
}
