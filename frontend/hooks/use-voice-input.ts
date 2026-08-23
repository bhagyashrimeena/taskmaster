"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

export type VoiceAgentState =
  | "idle"
  | "ready"
  | "listening"
  | "processing"
  | "researching"
  | "speaking"
  | "callConnecting"
  | "callActive"
  | "callEnded"
  | "callUnavailable"
  | "error";

type RecognitionResult = { transcript: string };
type RecognitionEvent = { results: ArrayLike<{ 0: RecognitionResult }>; resultIndex: number };
type RecognitionErrorEvent = { error: string };
type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};
type RecognitionConstructor = new () => Recognition;

function recognitionConstructor(): RecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const speechWindow = window as typeof window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

const subscribeToBrowserCapability = () => () => undefined;

export function useVoiceInput({
  onTranscript,
  onStateChange,
}: {
  onTranscript: (transcript: string) => void;
  onStateChange: (state: VoiceAgentState) => void;
}) {
  const supported = useSyncExternalStore(
    subscribeToBrowserCapability,
    () => Boolean(recognitionConstructor()),
    () => false,
  );
  const [listening, setListening] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const recognitionRef = useRef<Recognition | null>(null);
  const transcriptRef = useRef("");

  useEffect(() => {
    return () => recognitionRef.current?.abort();
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const cancel = useCallback(() => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    transcriptRef.current = "";
    setListening(false);
    onStateChange(supported ? "ready" : "idle");
  }, [onStateChange, supported]);

  const start = useCallback(() => {
    const Constructor = recognitionConstructor();
    if (!Constructor) {
      setMessage("Voice input is not available in this browser. You can still type your question.");
      onStateChange("idle");
      return;
    }
    if (recognitionRef.current || listening) return;
    const recognition = new Constructor();
    transcriptRef.current = "";
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0]?.transcript ?? "";
      }
      transcriptRef.current = transcript.trim();
      if (transcriptRef.current) onTranscript(transcriptRef.current);
    };
    recognition.onerror = (event) => {
      const denied = event.error === "not-allowed" || event.error === "service-not-allowed";
      setMessage(denied
        ? "Microphone permission was denied. You can still type your question."
        : "Voice input stopped unexpectedly. You can still type your question.");
      setListening(false);
      recognitionRef.current = null;
      onStateChange("error");
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
      onStateChange("ready");
    };
    recognitionRef.current = recognition;
    setMessage(null);
    setListening(true);
    onStateChange("listening");
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setListening(false);
      setMessage("Voice input could not start. You can still type your question.");
      onStateChange("error");
    }
  }, [listening, onStateChange, onTranscript]);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && listening) cancel();
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [cancel, listening]);

  return { supported, listening, message, start, stop, cancel };
}
