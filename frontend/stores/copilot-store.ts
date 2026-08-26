"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { askCopilot } from "@/lib/api/product";
import type { InteractionMode, SourceReference } from "@/lib/types";

export interface CopilotMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources: SourceReference[];
  suggestedQuestions?: string[];
  usedLongTermMemory?: boolean;
  memorySignals?: string[];
  mode?: InteractionMode;
}

interface CopilotState {
  conversationId: string | null;
  messages: CopilotMessage[];
  pending: boolean;
  error: string | null;
  send: (message: string, mode?: InteractionMode) => Promise<void>;
  adoptConversation: (conversationId: string) => void;
  appendCallTranscript: (message: CopilotMessage) => void;
  clear: () => void;
}

export const useCopilotStore = create<CopilotState>()(persist((set, get) => ({
  conversationId: null,
  messages: [],
  pending: false,
  error: null,
  send: async (message, mode = "text") => {
    const trimmed = message.trim();
    if (!trimmed || get().pending) return;
    const userMessage: CopilotMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: trimmed,
      sources: [],
      suggestedQuestions: [],
      mode,
    };
    set((state) => ({
      messages: [...state.messages, userMessage],
      pending: true,
      error: null,
    }));
    try {
      const response = await askCopilot({
        conversation_id: get().conversationId ?? undefined,
        message: trimmed,
        mode,
      });
      set((state) => ({
        conversationId: response.conversation_id,
        messages: [
          ...state.messages,
          {
            id: response.message_id,
            role: "assistant",
            text: response.answer,
            sources: response.sources,
            suggestedQuestions: response.suggested_questions,
            usedLongTermMemory: response.used_long_term_memory,
            memorySignals: response.memory_signals,
            mode,
          },
        ],
        pending: false,
      }));
    } catch {
      set({ pending: false, error: "Wealth Copilot could not answer right now." });
    }
  },
  adoptConversation: (conversationId) => set({ conversationId }),
  appendCallTranscript: (message) => set((state) => {
    const callMessage = { ...message, mode: "call" as const };
    const existingIndex = state.messages.findIndex((item) => item.id === message.id);
    if (existingIndex >= 0) {
      const messages = [...state.messages];
      messages[existingIndex] = callMessage;
      return { messages };
    }
    const last = state.messages.at(-1);
    if (last?.mode === "call" && last.role === callMessage.role) {
      const text = callMessage.text.trim();
      if (!text || last.text.includes(text)) return {};
      return {
        messages: [
          ...state.messages.slice(0, -1),
          { ...last, text: `${last.text.trim()} ${text}`.replace(/\s+/g, " ") },
        ],
      };
    }
    return { messages: [...state.messages, callMessage] };
  }),
  clear: () => set({ conversationId: null, messages: [], pending: false, error: null }),
}), {
  name: "wealth-copilot-conversation-v2",
  storage: createJSONStorage(() => localStorage),
  partialize: (state) => ({
    conversationId: state.conversationId,
    messages: state.messages,
    pending: false,
    error: null,
  }),
}));
