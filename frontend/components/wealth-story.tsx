"use client";

import {
  ArrowLeft,
  ArrowRight,
  Check,
  Film,
  LoaderCircle,
  Pause,
  Play,
  Sparkles,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { CSSProperties, useEffect, useRef, useState } from "react";

import { getDailyWealthStory, getStoryNarration, startStoryNarration, storySceneAudioUrl } from "@/lib/api";
import type { DailyWealthStory, StoryNarration } from "@/lib/types";


export function WealthStoryControl({ story, ready }: { story: DailyWealthStory | null; ready: boolean }) {
  const [generated, setGenerated] = useState<DailyWealthStory | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [narration, setNarration] = useState<StoryNarration | null>(null);
  const [muted, setMuted] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const generatedMatchesStory = generated && story
    ? generated.story_id === story.story_id && generated.day_id === story.day_id && generated.run_id === story.run_id
    : Boolean(generated);
  const resolved = generatedMatchesStory ? generated : story;
  const resolvedStoryId = resolved?.story_id;
  const resolvedActive = resolved ? Math.min(active, Math.max(0, resolved.scenes.length - 1)) : 0;
  const scene = resolved?.scenes[resolvedActive];
  const currentNarration = narration?.story_id === resolved?.story_id ? narration : null;
  const currentNarrationStatus = currentNarration?.status;
  const narratedScene = currentNarration?.scenes.find((item) => item.scene_id === scene?.scene_id);
  const displayDuration = currentNarration?.total_duration_seconds ?? resolved?.duration_seconds;

  useEffect(() => {
    if (!open || !resolvedStoryId) return;
    void getStoryNarration(resolvedStoryId).then(setNarration).catch(() => undefined);
  }, [open, resolvedStoryId]);

  useEffect(() => {
    if (!open || !currentNarrationStatus || !["queued", "generating"].includes(currentNarrationStatus)) return;
    const timer = window.setInterval(() => {
      if (resolvedStoryId) void getStoryNarration(resolvedStoryId).then(setNarration).catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [open, currentNarrationStatus, resolvedStoryId]);

  useEffect(() => {
    if (!audioRef.current) return;
    audioRef.current.muted = muted;
    if (playing) void audioRef.current.play().catch(() => undefined);
    else audioRef.current.pause();
  }, [active, muted, playing, narratedScene?.audio_url]);

  useEffect(() => {
    if (!open || !playing || !resolved || !scene || currentNarrationStatus !== "fallback") return;
    const timer = window.setTimeout(() => {
      setActive((index) => {
        if (index >= resolved.scenes.length - 1) {
          setPlaying(false);
          return index;
        }
        return index + 1;
      });
    }, scene.duration_seconds * 1000);
    return () => window.clearTimeout(timer);
  }, [open, playing, resolved, scene, currentNarrationStatus]);

  const watch = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = resolved ?? await getDailyWealthStory();
      setGenerated(next);
      setNarration(await startStoryNarration());
      setActive(0);
      setPlaying(true);
      setMuted(false);
      setOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Your visual recap is not ready yet.");
    } finally {
      setBusy(false);
    }
  };

  const jump = (index: number) => {
    if (!resolved) return;
    setActive(Math.max(0, Math.min(index, resolved.scenes.length - 1)));
    setPlaying(true);
  };

  const advance = () => {
    if (!resolved) return;
    setActive((index) => {
      if (index >= resolved.scenes.length - 1) {
        setPlaying(false);
        return index;
      }
      return index + 1;
    });
  };

  return (
    <>
      <section className="panel wealth-story-card" data-testid="wealth-story-card">
        <span className="wealth-story-card__icon"><Film size={18} /></span>
        <div><span className="eyebrow">Your financial day</span><h3>{resolved ? `Your financial day · ${Math.round(displayDuration ?? resolved.duration_seconds)} sec` : "Visual recap"}</h3><p>{resolved ? `${resolved.scenes.length} moments from what shaped your portfolio` : "Ready automatically when your financial day finishes."}</p>{error && <small>{error}</small>}</div>
        {ready || resolved ? <button className="primary-button" onClick={() => void watch()} disabled={busy} data-testid="watch-wealth-story">
          {busy ? <LoaderCircle className="spin" /> : <Play size={14} fill="currentColor" />} Watch
        </button> : <span className="wealth-story-card__availability">Available when today&apos;s financial day is complete.</span>}
      </section>

      {open && resolved && scene && (
        <div className="wealth-story-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
          <section className={`wealth-story-player wealth-story-player--${scene.kind}`} role="dialog" aria-modal="true" aria-labelledby="wealth-story-title" data-testid="wealth-story-player">
            <header className="wealth-story-player__top">
              <span><Sparkles size={15} /> Wealth Copilot</span>
              <button aria-label="Close visual recap" onClick={() => setOpen(false)}><X size={17} /></button>
            </header>
              <div className="wealth-story-progress" aria-label={`Scene ${resolvedActive + 1} of ${resolved.scenes.length}`}>
              {resolved.scenes.map((item, index) => (
                <span className={index < resolvedActive ? "is-complete" : index === resolvedActive ? "is-active" : ""} key={item.scene_id}>
                  <i style={{ "--scene-duration": `${currentNarration?.scenes.find((audio) => audio.scene_id === item.scene_id)?.actual_duration_seconds ?? item.duration_seconds}s` } as CSSProperties} />
                </span>
              ))}
            </div>
            <div className="wealth-story-scene" key={scene.scene_id}>
              <span className="wealth-story-scene__count">{String(resolvedActive + 1).padStart(2, "0")} / {String(resolved.scenes.length).padStart(2, "0")}</span>
              <div className="wealth-story-scene__content">
                <span className="eyebrow">{scene.eyebrow}</span>
                <h2 id="wealth-story-title">{scene.title}</h2>
                {scene.primary_value && <strong>{scene.primary_value}</strong>}
                {scene.secondary_text && <h3>{scene.secondary_text}</h3>}
                {scene.detail && <p>{scene.detail}</p>}
              </div>
              <div className="wealth-story-accuracy"><Check size={13} /> Based on today&apos;s portfolio and market context</div>
              {currentNarration && currentNarration.status !== "ready" && <small className="wealth-story-narration-state">{currentNarration.message}</small>}
              {narratedScene?.audio_url && (
                <audio
                  key={narratedScene.scene_id}
                  ref={audioRef}
                  src={storySceneAudioUrl(narratedScene.audio_url)}
                  muted={muted}
                  autoPlay={playing}
                  onEnded={advance}
                />
              )}
            </div>
            <footer className="wealth-story-player__controls">
              <button onClick={() => jump(resolvedActive - 1)} disabled={resolvedActive === 0} aria-label="Previous scene"><ArrowLeft size={16} /></button>
              <button className="wealth-story-play" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause recap" : "Play recap"}>{playing ? <Pause size={17} /> : <Play size={17} fill="currentColor" />}</button>
              <button onClick={() => jump(resolvedActive + 1)} disabled={resolvedActive === resolved.scenes.length - 1} aria-label="Next scene"><ArrowRight size={16} /></button>
              <button onClick={() => setMuted((value) => !value)} aria-label={muted ? "Unmute narration" : "Mute narration"}>{muted ? <VolumeX size={16} /> : <Volume2 size={16} />}</button>
            </footer>
          </section>
        </div>
      )}
    </>
  );
}
