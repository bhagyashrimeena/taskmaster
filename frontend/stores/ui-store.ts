"use client";

import { create } from "zustand";

import type { AlertCategory } from "@/lib/product-types";

export interface ActivityToastNotice {
  id: string;
  tone?: "info" | "success" | "alert";
  title: string;
  detail?: string;
  actionLabel?: string;
  actionHref?: string;
  durationMs?: number | null;
  replaceCurrent?: boolean;
}

interface UiState {
  alertFilter: AlertCategory;
  portfolioRange: "1D" | "1W" | "1M" | "3M" | "1Y";
  activityToast: ActivityToastNotice | null;
  activityToastQueue: ActivityToastNotice[];
  setAlertFilter: (filter: AlertCategory) => void;
  setPortfolioRange: (range: UiState["portfolioRange"]) => void;
  showActivityToast: (notice: ActivityToastNotice) => void;
  dismissActivityToast: (id: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  alertFilter: "attention",
  portfolioRange: "1D",
  activityToast: null,
  activityToastQueue: [],
  setAlertFilter: (alertFilter) => set({ alertFilter }),
  setPortfolioRange: (portfolioRange) => set({ portfolioRange }),
  showActivityToast: (notice) => set((state) => {
    if (notice.replaceCurrent) {
      return { activityToast: notice, activityToastQueue: [] };
    }
    if (state.activityToast?.id === notice.id) return { activityToast: notice };
    if (!state.activityToast) return { activityToast: notice };
    return {
      activityToastQueue: [
        ...state.activityToastQueue.filter((item) => item.id !== notice.id),
        notice,
      ].slice(-5),
    };
  }),
  dismissActivityToast: (id) => set((state) => {
    if (state.activityToast?.id !== id) {
      return { activityToastQueue: state.activityToastQueue.filter((item) => item.id !== id) };
    }
    const [next, ...remaining] = state.activityToastQueue;
    return { activityToast: next ?? null, activityToastQueue: remaining };
  }),
}));
