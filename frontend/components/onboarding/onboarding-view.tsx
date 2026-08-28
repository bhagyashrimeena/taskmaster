"use client";

import { Check, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { useOnboardingControls, useOnboardingProfile } from "@/hooks/use-product-queries";
import type { OnboardingInferenceInput, SuggestedProfile, SuggestedValue } from "@/lib/product-types";

const userId = "demo_user";

const choices = {
  age_range: ["22-25", "26-30", "31-40", "41-55", "55_plus"],
  income_range: ["5L-10L", "10L-20L", "20L-50L", "50L_plus"],
  employment_type: ["salaried", "self_employed", "student", "business_owner"],
  investment_experience: ["beginner", "intermediate", "advanced"],
  existing_investments: ["equity", "mutual_funds", "debt", "gold", "cash"],
  primary_goals: ["wealth_building", "emergency_fund", "tax_planning", "retirement", "short_term_purchase", "learning_finance"],
  time_horizon: ["under_1_year", "1_3_years", "3_5_years", "5_plus_years", "10_plus_years"],
  dependents: ["none", "parents", "children", "spouse", "multiple"],
  emergency_fund_status: ["none", "partial", "complete"],
  market_interest_level: ["low", "moderate", "active"],
  preferred_explanation_style: ["simple", "balanced", "detailed"],
};

const labels: Record<string, string> = {
  age_range: "Age range",
  income_range: "Income range",
  employment_type: "Employment",
  investment_experience: "Experience",
  existing_investments: "Existing investments",
  primary_goals: "Primary goals",
  time_horizon: "Time horizon",
  dependents: "Dependents",
  emergency_fund_status: "Emergency fund",
  market_interest_level: "Market interest",
  preferred_explanation_style: "Explanation style",
  life_stage: "Life stage",
  cashflow_profile: "Cashflow profile",
  emergency_fund_focus: "Emergency fund focus",
  risk_profile: "Risk profile",
  risk_capacity: "Risk capacity",
  risk_comfort: "Risk comfort",
  primary_goal: "Primary goal",
  alert_sensitivity: "Alert sensitivity",
  minimum_attention_outcome: "Minimum attention outcome",
  learning_preference: "Learning preference",
};

const pretty = (value: unknown) => String(value ?? "—").replaceAll("_", " ");
const preferenceString = (preferences: Record<string, unknown>, field: string, fallback: string) =>
  typeof preferences[field] === "string" ? preferences[field] : fallback;

const starterInput: OnboardingInferenceInput = {
  user_id: userId,
  age_range: "22-25",
  income_range: "10L-20L",
  employment_type: "salaried",
  investment_experience: "beginner",
  existing_investments: ["equity", "mutual_funds"],
  primary_goals: ["wealth_building", "emergency_fund"],
  time_horizon: "5_plus_years",
  dependents: "none",
  emergency_fund_status: "partial",
  market_interest_level: "moderate",
  preferred_explanation_style: "simple",
  quiet_mode: false,
};

function ToggleGroup({
  field,
  values,
  input,
  setInput,
  multiple = false,
}: {
  field: keyof OnboardingInferenceInput;
  values: string[];
  input: OnboardingInferenceInput;
  setInput: (next: OnboardingInferenceInput) => void;
  multiple?: boolean;
}) {
  const selected = input[field];
  return (
    <div>
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-muted">{labels[field] ?? field}</p>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => {
          const active = Array.isArray(selected) ? selected.includes(value) : selected === value;
          return (
            <button
              className={`min-h-11 rounded-full border px-3.5 text-sm font-semibold capitalize transition ${
                active ? "border-brand bg-brand text-background" : "border-line bg-surface text-muted hover:border-brand/45 hover:text-ink"
              }`}
              key={value}
              type="button"
              aria-pressed={active}
              onClick={() => {
                if (!multiple) {
                  setInput({ ...input, [field]: value });
                  return;
                }
                const current = Array.isArray(selected) ? selected : [];
                setInput({
                  ...input,
                  [field]: active ? current.filter((item) => item !== value) : [...current, value],
                });
              }}
            >
              {pretty(value)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SuggestedField({
  name,
  suggestion,
  finalProfile,
  setFinalProfile,
  options,
}: {
  name: string;
  suggestion: SuggestedValue;
  finalProfile: Record<string, unknown>;
  setFinalProfile: (next: Record<string, unknown>) => void;
  options?: string[];
}) {
  return (
    <article className="rounded-2xl border border-line bg-surface/80 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-brand">{labels[name] ?? name}</p>
          <strong className="mt-1 block text-lg capitalize">Suggested: {pretty(suggestion.value)}</strong>
        </div>
        <span className="rounded-full border border-brand/20 bg-brand/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-brand">
          {suggestion.confidence} confidence
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted">Why: {suggestion.reason}</p>
      <label className="mt-3 block text-xs font-bold uppercase tracking-[0.16em] text-muted" htmlFor={`onboarding-${name}`}>
        Edit value
      </label>
      <select
        id={`onboarding-${name}`}
        className="mt-2 min-h-11 w-full rounded-xl border border-line bg-background px-3 text-sm font-semibold capitalize outline-none focus:border-brand"
        value={String(finalProfile[name] ?? suggestion.value)}
        onChange={(event) => setFinalProfile({ ...finalProfile, [name]: event.target.value })}
      >
        {Array.from(new Set([String(suggestion.value), ...(options ?? [])])).map((value) => (
          <option key={value} value={value}>{pretty(value)}</option>
        ))}
      </select>
    </article>
  );
}

function CheckpointEditor({
  preferences,
  onChange,
}: {
  preferences: Record<string, unknown>;
  onChange: (preferences: Record<string, unknown>) => void;
}) {
  const checkpoints = { ...((preferences.checkpoint_preferences as Record<string, boolean> | undefined) ?? {}) };
  return (
    <div className="grid gap-2 rounded-2xl border border-line bg-surface/80 p-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-brand">Suggested checkpoint schedule</p>
      {Object.entries(checkpoints).map(([key, enabled]) => (
        <label className="flex min-h-11 items-center justify-between gap-3 rounded-xl bg-background px-3 text-sm capitalize" key={key}>
          <span>{pretty(key)}</span>
          <input
            className="size-5 accent-[var(--brand)]"
            type="checkbox"
            checked={Boolean(enabled)}
            onChange={(event) => onChange({
              ...preferences,
              checkpoint_preferences: { ...checkpoints, [key]: event.target.checked },
            })}
          />
        </label>
      ))}
    </div>
  );
}

function makeFinalProfile(suggested: SuggestedProfile): Record<string, unknown> {
  return {
    life_stage: suggested.financial_profile_suggestions.life_stage.value,
    cashflow_profile: suggested.financial_profile_suggestions.cashflow_profile.value,
    emergency_fund_focus: suggested.financial_profile_suggestions.emergency_fund_focus.value,
    risk_profile: suggested.risk_profile_suggestions.risk_profile.value,
    risk_capacity: suggested.risk_profile_suggestions.risk_capacity.value,
    risk_comfort: suggested.risk_profile_suggestions.risk_comfort.value,
    primary_goal: suggested.goal_suggestions.primary_goal,
    secondary_goals: suggested.goal_suggestions.secondary_goals,
    goal_order: suggested.goal_suggestions.suggested_order,
    agent_preferences: suggested.agent_preferences,
  };
}

export function OnboardingView() {
  const saved = useOnboardingProfile(userId);
  const controls = useOnboardingControls(userId);
  const [step, setStep] = useState(0);
  const [input, setInput] = useState<OnboardingInferenceInput>(starterInput);
  const [suggested, setSuggested] = useState<SuggestedProfile | null>(null);
  const [finalProfile, setFinalProfile] = useState<Record<string, unknown>>({});

  const agentPreferences = useMemo(
    () => ({ ...((finalProfile.agent_preferences as Record<string, unknown> | undefined) ?? suggested?.agent_preferences ?? {}) }),
    [finalProfile.agent_preferences, suggested],
  );

  const runInference = async () => {
    const profile = await controls.infer.mutateAsync(input);
    setSuggested(profile);
    setFinalProfile(makeFinalProfile(profile));
    setStep(3);
  };

  const saveProfile = async () => {
    if (!suggested) return;
    await controls.save.mutateAsync({ raw_inputs: input, suggested_profile: suggested, final_profile: finalProfile });
  };

  return (
    <div className="space-y-5">
      <section className="rounded-[2rem] border border-brand/20 bg-[radial-gradient(circle_at_top_left,rgba(111,255,224,.18),transparent_35%),linear-gradient(135deg,#071014,#10231d)] p-5 text-white shadow-[var(--shadow-card)] md:p-8">
        <p className="section-kicker section-kicker--dark">Onboarding</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight md:text-6xl">Set your financial rhythm in minutes</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-white/68 md:text-base">
          Share a few early inputs. Wealth Copilot suggests defaults for goals, risk comfort, alerts, checkpoints, and voice style — and you can edit everything.
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-bold uppercase tracking-wider text-brand">
          <span className="rounded-full bg-white/8 px-3 py-1.5">Suggested, not fixed</span>
          <span className="rounded-full bg-white/8 px-3 py-1.5">No trade advice</span>
          <span className="rounded-full bg-white/8 px-3 py-1.5">Editable profile</span>
        </div>
      </section>

      <section className="product-card p-4 md:p-6" aria-live="polite">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <p className="section-kicker">Step {step + 1} of 6</p>
            <h2 className="section-title mt-1">
              {["Basic profile", "Experience", "Goals", "Suggested financial profile", "Suggested risk profile", "Agent behavior"][step]}
            </h2>
          </div>
          {saved.data?.session && <span className="rounded-full border border-brand/20 bg-brand/10 px-3 py-1 text-xs font-bold text-brand">Saved</span>}
        </div>

        {step === 0 && (
          <div className="grid gap-5">
            <ToggleGroup field="age_range" values={choices.age_range} input={input} setInput={setInput} />
            <ToggleGroup field="income_range" values={choices.income_range} input={input} setInput={setInput} />
            <ToggleGroup field="employment_type" values={choices.employment_type} input={input} setInput={setInput} />
          </div>
        )}
        {step === 1 && (
          <div className="grid gap-5">
            <ToggleGroup field="investment_experience" values={choices.investment_experience} input={input} setInput={setInput} />
            <ToggleGroup field="existing_investments" values={choices.existing_investments} input={input} setInput={setInput} multiple />
            <ToggleGroup field="market_interest_level" values={choices.market_interest_level} input={input} setInput={setInput} />
          </div>
        )}
        {step === 2 && (
          <div className="grid gap-5">
            <ToggleGroup field="primary_goals" values={choices.primary_goals} input={input} setInput={setInput} multiple />
            <ToggleGroup field="time_horizon" values={choices.time_horizon} input={input} setInput={setInput} />
            <ToggleGroup field="dependents" values={choices.dependents} input={input} setInput={setInput} />
            <ToggleGroup field="emergency_fund_status" values={choices.emergency_fund_status} input={input} setInput={setInput} />
            <ToggleGroup field="preferred_explanation_style" values={choices.preferred_explanation_style} input={input} setInput={setInput} />
            <label className="flex min-h-11 items-center justify-between gap-3 rounded-2xl border border-line bg-surface px-4 text-sm font-semibold">
              Quiet mode: fewer immediate interruptions
              <input className="size-5 accent-[var(--brand)]" type="checkbox" checked={Boolean(input.quiet_mode)} onChange={(event) => setInput({ ...input, quiet_mode: event.target.checked })} />
            </label>
          </div>
        )}

        {suggested && step >= 3 && (
          <div className="grid gap-4">
            <p className="rounded-2xl border border-brand/20 bg-brand/10 p-3 text-sm leading-6 text-brand">
              {suggested.disclaimer}
            </p>
            {step === 3 && (
              <div className="grid gap-3 md:grid-cols-2">
                <SuggestedField name="life_stage" suggestion={suggested.financial_profile_suggestions.life_stage} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={["early_career", "family_builder", "established_earner"]} />
                <SuggestedField name="cashflow_profile" suggestion={suggested.financial_profile_suggestions.cashflow_profile} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={["growing_income", "stable_income", "variable_income"]} />
                <SuggestedField name="emergency_fund_focus" suggestion={suggested.financial_profile_suggestions.emergency_fund_focus} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={["complete_first", "maintain"]} />
                <SuggestedField name="primary_goal" suggestion={{ value: suggested.goal_suggestions.primary_goal, confidence: "medium", reason: "Suggested from the goals you selected; you can reorder priorities later." }} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={choices.primary_goals} />
              </div>
            )}
            {step === 4 && (
              <div className="grid gap-3 md:grid-cols-3">
                <SuggestedField name="risk_profile" suggestion={suggested.risk_profile_suggestions.risk_profile} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={["conservative", "moderate", "moderately_aggressive", "aggressive"]} />
                <SuggestedField name="risk_capacity" suggestion={suggested.risk_profile_suggestions.risk_capacity} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={["low", "medium", "medium_high", "high"]} />
                <SuggestedField name="risk_comfort" suggestion={suggested.risk_profile_suggestions.risk_comfort} finalProfile={finalProfile} setFinalProfile={setFinalProfile} options={["cautious", "balanced", "market_aware"]} />
              </div>
            )}
            {step === 5 && (
              <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
                <div className="grid gap-3">
                  <SuggestedField name="alert_sensitivity" suggestion={{ value: preferenceString(agentPreferences, "alert_sensitivity", "balanced"), confidence: "medium", reason: "Suggested from your market interest and quiet-mode preference." }} finalProfile={agentPreferences} setFinalProfile={(next) => setFinalProfile({ ...finalProfile, agent_preferences: next })} options={["quiet", "balanced", "active"]} />
                  <SuggestedField name="minimum_attention_outcome" suggestion={{ value: preferenceString(agentPreferences, "minimum_attention_outcome", "INVESTIGATE"), confidence: "medium", reason: "Suggested to control which events interrupt you immediately." }} finalProfile={agentPreferences} setFinalProfile={(next) => setFinalProfile({ ...finalProfile, agent_preferences: next })} options={["MONITOR", "INVESTIGATE", "ALERT"]} />
                  <SuggestedField name="learning_preference" suggestion={{ value: preferenceString(agentPreferences, "learning_preference", "simple_explanations"), confidence: "medium", reason: "Suggested from investing experience and explanation style." }} finalProfile={agentPreferences} setFinalProfile={(next) => setFinalProfile({ ...finalProfile, agent_preferences: next })} options={["simple_explanations", "concise_market_context", "deeper_research"]} />
                </div>
                <CheckpointEditor preferences={agentPreferences} onChange={(next) => setFinalProfile({ ...finalProfile, agent_preferences: next })} />
              </div>
            )}
            {suggested.missing_inputs.length > 0 && (
              <p className="text-xs leading-5 text-muted">
                Lower-confidence areas: {suggested.missing_inputs.map(pretty).join(", ")}. You can add these later.
              </p>
            )}
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <button className="min-h-11 rounded-full border border-line px-4 text-sm font-bold text-muted disabled:opacity-40" type="button" disabled={step === 0 || controls.pending} onClick={() => setStep(Math.max(0, step - 1))}>
            <ChevronLeft className="mr-1 inline" size={16} /> Back
          </button>
          <div className="flex flex-wrap gap-2">
            {step < 2 && (
              <button className="min-h-11 rounded-full bg-brand px-5 text-sm font-bold text-background" type="button" onClick={() => setStep(step + 1)}>
                Next <ChevronRight className="ml-1 inline" size={16} />
              </button>
            )}
            {step === 2 && (
              <button className="min-h-11 rounded-full bg-brand px-5 text-sm font-bold text-background disabled:opacity-50" type="button" disabled={controls.pending} onClick={runInference}>
                <Sparkles className="mr-1 inline" size={16} /> Suggest defaults
              </button>
            )}
            {step >= 3 && step < 5 && (
              <button className="min-h-11 rounded-full bg-brand px-5 text-sm font-bold text-background" type="button" onClick={() => setStep(step + 1)}>
                Continue <ChevronRight className="ml-1 inline" size={16} />
              </button>
            )}
            {step === 5 && (
              <button className="min-h-11 rounded-full bg-brand px-5 text-sm font-bold text-background disabled:opacity-50" type="button" disabled={!suggested || controls.pending} onClick={saveProfile}>
                <Check className="mr-1 inline" size={16} /> Save editable profile
              </button>
            )}
          </div>
        </div>
        {controls.save.isSuccess && <p className="mt-4 rounded-2xl bg-positive/10 p-3 text-sm font-semibold text-positive">Profile saved. Wealth Copilot will use your final selected preferences, not just the suggestions.</p>}
        {controls.infer.isError || controls.save.isError ? <p className="mt-4 rounded-2xl bg-negative/10 p-3 text-sm font-semibold text-negative">Onboarding could not update right now. You can retry without losing your choices.</p> : null}
      </section>
    </div>
  );
}
