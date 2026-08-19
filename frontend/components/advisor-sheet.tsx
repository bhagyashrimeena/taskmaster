"use client";

import {
  ArrowLeft,
  Check,
  CircleAlert,
  Clock3,
  ExternalLink,
  LoaderCircle,
  Mail,
  Send,
  ShieldCheck,
  UserRoundCheck,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  createAdvisorPacket,
  getAdvisorCase,
  getAdvisorProfile,
  markAdvisorPacketReady,
  sendAdvisorPacket,
} from "@/lib/api";
import type { AdvisorCase, AdvisorProfile } from "@/lib/types";

export interface AdvisorTarget {
  type: "story" | "event";
  id: string;
  title: string;
}

const defaultQuestion = "Does this development materially change your view of this holding, or is it something you would currently monitor?";

export function AdvisorSheet({ target, onClose }: { target: AdvisorTarget | null; onClose: () => void }) {
  const [profile, setProfile] = useState<AdvisorProfile | null>(null);
  const [advisorCase, setAdvisorCase] = useState<AdvisorCase | null>(null);
  const [question, setQuestion] = useState(defaultQuestion);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    void getAdvisorProfile().then(setProfile).catch(() => setError("Your advisor profile could not be loaded."));
  }, [target]);

  useEffect(() => {
    const requestId = advisorCase?.packet.request_id;
    if (!requestId || advisorCase.packet.status !== "SENT") return;
    const timer = window.setInterval(() => {
      void getAdvisorCase(requestId)
        .then((next) => {
          setAdvisorCase(next);
          if (next.packet.status === "REPLIED") window.clearInterval(timer);
        })
        .catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [advisorCase?.packet.request_id, advisorCase?.packet.status]);

  if (!target) return null;

  const prepare = async () => {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setAdvisorCase(await createAdvisorPacket({ target_type: target.type, target_id: target.id, user_question: question.trim() }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be prepared.");
    } finally {
      setBusy(false);
    }
  };

  const review = async () => {
    if (!advisorCase) return;
    setBusy(true);
    setError(null);
    try {
      setAdvisorCase(await markAdvisorPacketReady(advisorCase.packet.request_id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The email could not be opened for review.");
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    if (!advisorCase) return;
    setBusy(true);
    setError(null);
    try {
      const next = await sendAdvisorPacket(advisorCase.packet.request_id);
      setAdvisorCase(next);
      if (next.packet.send_error) setError(next.packet.send_error);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The advisor request could not be sent.");
    } finally {
      setBusy(false);
    }
  };

  const packet = advisorCase?.packet;
  const response = advisorCase?.response;
  const isReview = packet?.status === "READY";
  const isSent = packet?.status === "SENT";
  const isReplied = packet?.status === "REPLIED";

  return (
    <div className="advisor-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="advisor-sheet" role="dialog" aria-modal="true" aria-labelledby="advisor-title" data-testid="advisor-sheet">
        <header className="advisor-sheet__header">
          <div className="advisor-identity">
            <span><UserRoundCheck size={18} /></span>
            <div><small>Human expert handoff</small><strong id="advisor-title">Ask your advisor</strong></div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close advisor request"><X size={16} /></button>
        </header>

        <div className="advisor-sheet__body">
          <div className="advisor-target"><small>{target.type}</small><strong>{target.title}</strong></div>
          {profile && (
            <div className="advisor-profile">
              <span><UserRoundCheck size={16} /></span>
              <div><strong>{profile.name}</strong><small>{profile.firm} · {profile.email}</small></div>
              <em>{profile.provider === "demo" ? "Advisor preview" : "Connected email"}</em>
            </div>
          )}

          {!packet && (
            <section className="advisor-compose">
              <span className="eyebrow">Your question</span>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1200} aria-label="Question for advisor" />
              <div className="advisor-safety"><ShieldCheck size={15} /><p>Only relevant facts, portfolio exposure, sources, and your question will be shared. Nothing is sent yet.</p></div>
              <button className="primary-button advisor-primary" onClick={() => void prepare()} disabled={busy || !question.trim()} data-testid="prepare-advisor-packet">
                {busy ? <LoaderCircle className="spin" size={14} /> : <Mail size={14} />} Prepare request
              </button>
            </section>
          )}

          {packet?.status === "DRAFT" && (
            <section className="advisor-packet">
              <div className="advisor-step"><span>1</span><div><strong>Packet prepared</strong><small>Review what Wealth Copilot assembled from existing context.</small></div></div>
              <div className="advisor-context-card">
                <h3>What will be shared</h3>
                <p><strong>Exposure</strong>{packet.exposure}</p>
                <p><strong>Relevance</strong>{packet.relevance}</p>
                <p><strong>Your question</strong>{packet.user_question}</p>
              </div>
              <div className="advisor-columns">
                <section><h4>Facts</h4>{packet.facts.map((fact) => <p key={fact}><Check size={12} />{fact}</p>)}</section>
                <section><h4>Still unknown</h4>{packet.unknowns.map((unknown) => <p key={unknown}><CircleAlert size={12} />{unknown}</p>)}</section>
              </div>
              <button className="primary-button advisor-primary" onClick={() => void review()} disabled={busy} data-testid="review-advisor-email">
                {busy ? <LoaderCircle className="spin" size={14} /> : <Mail size={14} />} Review exact email
              </button>
            </section>
          )}

          {isReview && (
            <section className="advisor-review">
              <button className="advisor-back" onClick={() => setAdvisorCase({ ...advisorCase!, packet: { ...packet, status: "DRAFT" } })}><ArrowLeft size={13} /> Back to packet</button>
              <div className="advisor-step"><span>2</span><div><strong>Review before sending</strong><small>This is the exact recipient and message.</small></div></div>
              <div className="email-preview">
                <p><span>To</span><strong>{packet.email.to_name} &lt;{packet.email.to_email}&gt;</strong></p>
                <p><span>Subject</span><strong>{packet.email.subject}</strong></p>
                <pre>{packet.email.body}</pre>
              </div>
              <div className="advisor-source-list"><h4>Source links included</h4>{packet.sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>{source.name}<ExternalLink size={12} /></a>)}</div>
              <div className="advisor-confirm-note"><ShieldCheck size={15} /><span>Sending requires this separate confirmation. Wealth Copilot cannot send silently.</span></div>
              <button className="primary-button advisor-primary" onClick={() => void send()} disabled={busy} data-testid="confirm-send-advisor">
                {busy ? <LoaderCircle className="spin" size={14} /> : <Send size={14} />} Confirm &amp; send
              </button>
            </section>
          )}

          {isSent && (
            <section className="advisor-waiting">
              <span className="advisor-waiting__icon"><Clock3 size={22} /></span>
              <h3>Request sent to {packet.email.to_name}</h3>
              <p>The reviewed request is recorded in today&apos;s financial-day state. We&apos;ll attach the reply here when it arrives.</p>
              <div><LoaderCircle className="spin" size={13} /> Waiting for advisor response</div>
            </section>
          )}

          {isReplied && response && (
            <section className="advisor-reply" data-testid="advisor-reply">
              <div className="advisor-step"><span><Check size={13} /></span><div><strong>Advisor replied</strong><small>Linked to this {target.type} and saved in today&apos;s financial day.</small></div></div>
              <article>
                <header><div><span>{response.perspective_label}</span><strong>{response.advisor_name}</strong></div><time>{new Date(response.received_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</time></header>
                <p>{response.message}</p>
              </article>
              <small className="advisor-attribution">This is attributed human commentary. Wealth Copilot does not endorse or convert it into an investment instruction.</small>
            </section>
          )}

          {error && <div className="advisor-error" role="alert"><CircleAlert size={15} /><span>{error}</span></div>}
        </div>
      </aside>
    </div>
  );
}
