"use client";

import {
  ArrowUpRight,
  BellRing,
  Bookmark,
  Check,
  CircleAlert,
  Clock3,
  ExternalLink,
  Landmark,
  LoaderCircle,
  MessageCircle,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  SkipForward,
  Sparkles,
  TrendingDown,
  UserRoundCheck,
  WalletCards,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { CopilotRequest, CopilotSheet, CopilotTarget } from "@/components/copilot-sheet";
import { AudioBriefControl } from "@/components/audio-brief";
import { AdvisorSheet, AdvisorTarget } from "@/components/advisor-sheet";
import { WealthStoryControl } from "@/components/wealth-story";
import { readStoredThread } from "@/lib/chat-storage.js";
import { advancePresentationClock, advancePresentationClockToNext, getDashboard, getFinancialDay, getPresentationClock, pausePresentationClock, playPresentationClock, requestRefresh, restartPresentationClock, saveEventAction, saveStoryForEvening } from "@/lib/api";
import type { DashboardData, FinancialDayState, FreshnessStatus, PresentationClockState, StoryView } from "@/lib/types";

const compactInr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  notation: "compact",
  maximumFractionDigits: 2,
});

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function formatMarketClock(value: string) {
  const [hourValue, minute] = value.split(":");
  const hour = Number(hourValue);
  const suffix = hour >= 12 ? "PM" : "AM";
  const twelveHour = hour % 12 || 12;
  return `${twelveHour}:${minute} ${suffix}`;
}

function freshnessLabel(status: FreshnessStatus, fetchedAt: string) {
  const ageMinutes = Math.max(0, Math.floor((Date.now() - new Date(fetchedAt).getTime()) / 60000));
  if (status === "stale") return `Last updated ${ageMinutes} min ago`;
  if (ageMinutes === 0) return "Updated just now";
  return `Updated ${ageMinutes} min ago`;
}

function attentionMessage(count: number) {
  return `${count} ${count === 1 ? "thing deserves" : "things deserve"} your attention today`;
}

function clockMinute(value: string | undefined) {
  if (!value) return 0;
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function isTransientCitationUrl(value: string) {
  try {
    return new URL(value).hostname === "vertexaisearch.cloud.google.com";
  } catch {
    return false;
  }
}

function freshnessClass(status: FreshnessStatus) {
  return `freshness freshness--${status}`;
}

function DashboardSkeleton() {
  return (
    <main className="dashboard-shell" aria-label="Loading Wealth Copilot">
      <div className="loading-card">
        <div className="brand-mark"><Sparkles size={20} /></div>
        <p>Opening your latest intelligence…</p>
        <div className="skeleton-line" />
      </div>
    </main>
  );
}

function StoryCard({
  story,
  index,
  saved,
  onExplain,
  onResearch,
  onAskAdvisor,
  onSave,
}: {
  story: StoryView;
  index: number;
  saved: boolean;
  onExplain: () => void;
  onResearch: () => void;
  onAskAdvisor: () => void;
  onSave: () => void;
}) {
  return (
    <article className="story-card" data-testid={`story-${index + 1}`}>
      <div className="story-rank">{String(index + 1).padStart(2, "0")}</div>
      <div className="story-body">
        <div className="story-topline">
          <div className="holding-chips">
            {(story.affected_holdings.length ? story.affected_holdings : ["SECTOR"]).map((holding) => (
              <span className="chip" key={holding}>{holding}</span>
            ))}
          </div>
          <div className="score-pill" aria-label={`Relevance ${story.relevance_score.toFixed(1)}`}>
            <Sparkles size={13} /> {story.relevance_score.toFixed(1)}
          </div>
        </div>
        <h3>{story.headline}</h3>
        <p className="story-summary">{story.summary}</p>
        <div className="story-metrics">
          <span><strong>{story.direct_exposure_pct.toFixed(2)}%</strong> direct exposure</span>
          <span><strong>{story.sector_exposure_pct.toFixed(2)}%</strong> sector exposure</span>
          {story.canonical_url_status !== "verified" || !story.canonical_url || isTransientCitationUrl(story.canonical_url) ? (
            <span className="story-source--unavailable" title="A durable publisher URL was not provided for this source.">
              {story.source_name} · source link unavailable
            </span>
          ) : (
            <a href={story.canonical_url} target="_blank" rel="noreferrer">
              {story.source_name} <ExternalLink size={12} />
            </a>
          )}
        </div>
        <div className="story-actions">
          <button className="text-button" onClick={onExplain}>
            Explain <Sparkles size={14} />
          </button>
          <button className="text-button" onClick={onResearch}>
            Learn more <ArrowUpRight size={14} />
          </button>
          <button className="text-button" onClick={onAskAdvisor}>
            Ask advisor <UserRoundCheck size={14} />
          </button>
          <button className="text-button" onClick={onSave} aria-pressed={saved}>
            {saved ? <Check size={14} /> : <Bookmark size={14} />} {saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </article>
  );
}

function FinancialDayPanel({
  day,
  clock,
  controlling,
  onPlayPause,
  onAdvance,
  onNext,
  onRestart,
  presentation,
}: {
  day: FinancialDayState | null;
  clock: PresentationClockState | null;
  controlling: boolean;
  onPlayPause: () => void;
  onAdvance: () => void;
  onNext: () => void;
  onRestart: () => void;
  presentation: boolean;
}) {
  const running = presentation ? clock?.status === "running" : day?.status === "running";
  const complete = day?.status === "complete";
  const currentMinute = presentation ? clockMinute(clock?.current_time) : Number.POSITIVE_INFINITY;
  const eventReleased = !presentation || currentMinute >= 12 * 60 + 17;
  const closeReleased = !presentation || currentMinute >= 15 * 60 + 30;
  const tomorrowReleased = !presentation || currentMinute >= 21 * 60;
  return (
    <section className="panel day-panel" aria-labelledby="financial-day-title" data-testid="financial-day">
      <div className="day-panel__header">
        <div>
          <span className="eyebrow">Autonomous operations</span>
          <h2 id="financial-day-title">Your financial day</h2>
        </div>
        <span className={`day-state day-state--${day?.status ?? "not_started"}`}>
          {running ? <LoaderCircle className="spin" size={12} /> : complete ? <Check size={12} /> : <Clock3 size={12} />}
          {running ? "updating" : (day?.status ?? "ready").replace("_", " ")}
        </span>
      </div>
      <p className="day-panel__intro">See TaskMaster carry context from morning scan to tomorrow prep.</p>
      {presentation && clock && (
        <div className="market-clock" data-testid="presentation-clock">
          <div className="market-clock__readout">
            <span>Financial day</span>
            <strong data-testid="market-clock-time">{formatMarketClock(clock.current_time)}</strong>
            <small>{clock.speed}×</small>
          </div>
          <div className="market-clock__controls">
            <button
              type="button"
              onClick={onPlayPause}
              disabled={controlling || clock.status === "complete" || clock.status === "failed"}
              aria-label={running ? "Pause financial day" : "Play financial day"}
              data-testid="clock-play-pause"
            >
              {controlling ? <LoaderCircle className="spin" size={14} /> : running ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
              {running ? "Pause" : "Play"}
            </button>
            <button type="button" onClick={onAdvance} disabled={controlling || running || clock.status === "complete"} aria-label="Advance financial day by one hour">
              +1h
            </button>
            <button type="button" onClick={onNext} disabled={controlling || running || !clock.next_checkpoint} aria-label="Advance to next checkpoint" data-testid="clock-next">
              <SkipForward size={13} /> Next
            </button>
            <button type="button" className="market-clock__restart" onClick={onRestart} disabled={controlling} aria-label="Restart financial day" title="Restart day" data-testid="clock-restart">
              <RotateCcw size={13} />
            </button>
          </div>
          <p>{clock.message}</p>
        </div>
      )}
      <div className="day-timeline">
        {(day?.timeline ?? [
          { step_id: "morning", scheduled_time: "07:00", label: "Morning Pulse", status: "pending" as const, detail: "", linked_ids: [] },
          { step_id: "health", scheduled_time: "08:00", label: "Portfolio Health", status: "pending" as const, detail: "", linked_ids: [] },
          { step_id: "event", scheduled_time: "12:17", label: "HDFC Bank event", status: "pending" as const, detail: "", linked_ids: [] },
          { step_id: "close", scheduled_time: "15:30", label: "Market Close Review", status: "pending" as const, detail: "", linked_ids: [] },
          { step_id: "evening", scheduled_time: "20:00", label: "Evening Wealth Wrap", status: "pending" as const, detail: "", linked_ids: [] },
          { step_id: "tomorrow", scheduled_time: "21:00", label: "Tomorrow Prep", status: "pending" as const, detail: "", linked_ids: [] },
          { step_id: "story", scheduled_time: "21:01", label: "Daily Wealth Story", status: "pending" as const, detail: "", linked_ids: [] },
        ]).map((step, index, timeline) => (
          <div className={`day-step day-step--${step.status}`} key={step.step_id} data-testid={`day-step-${step.step_id}`}>
            <time>{step.scheduled_time}</time>
            <div className="day-step__marker">
              {step.status === "complete" ? <Check size={11} /> : step.status === "running" ? <LoaderCircle className="spin" size={11} /> : <span />}
            </div>
            <div className="day-step__copy">
              <strong>{presentation && step.step_id === "event" && !eventReleased ? "Market Watch" : step.label}</strong>
              {step.status !== "pending" && <span>{step.detail}</span>}
            </div>
            {index < timeline.length - 1 && <i aria-hidden="true" />}
          </div>
        ))}
      </div>
      {day?.market_close_review && closeReleased && (
        <div className="day-result">
          <strong>{day.market_close_review.portfolio_return_pct >= 0 ? "+" : ""}{day.market_close_review.portfolio_return_pct.toFixed(2)}%</strong>
          <span>closing portfolio move explained</span>
        </div>
      )}
      {day?.tomorrow_events.length && tomorrowReleased ? (
        <p className="day-tomorrow"><strong>Tomorrow:</strong> {day.tomorrow_events.length} portfolio-relevant items scheduled.</p>
      ) : null}
    </section>
  );
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedStories, setSavedStories] = useState<Set<string>>(new Set());
  const [savedEvents, setSavedEvents] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<string | null>(null);
  const [copilotRequest, setCopilotRequest] = useState<CopilotRequest | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotUnread, setCopilotUnread] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [globalQuestion, setGlobalQuestion] = useState("");
  const [inlineCopilotVisible, setInlineCopilotVisible] = useState(true);
  const [signalNotice, setSignalNotice] = useState<string | null>(null);
  const inlineCopilotRef = useRef<HTMLFormElement | null>(null);
  const [financialDay, setFinancialDay] = useState<FinancialDayState | null>(null);
  const [presentationClock, setPresentationClock] = useState<PresentationClockState | null>(null);
  const [advisorTarget, setAdvisorTarget] = useState<AdvisorTarget | null>(null);
  const [clockControlling, setClockControlling] = useState(false);
  const [proactiveAlert, setProactiveAlert] = useState(false);
  const [presentationMode, setPresentationMode] = useState(false);
  const refreshStarted = useRef(false);
  const interactionKey = useRef(0);
  const alertedEventIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    window.queueMicrotask(() => {
      setPresentationMode(new URLSearchParams(window.location.search).get("presentation") === "true");
      setCopilotUnread(Boolean(readStoredThread()?.unread_count));
    });
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!copilotOpen) setCopilotUnread(Boolean(readStoredThread()?.unread_count));
    }, 700);
    return () => window.clearInterval(timer);
  }, [copilotOpen]);

  const load = useCallback(async () => {
    try {
      const next = await getDashboard();
      setData(next);
      setSavedStories(new Set(next.daily_state.saved_story_ids));
      setSavedEvents(new Set(next.daily_state.saved_event_ids));
      setError(null);
      return next;
    } catch {
      setError("Your latest dashboard could not be loaded. Please try again.");
      return null;
    }
  }, []);

  const beginRefresh = useCallback(async () => {
    if (refreshStarted.current) return;
    refreshStarted.current = true;
    try {
      await requestRefresh();
      await load();
    } catch {
      refreshStarted.current = false;
    }
  }, [load]);

  useEffect(() => {
    let active = true;
    void getDashboard()
      .then((loaded) => {
        if (!active) return;
        setData(loaded);
        setSavedStories(new Set(loaded.daily_state.saved_story_ids));
        setSavedEvents(new Set(loaded.daily_state.saved_event_ids));
        setError(null);
        void beginRefresh();
      })
      .catch(() => {
        if (active) setError("Your latest dashboard could not be loaded. Please try again.");
      });
    return () => { active = false; };
  }, [beginRefresh, load]);

  const loadFinancialDay = useCallback(async () => {
    try {
      const next = await getFinancialDay();
      const incoming = new Set(next.events_alerted.map((item) => item.event.event_id));
      const newlyAlerted = [...incoming].some((id) => !alertedEventIds.current.has(id));
      if (presentationMode && newlyAlerted) {
        setToast(null);
        setProactiveAlert(true);
        setSignalNotice("New signal detected");
        void load();
      }
      alertedEventIds.current = incoming;
      setFinancialDay(next);
      return next;
    } catch {
      return null;
    }
  }, [load, presentationMode]);

  useEffect(() => {
    let active = true;
    void getFinancialDay()
      .then((next) => {
        if (!active) return;
        alertedEventIds.current = new Set(next.events_alerted.map((item) => item.event.event_id));
        setFinancialDay(next);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const loadPresentationClock = useCallback(async () => {
    try {
      const next = await getPresentationClock();
      setPresentationClock(next);
      return next;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    if (!presentationMode) return;
    const initial = window.setTimeout(() => void loadPresentationClock(), 0);
    const timer = window.setInterval(() => void loadPresentationClock(), 500);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [loadPresentationClock, presentationMode]);

  useEffect(() => {
    if (financialDay?.status !== "running") return;
    const timer = window.setInterval(() => void loadFinancialDay(), 1000);
    return () => window.clearInterval(timer);
  }, [financialDay?.status, loadFinancialDay]);

  useEffect(() => {
    if (!data || !["queued", "running"].includes(data.refresh.phase)) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [data, load]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!signalNotice) return;
    const timer = window.setTimeout(() => setSignalNotice(null), 3200);
    return () => window.clearTimeout(timer);
  }, [signalNotice]);

  useEffect(() => {
    const target = inlineCopilotRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => setInlineCopilotVisible(entry.isIntersecting),
      { threshold: 0.1 },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [data]);

  if (!data && !error) return <DashboardSkeleton />;
  if (!data) {
    return (
      <main className="dashboard-shell"><div className="error-card"><CircleAlert /><h1>We couldn&apos;t open Wealth Copilot</h1><p>{error}</p><button className="primary-button" onClick={() => void load()}>Try again</button></div></main>
    );
  }

  const event = data.important_event;
  const presentationMinute = presentationMode ? clockMinute(presentationClock?.current_time) : Number.POSITIVE_INFINITY;
  const eventReleased = !presentationMode || presentationMinute >= 12 * 60 + 17;
  const eveningReleased = !presentationMode || presentationMinute >= 20 * 60;
  const storyReleased = !presentationMode || presentationMinute >= 21 * 60 + 1;
  const visibleAttentionCount = data.attention_summary?.high_priority_count ?? data.attention_count;
  const activityItems = (financialDay?.timeline ?? [])
    .filter((step) => step.status === "complete" && (!presentationMode || clockMinute(presentationClock?.current_time) >= clockMinute(step.scheduled_time)))
    .map((step) => ({
      time: step.scheduled_time,
      title: step.step_id === "event" && eventReleased ? `${event.event.company ?? "Market"} deserves attention` : `${step.label} ready`,
      detail: step.detail,
      alert: step.step_id === "event" && eventReleased && event.notification_required,
    }));
  const refreshing = ["queued", "running"].includes(data.refresh.phase);
  const openCopilot = (target: CopilotTarget, mode: "explain" | "chat" | "research", message: string) => {
    interactionKey.current += 1;
    setCopilotOpen(true);
    setCopilotRequest({ key: interactionKey.current, target, mode, message });
  };

  const restoreCopilot = () => {
    const stored = readStoredThread();
    const target: CopilotTarget = stored?.target ? {
      type: stored.target.type === "story" || stored.target.type === "event" ? stored.target.type : "dashboard",
      id: stored.target.id,
      title: stored.target.title ?? "Ask Wealth Copilot",
    } : { type: "dashboard", title: "Ask Wealth Copilot" };
    interactionKey.current += 1;
    setCopilotUnread(false);
    setCopilotOpen(true);
    setCopilotRequest({ key: interactionKey.current, target, mode: "chat", message: "" });
  };
  const saveStory = async (id: string) => {
    try {
      await saveStoryForEvening(id);
      setSavedStories((current) => new Set(current).add(id));
      setToast("Saved for your evening brief");
    } catch {
      setToast("This story could not be saved right now");
    }
  };
  const saveHero = async () => {
    try {
      await saveEventAction(event.event.event_id, "save_for_evening");
      setSavedEvents((current) => new Set(current).add(event.event.event_id));
      setToast("Important event saved for this evening");
    } catch {
      setToast("This event could not be saved right now");
    }
  };
  const askGlobal = (submitEvent: FormEvent) => {
    submitEvent.preventDefault();
    const message = globalQuestion.trim();
    if (!message) return;
    setGlobalQuestion("");
    openCopilot({ type: "dashboard", title: "Ask Wealth Copilot" }, "chat", message);
  };
  const controlClock = async (operation: () => Promise<PresentationClockState>, success?: string) => {
    setClockControlling(true);
    try {
      const next = await operation();
      setPresentationClock(next);
      await loadFinancialDay();
      if (success) setToast(success);
    } catch {
      setToast("The financial day control is temporarily unavailable");
    } finally {
      setClockControlling(false);
    }
  };

  const toggleClock = () => void controlClock(
    presentationClock?.status === "running" ? pausePresentationClock : playPresentationClock,
  );

  const restartClock = () => void controlClock(async () => {
    const next = await restartPresentationClock();
    alertedEventIds.current = new Set();
    setProactiveAlert(false);
    return next;
  });

  const importantEventSection = event.decision === "IGNORE" ? (
    <section id="important-event" className="hero-event hero-event--quiet" aria-labelledby="hero-event-title" data-testid="quiet-market-state">
      <div className="event-accent" />
      <div className="event-header">
        <div className="event-label"><Check size={15} /> No interruption needed <span>QUIET</span></div>
        <span className="event-time">Checked {formatTime(event.event.timestamp)}</span>
      </div>
      <div className="event-content">
        <div className="event-main">
          <span className="eyebrow">Market state</span>
          <h2 id="hero-event-title">Nothing needs your attention right now</h2>
          <p>{event.reason}</p>
        </div>
        <div className="event-stats">
          <div><span>Portfolio alerts</span><strong>0</strong></div>
          <div><span>Relevance</span><strong>{event.relevance_score.toFixed(2)}</strong></div>
        </div>
      </div>
    </section>
  ) : (
    <section id="important-event" className="hero-event" aria-labelledby="hero-event-title" data-testid="hero-event">
      <div className="event-accent" />
      <div className="event-header">
        <div className="event-label"><BellRing size={15} /> Important event <span>{event.decision}</span></div>
        <span className="event-time">Detected {formatTime(event.event.timestamp)}</span>
      </div>
      <div className="event-content">
        <div className="event-main">
          <span className="eyebrow">Something unusual is happening</span>
          <h2 id="hero-event-title">{event.event.company}</h2>
          <div className="event-move"><TrendingDown size={26} /><strong>{event.event.price_change_pct?.toFixed(1)}%</strong><span>while its sector is {event.event.sector_change_pct?.toFixed(1)}%</span></div>
          <p>{event.reason}</p>
          <div className="event-actions">
            <button className="primary-button" onClick={() => openCopilot({ type: "event", id: event.event.event_id, title: event.title }, "explain", "Why does this event matter to me?")}><Sparkles size={15} />Explain</button>
            <button className="secondary-button" onClick={() => openCopilot({ type: "event", id: event.event.event_id, title: event.title }, "research", "Research this event more deeply.")}>Learn more <ArrowUpRight size={15} /></button>
            <button className="secondary-button" onClick={() => setAdvisorTarget({ type: "event", id: event.event.event_id, title: event.title })} data-testid="ask-advisor-event"><UserRoundCheck size={15} /> Ask advisor</button>
            <button className="secondary-button" onClick={() => void saveHero()}><Bookmark size={15} /> {savedEvents.has(event.event.event_id) ? "Saved for evening" : "Save for evening"}</button>
          </div>
        </div>
        <div className="event-stats">
          <div><span>Your exposure</span><strong>{event.affected_portfolio_percentage.toFixed(2)}%</strong></div>
          <div><span>Sector exposure</span><strong>{event.sector_exposure_percentage.toFixed(2)}%</strong></div>
          <div><span>Relevance</span><strong>{event.relevance_score.toFixed(2)}</strong></div>
        </div>
      </div>
    </section>
  );

  return (
    <div className="app-background">
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="#top" aria-label="Wealth Copilot home">
            <span className="brand-mark"><Sparkles size={18} /></span>
            <span>Wealth Copilot</span>
          </a>
          <div className="header-status">
            <span className={freshnessClass(data.daily_brief.freshness.status)}>
              <span className="status-dot" /> {freshnessLabel(data.daily_brief.freshness.status, data.daily_brief.freshness.fetched_at)}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh market intelligence in background"
              title="Refresh in background"
              disabled={refreshing}
              onClick={() => { refreshStarted.current = false; void beginRefresh(); }}
            >
              <RefreshCw size={16} className={refreshing ? "spin" : ""} />
            </button>
            <button
              className={`icon-button activity-trigger ${proactiveAlert ? "has-alert" : ""}`}
              aria-label="Open Activity and Alerts"
              title="Activity and alerts"
              onClick={() => setActivityOpen((open) => !open)}
            >
              <BellRing size={16} />
              {proactiveAlert && <span className="activity-trigger__badge">1</span>}
            </button>
          </div>
        </div>
      </header>
      {activityOpen && (
        <aside className="activity-drawer" aria-label="Activity and Alerts" data-testid="activity-drawer">
          <div className="activity-drawer__header"><div><span className="eyebrow">Today</span><h2>Activity &amp; Alerts</h2></div><button className="icon-button" aria-label="Close Activity and Alerts" onClick={() => setActivityOpen(false)}>×</button></div>
          <div className="activity-drawer__list">
            {!activityItems.length && <p className="activity-drawer__empty">Morning Pulse will appear here as the financial day unfolds.</p>}
            {activityItems.map((item) => <article className={item.alert ? "is-alert" : ""} key={`${item.time}-${item.title}`}><time>{item.time}</time><div><strong>{item.title}</strong><span>{item.detail}</span>{item.alert && <a href="#important-event" onClick={() => setActivityOpen(false)}>View event</a>}</div></article>)}
          </div>
        </aside>
      )}

      <main className="dashboard" id="top">
        <section className="intro" aria-labelledby="attention-title">
          <div>
            <span className="eyebrow">{data.greeting}</span>
            <h1 id="attention-title" key={visibleAttentionCount}>{attentionMessage(visibleAttentionCount)}</h1>
            <p>{visibleAttentionCount} high-priority signals from {data.daily_brief.stories.length} portfolio-relevant stories.</p>
            <AudioBriefControl type="morning" />
          </div>
          <div className="attention-orbit" aria-hidden="true">
            <span key={visibleAttentionCount} className="attention-orbit__count">{visibleAttentionCount}</span><small>signals</small>
          </div>
        </section>

        {signalNotice && <div className="signal-notice" role="status"><BellRing size={13} /> {signalNotice}</div>}

        <form ref={inlineCopilotRef} className="global-copilot" onSubmit={askGlobal} data-testid="global-copilot">
          <span className="global-copilot__icon"><MessageCircle size={19} /></span>
          <div className="global-copilot__copy"><strong>Ask Wealth Copilot</strong><span>Portfolio context, explained.</span></div>
          <input value={globalQuestion} onChange={(inputEvent) => setGlobalQuestion(inputEvent.target.value)} placeholder="What should I understand today?" aria-label="Ask Wealth Copilot" />
          <button type="submit" aria-label="Send to Wealth Copilot" disabled={!globalQuestion.trim()}><Send size={16} /></button>
        </form>

        {eventReleased && event.decision !== "IGNORE" && importantEventSection}

        <section className="summary-grid" aria-label="Portfolio snapshot">
          <article className="panel portfolio-panel">
            <div className="panel-heading">
              <div><span className="eyebrow">Portfolio snapshot</span><h2>{compactInr.format(data.portfolio.portfolio_value)}</h2></div>
              <div className="panel-icon"><WalletCards size={20} /></div>
            </div>
            <div className="portfolio-meta">
              <span className="source-badge"><ShieldCheck size={13} /> {data.portfolio.source.label}</span>
              {presentationMode && data.portfolio.source.checkpoint && (
                <span className="source-badge">
                  <Clock3 size={12} /> {formatMarketClock(data.portfolio.source.checkpoint)}
                </span>
              )}
              {data.portfolio.day_change_pct !== null && (
                <span className={data.portfolio.day_change_pct >= 0 ? "positive" : "negative"}>
                  {data.portfolio.day_change_pct >= 0 ? "+" : ""}{data.portfolio.day_change_pct.toFixed(2)}% today
                </span>
              )}
            </div>
            <div className="holdings-list">
              {data.portfolio.largest_holdings.map((holding) => (
                <div className="holding-row" key={holding.symbol}>
                  <div><strong>{holding.symbol}</strong><span>{holding.portfolio_weight.toFixed(2)}% of portfolio</span></div>
                  <div className="holding-value"><strong>{compactInr.format(holding.market_value)}</strong><span className={(holding.day_change_pct ?? 0) >= 0 ? "positive" : "negative"}>{holding.day_change_pct !== null ? `${holding.day_change_pct >= 0 ? "+" : ""}${holding.day_change_pct.toFixed(2)}%` : "—"}</span></div>
                </div>
              ))}
            </div>
          </article>

          <article className="panel sector-panel">
            <div className="panel-heading">
              <div><span className="eyebrow">Exposure map</span><h2>By sector</h2></div>
              <div className="panel-icon panel-icon--mint"><Landmark size={20} /></div>
            </div>
            <div className="sector-list">
              {data.portfolio.sector_exposure.map((sector, index) => (
                <div className="sector-row" key={sector.sector}>
                  <div><span>{sector.sector}</span><strong>{sector.portfolio_weight.toFixed(1)}%</strong></div>
                  <div className="bar-track"><span className={`bar-fill bar-fill--${(index % 4) + 1}`} style={{ width: `${sector.portfolio_weight}%` }} /></div>
                </div>
              ))}
            </div>
          </article>
        </section>

        {!eventReleased ? (
          <section id="important-event" className="hero-event hero-event--quiet" aria-labelledby="hero-event-title" data-testid="pre-event-monitoring">
            <div className="event-accent" />
            <div className="event-header">
              <div className="event-label"><Clock3 size={15} /> Monitoring your portfolio <span>WATCHING</span></div>
              <span className="event-time">Next market watch at 12:17 PM</span>
            </div>
            <div className="event-content">
              <div className="event-main">
                <span className="eyebrow">Market state</span>
                <h2 id="hero-event-title">No portfolio event needs your attention yet</h2>
                <p>Wealth Copilot is monitoring your holdings and will surface a material change when it occurs.</p>
              </div>
              <div className="event-stats">
                <div><span>Portfolio alerts</span><strong>0</strong></div>
                <div><span>Relevance</span><strong>—</strong></div>
              </div>
            </div>
          </section>
        ) : event.decision === "IGNORE" ? importantEventSection : null}

        <div className="content-grid">
          <section className="brief-section" aria-labelledby="brief-title">
            <div className="section-heading">
              <div><span className="eyebrow">Personalized daily brief</span><h2 id="brief-title">What matters today</h2></div>
              <div className="brief-meta"><span className={freshnessClass(data.daily_brief.freshness.status)}><span className="status-dot" /> {freshnessLabel(data.daily_brief.freshness.status, data.daily_brief.freshness.fetched_at)}</span><small>{data.daily_brief.analyzed_count} stories analyzed</small></div>
            </div>
            <div className="story-list">
              {data.daily_brief.stories.map((story, index) => (
                <StoryCard key={story.id} story={story} index={index} saved={savedStories.has(story.id)} onExplain={() => openCopilot({ type: "story", id: story.id, title: story.headline }, "explain", "Why am I seeing this story?")} onResearch={() => openCopilot({ type: "story", id: story.id, title: story.headline }, "research", "Research this story more deeply.")} onAskAdvisor={() => setAdvisorTarget({ type: "story", id: story.id, title: story.headline })} onSave={() => void saveStory(story.id)} />
              ))}
            </div>
          </section>

          <aside className="activity-column" aria-labelledby="activity-title">
            <FinancialDayPanel
              day={financialDay}
              clock={presentationClock}
              controlling={clockControlling}
              onPlayPause={toggleClock}
              onAdvance={() => void controlClock(() => advancePresentationClock(60))}
              onNext={() => void controlClock(advancePresentationClockToNext)}
              onRestart={restartClock}
              presentation={presentationMode}
            />
            <section className="panel activity-panel">
              <div className="panel-heading"><div><span className="eyebrow">Agent activity</span><h2 id="activity-title">Why it surfaced</h2></div><div className="panel-icon panel-icon--mint"><Sparkles size={20} /></div></div>
              <div className="trace-list">
                {(presentationMode && !eventReleased ? data.agent_activity.filter((item) => !/event|investigat|alert|decision|relevance/i.test(`${item.stage} ${item.label} ${item.detail}`)) : data.agent_activity).map((item, index, visibleActivity) => (
                  <div className="trace-item" key={item.stage}>
                    <div className={`trace-check ${item.status === "attention" ? "trace-check--attention" : ""}`}>{item.status === "attention" ? <BellRing size={13} /> : <Check size={13} />}</div>
                    <div><strong>{item.label}</strong><span>{item.detail}</span></div>
                    {index < visibleActivity.length - 1 && <div className="trace-line" />}
                  </div>
                ))}
              </div>
              <div className="agent-summary"><Sparkles size={15} /><p>The agent checked {data.portfolio.holdings_count} holdings and analyzed {data.daily_brief.analyzed_count} market stories. {!eventReleased ? "No event has crossed the interruption threshold yet." : event.notification_required ? "One event deserves attention." : event.decision === "IGNORE" ? "No event crossed the interruption threshold." : "One event is being monitored."}</p></div>
            </section>

            <section className="panel update-panel">
              <div className="update-icon">{refreshing ? <LoaderCircle className="spin" /> : <Clock3 />}</div>
              <div><span className="eyebrow">Market update</span><h3>{refreshing ? "Refreshing quietly" : data.daily_brief.freshness.label}</h3><p>{data.refresh.message}</p></div>
            </section>

            <section className="panel evening-panel">
              <div><span className="eyebrow">Evening Wealth Wrap</span><h3>{eveningReleased ? "Your financial day in 90 seconds" : "Available this evening"}</h3><p>{eveningReleased ? "Includes anything you saved to revisit." : "The wrap will be prepared after market close."}</p></div>
              {eveningReleased && <AudioBriefControl type="evening" compact />}
            </section>
            <WealthStoryControl story={storyReleased ? financialDay?.daily_story ?? null : null} ready={storyReleased && financialDay?.status === "complete"} />
          </aside>
        </div>

        <footer>
          <div className="footer-brand"><span className="brand-mark"><Sparkles size={14} /></span> Wealth Copilot</div>
          <p>{data.disclaimer}</p>
        </footer>
      </main>
      {proactiveAlert && (
        <div className="toast toast--attention" role="alert" data-testid="proactive-event-alert">
          <BellRing size={18} />
          <div>
            <strong>Wealth Copilot found something that deserves attention</strong>
            <span>HDFC Bank is moving materially differently from its sector.</span>
          </div>
          <a href="#important-event" onClick={() => setProactiveAlert(false)}>View</a>
          <button type="button" onClick={() => setProactiveAlert(false)} aria-label="Dismiss alert">×</button>
        </div>
      )}
      {toast && <div className="toast" role="status"><Check size={15} /> {toast}</div>}
      {copilotOpen ? (
        <CopilotSheet request={copilotRequest} onClose={() => { setCopilotOpen(false); setCopilotRequest(null); }} />
      ) : !inlineCopilotVisible ? (
        <button
          type="button"
          className="copilot-launcher copilot-launcher--visible"
          aria-label="Open Wealth Copilot"
          title="Open Wealth Copilot"
          onClick={restoreCopilot}
        >
          <MessageCircle size={20} />
          {copilotUnread ? <span className="copilot-launcher__badge">1</span> : readStoredThread() && <span className="copilot-launcher__badge">Resume</span>}
        </button>
      ) : null}
      <AdvisorSheet key={advisorTarget ? `${advisorTarget.type}-${advisorTarget.id}` : "advisor-closed"} target={advisorTarget} onClose={() => setAdvisorTarget(null)} />
    </div>
  );
}
