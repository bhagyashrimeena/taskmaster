"use client";

import { create } from "zustand";

import type { AlertCategory } from "@/lib/product-types";

export interface ProactiveAlertNotice {
  eventId: string;
  caseId: string | null;
  title: string;
  summary: string;
}

interface UiState {
  alertFilter: AlertCategory;
  portfolioRange: "1D" | "1W" | "1M" | "3M" | "1Y";
  proactiveAlert: ProactiveAlertNotice | null;
  setAlertFilter: (filter: AlertCategory) => void;
  setPortfolioRange: (range: UiState["portfolioRange"]) => void;
  showProactiveAlert: (notice: ProactiveAlertNotice) => void;
  dismissProactiveAlert: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  alertFilter: "attention",
  portfolioRange: "1D",
  proactiveAlert: null,
  setAlertFilter: (alertFilter) => set({ alertFilter }),
  setPortfolioRange: (portfolioRange) => set({ portfolioRange }),
  showProactiveAlert: (proactiveAlert) => set({ proactiveAlert }),
  dismissProactiveAlert: () => set({ proactiveAlert: null }),
}));
