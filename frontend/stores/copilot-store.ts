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
          },
        ],
        pending: false,
      }));
    } catch {
      set({ pending: false, error: "Wealth Copilot could not answer right now." });
    }
  },
  adoptConversation: (conversationId) => set({ conversationId }),
  appendCallTranscript: (message) => set((state) => ({
    messages: state.messages.some((item) => item.id === message.id)
      ? state.messages
      : [...state.messages, message],
  })),
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
