"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Room } from "livekit-client";

import { createVoiceSession } from "@/lib/api/product";
import type { VoiceAgentState } from "@/hooks/use-voice-input";

type CallStatusEvent = {
  type: "call_status";
  event: string;
  message: string;
};

function stateForCallEvent(event: string): VoiceAgentState {
  if (event === "listening" || event === "interrupted") return "listening";
  if (event === "researching_sources") return "researching";
  if (event === "tts_stream_started" || event === "speaking") return "speaking";
  if (event === "waiting_for_user" || event === "call_started") return "callActive";
  if (event === "error") return "error";
  return "processing";
}

export function useLiveKitSession({
  conversationId,
  enabled,
  onStateChange,
  onConversationId,
  onTranscript,
}: {
  conversationId: string | null;
  enabled: boolean;
  onStateChange: (state: VoiceAgentState) => void;
  onConversationId: (conversationId: string) => void;
  onTranscript: (message: { id: string; role: "user" | "assistant"; text: string }) => void;
}) {
  const roomRef = useRef<Room | null>(null);
  const audioElements = useRef<HTMLMediaElement[]>([]);
  const [muted, setMuted] = useState(false);
  const [active, setActive] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const clearAudio = useCallback(() => {
    audioElements.current.forEach((element) => element.remove());
    audioElements.current = [];
  }, []);

  const end = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) await room.disconnect();
    clearAudio();
    setActive(false);
    setConnecting(false);
    setMuted(false);
    setMessage("Call ended. You can reconnect when you’re ready.");
    onStateChange("callEnded");
  }, [clearAudio, onStateChange]);

  const start = useCallback(async () => {
    if (!enabled) {
      setMessage("Live call is not configured yet.");
      onStateChange("callUnavailable");
      return;
    }
    if (connecting || active) return;
    setConnecting(true);
    setMessage(null);
    onStateChange("callConnecting");
    try {
      const session = await createVoiceSession(conversationId);
      if (!session.enabled || !session.livekit_url || !session.token) {
        setConnecting(false);
        setMessage(session.reason ?? "Live call is not configured yet.");
        onStateChange("callUnavailable");
        return;
      }
      const { Room, RoomEvent, Track } = await import("livekit-client");
      const room = new Room({ adaptiveStream: true, disconnectOnPageLeave: true });
      room.on(RoomEvent.Disconnected, () => {
        roomRef.current = null;
        clearAudio();
        setActive(false);
        setConnecting(false);
        setMuted(false);
        setMessage("Call ended. You can reconnect when you’re ready.");
        onStateChange("callEnded");
      });
      room.on(RoomEvent.Reconnecting, () => onStateChange("callConnecting"));
      room.on(RoomEvent.Reconnected, () => onStateChange("callActive"));
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const remoteSpeaking = speakers.some((participant) => participant.identity !== room.localParticipant.identity);
        onStateChange(remoteSpeaking ? "speaking" : "callActive");
      });
      room.on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
        if (topic !== "wealth-copilot.call-state") return;
        try {
          const event = JSON.parse(new TextDecoder().decode(payload)) as CallStatusEvent;
          if (event.type !== "call_status" || !event.message) return;
          setMessage(event.message);
          onStateChange(stateForCallEvent(event.event));
          if (process.env.NODE_ENV === "development" && event.event.startsWith("latency_")) {
            console.debug("Wealth Copilot voice latency", event);
          }
        } catch {
          // Ignore malformed participant data while keeping the call connected.
        }
      });
      room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        const role = participant?.identity === room.localParticipant.identity ? "user" : "assistant";
        segments.filter((segment) => segment.final && segment.text.trim()).forEach((segment) => {
          onTranscript({
            id: `call-${session.room_name ?? "room"}-${segment.id}`,
            role,
            text: segment.text.trim(),
          });
        });
      });
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind !== Track.Kind.Audio) return;
        const element = track.attach();
        element.dataset.wealthCopilotCallAudio = "true";
        element.hidden = true;
        document.body.appendChild(element);
        audioElements.current.push(element);
      });
      roomRef.current = room;
      await room.connect(session.livekit_url, session.token);
      if (session.conversation_id) onConversationId(session.conversation_id);
      await room.localParticipant.setMicrophoneEnabled(true);
      if (room.remoteParticipants.size === 0) {
        await new Promise<void>((resolve, reject) => {
          const timer = window.setTimeout(() => {
            room.off(RoomEvent.ParticipantConnected, connected);
            reject(new Error("The voice agent did not join the room."));
          }, 12_000);
          const connected = () => {
            window.clearTimeout(timer);
            resolve();
          };
          room.once(RoomEvent.ParticipantConnected, connected);
        });
      }
      setConnecting(false);
      setActive(true);
      setMuted(false);
      setMessage("Secure live voice session connected.");
      onStateChange("callActive");
    } catch {
      const room = roomRef.current;
      roomRef.current = null;
      if (room) await room.disconnect().catch(() => undefined);
      clearAudio();
      setConnecting(false);
      setActive(false);
      setMessage("The call could not connect. You can retry or type your question.");
      onStateChange("error");
    }
  }, [active, clearAudio, connecting, conversationId, enabled, onConversationId, onStateChange, onTranscript]);

  const toggleMute = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    const next = !muted;
    await room.localParticipant.setMicrophoneEnabled(!next);
    setMuted(next);
  }, [muted]);

  useEffect(() => () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) void room.disconnect();
    clearAudio();
  }, [clearAudio]);

  return { active, connecting, muted, message, start, end, toggleMute };
}
