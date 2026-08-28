"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  advanceFinancialDayClock,
  getOnboardingProfile,
  getAlert,
  getAlerts,
  getCopilotBootstrap,
  getPortfolio,
  getTimeline,
  getToday,
  getFinancialDayClock,
  pauseFinancialDayClock,
  inferOnboardingProfile,
  restartFinancialDayClock,
  saveOnboardingProfile,
  startFinancialDayClock,
} from "@/lib/api/product";
import type { FinancialDayClockState } from "@/lib/types";
import type { AlertCategory, OnboardingInferenceInput, SuggestedProfile } from "@/lib/product-types";
import { productKeys } from "@/lib/queries/keys";

const common = {
  staleTime: 30_000,
  retry: 2,
  refetchOnWindowFocus: true,
} as const;

export function useToday() {
  return useQuery({ queryKey: productKeys.today, queryFn: getToday, ...common });
}

export function usePortfolio() {
  return useQuery({ queryKey: productKeys.portfolio, queryFn: getPortfolio, ...common });
}

export function useAlerts(category?: AlertCategory) {
  return useQuery({ queryKey: productKeys.alerts(category), queryFn: () => getAlerts(category), ...common });
}

export function useAlert(caseId: string) {
  return useQuery({ queryKey: productKeys.alert(caseId), queryFn: () => getAlert(caseId), enabled: Boolean(caseId), ...common });
}

export function useTimeline() {
  return useQuery({ queryKey: productKeys.timeline, queryFn: getTimeline, ...common });
}

export function useFinancialDayClock() {
  return useQuery({
    queryKey: productKeys.dayClock,
    queryFn: getFinancialDayClock,
    ...common,
    refetchInterval: (query) => query.state.data?.status === "running" ? 1_000 : false,
  });
}

export function useFinancialDayClockControls() {
  const queryClient = useQueryClient();
  const options = {
    onSuccess: (state: FinancialDayClockState) => {
      queryClient.setQueryData(productKeys.dayClock, state);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: productKeys.all }),
  };
  const start = useMutation({ mutationFn: startFinancialDayClock, ...options });
  const pause = useMutation({ mutationFn: pauseFinancialDayClock, ...options });
  const restart = useMutation({ mutationFn: restartFinancialDayClock, ...options });
  const advance = useMutation({ mutationFn: advanceFinancialDayClock, ...options });
  return {
    advance,
    start,
    pause,
    restart,
    pending: start.isPending || pause.isPending || restart.isPending || advance.isPending,
  };
}

export function useCopilotBootstrap(conversationId?: string | null) {
  return useQuery({
    queryKey: productKeys.copilot(conversationId),
    queryFn: () => getCopilotBootstrap(conversationId),
    ...common,
  });
}

export function useOnboardingProfile(userId = "demo_user") {
  return useQuery({
    queryKey: productKeys.onboarding(userId),
    queryFn: () => getOnboardingProfile(userId),
    ...common,
  });
}

export function useOnboardingControls(userId = "demo_user") {
  const queryClient = useQueryClient();
  const infer = useMutation({
    mutationFn: (input: OnboardingInferenceInput) => inferOnboardingProfile({ user_id: userId, ...input }),
  });
  const save = useMutation({
    mutationFn: (input: {
      raw_inputs: OnboardingInferenceInput;
      suggested_profile: SuggestedProfile;
      final_profile: Record<string, unknown>;
    }) => saveOnboardingProfile({ user_id: userId, ...input }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.onboarding(userId) });
      queryClient.invalidateQueries({ queryKey: productKeys.copilot(null) });
      queryClient.invalidateQueries({ queryKey: productKeys.timeline });
      queryClient.invalidateQueries({ queryKey: productKeys.today });
    },
  });
  return { infer, save, pending: infer.isPending || save.isPending };
}
