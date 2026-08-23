"use client";

import { BookOpenText, Headphones, LoaderCircle, Pause, Play, Volume2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { audioFileUrl, generateAudioBrief, getAudioBrief, getAudioStatus } from "@/lib/api";
import type { AudioBrief, AudioBriefType } from "@/lib/types";


function durationLabel(brief: AudioBrief | null) {
  const seconds = brief?.actual_duration_seconds || brief?.estimated_duration_seconds || 60;
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const minutes = Math.max(1, Math.round(seconds / 60));
  return `${minutes} min`;
}


export function AudioBriefControl({ type, compact = false }: { type: AudioBriefType; compact?: boolean }) {
  const [brief, setBrief] = useState<AudioBrief | null>(null);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await getAudioBrief(type);
      setBrief(next);
      setError(next.status === "fallback" ? next.message : null);
    } catch {
      setError("Audio is unavailable right now");
    }
  }, [type]);

  useEffect(() => { window.queueMicrotask(() => void load()); }, [load]);

  useEffect(() => {
    if (!brief || !["queued", "generating"].includes(brief.status)) return;
    const timer = window.setInterval(() => {
      void getAudioStatus(brief.brief_id).then((next) => {
        setBrief(next);
        if (["ready", "fallback"].includes(next.status)) {
          setBusy(false);
          setError(next.status === "fallback" ? next.message : null);
        }
      }).catch(() => setBusy(false));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [brief]);

  const listen = async () => {
    if (brief?.status === "ready" && audioRef.current) {
      if (playing) audioRef.current.pause();
      else await audioRef.current.play();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await generateAudioBrief(type);
      setBrief(response.brief);
      if (response.brief.status === "ready") setBusy(false);
    } catch {
      setBusy(false);
      setError("Audio could not be prepared. Try the written brief instead.");
      setTranscriptOpen(true);
    }
  };

  const isGenerating = busy || brief?.status === "queued" || brief?.status === "generating";
  const label = isGenerating
    ? "Preparing audio"
    : playing
    ? "Pause"
    : brief?.status === "ready"
    ? `Play · ${durationLabel(brief)}`
    : brief?.status === "fallback"
    ? `Retry Gemini · ${durationLabel(brief)}`
    : `Listen · ${durationLabel(brief)}`;

  return (
    <div className={`audio-brief-control ${compact ? "audio-brief-control--compact" : ""}`} data-testid={`${type}-audio`}>
      <button className="audio-listen-button" onClick={() => void listen()} disabled={isGenerating || !brief}>
        {isGenerating ? <LoaderCircle className="spin" /> : playing ? <Pause /> : brief?.status === "ready" ? <Play /> : <Headphones />}
        <span>{label}</span>
      </button>
      <button className="audio-text-button" onClick={() => setTranscriptOpen(true)} disabled={!brief} aria-label={`Read ${type} brief`}><BookOpenText /></button>
      {error && <span className="audio-error">{error}</span>}
      {brief?.audio_url && (
        <audio
          ref={audioRef}
          src={audioFileUrl(brief.audio_url)}
          preload="metadata"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
        />
      )}
      {transcriptOpen && brief && (
        <div className="audio-transcript-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setTranscriptOpen(false); }}>
          <section className="audio-transcript" role="dialog" aria-modal="true" aria-labelledby={`${type}-transcript-title`}>
            <header><div><span className="eyebrow">Brief transcript</span><h2 id={`${type}-transcript-title`}>{brief.title}</h2></div><button className="icon-button" aria-label="Close transcript" onClick={() => setTranscriptOpen(false)}><X /></button></header>
            <div className="audio-transcript__meta"><Volume2 /> {brief.voice} · {durationLabel(brief)} · snapshot {new Date(brief.source_snapshot_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</div>
            <div className="audio-transcript__sections">{brief.sections.map((section) => <section key={section.title}><span className="eyebrow">{section.title}</span><p>{section.text}</p></section>)}</div>
            <p className="copilot-boundary">This recording presents the same intelligence shown on your dashboard.</p>
          </section>
        </div>
      )}
    </div>
  );
}
