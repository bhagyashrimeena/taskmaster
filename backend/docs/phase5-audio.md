# Phase 5 — Morning Pulse and Evening Wealth Wrap

Phase 5 is a presentation layer over the existing structured dashboard intelligence. It does not ask the TTS model to select stories or make financial conclusions.

```text
Dashboard + daily state
        ↓
deterministic script builder
        ↓
approved, validated transcript
        ↓
Gemini 3.1 Flash TTS on Vertex AI
        ↓
cached 24 kHz mono WAV
```

## Briefs

- **Morning Pulse:** important event plus the three highest-ranked personalized stories, targeting 60–90 seconds.
- **Evening Wealth Wrap:** important event, portfolio context, and saved-for-evening items. If nothing was saved, it uses the two highest-ranked stories.

Every `AudioBrief` records the brief type, script sections, approved transcript, generation and source-snapshot times, duration target, estimated/actual duration, voice/model, freshness, used story/event IDs, cache status, audio URL, and complete text fallback.

## Media Agent

The Media Agent is a thin TaskMaster specialist with four tools:

- `create_morning_script()`
- `create_evening_script()`
- `generate_audio(brief_type)`
- `get_audio_status(brief_id)`

The web API calls the deterministic media service directly so playback never adds an unnecessary TaskMaster turn. Conversational requests can still route through TaskMaster to the same Media Agent.

## API

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/api/v1/audio/{morning|evening}` | Returns text and current cache status; never generates audio |
| `POST` | `/api/v1/audio/{morning|evening}/generate` | Queues generation or returns the cached artifact |
| `GET` | `/api/v1/audio/{brief_id}/status` | Polls generation status and text fallback |
| `GET` | `/api/v1/audio/{brief_id}/file` | Serves immutable `audio/wav` when ready |

Generation is non-blocking and coalesced by brief ID. Cache identity is based on the approved script and used story/event IDs, so a freshness timestamp alone does not regenerate identical audio. Metadata and WAV files live under `backend/.cache/audio`. Interrupted generation recovers to `text_ready` after restart.

## TTS configuration

```env
TTS_MODEL=gemini-3.1-flash-tts-preview
TTS_VOICE=Kore
TTS_LANGUAGE_CODE=en-IN
```

Vertex returns 24 kHz, 16-bit mono PCM. The provider wraps it in a WAV header before caching and serving it. The model receives delivery instructions plus the exact approved transcript and is explicitly told not to add commentary.

The implementation follows Google's current Gemini-TTS Vertex AI contract: https://docs.cloud.google.com/text-to-speech/docs/gemini-tts

## Failure behavior

Any provider, quota, safety, or file error changes the brief to `fallback`. The dashboard stays usable and exposes the complete structured transcript. A later explicit listen request can retry generation.
