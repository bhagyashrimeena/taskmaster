"""FastAPI surface for dashboard, interactions, media, and the financial day."""

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .advisor.schemas import (
    AdvisorCase,
    AdvisorProfile,
    CreateAdvisorPacketRequest,
    SendAdvisorPacketRequest,
)
from .advisor.service import advisor_service

from .agents.event_watcher import save_event_action
from .dashboard.schemas import (
    DashboardResponse,
    EventActionRequest,
    EventActionResponse,
    RefreshView,
)
from .dashboard.service import dashboard_service
from .interaction.context import resolve_surface_context
from .interaction.memory import daily_interaction_store
from .interaction.research_jobs import research_job_manager
from .interaction.schemas import (
    ConversationRequest,
    ConversationResponse,
    FeedbackRequest,
    FeedbackResponse,
    ResearchJob,
    ResearchRequest,
    SaveStoryResponse,
)
from .interaction.service import interaction_service
from .media.schemas import AudioBrief, AudioBriefType, AudioGenerationResponse
from .media.service import media_service
from .day.orchestrator import day_orchestrator
from .day.presentation import (
    PresentationAdvanceRequest,
    PresentationClockState,
    presentation_clock,
)
from .day.scheduler import day_scheduler
from .day.schemas import FinancialDayState
from .day.store import financial_day_store
from .story.schemas import DailyWealthStory, StoryNarration
from .story.narration import story_narration_service
from .story.service import daily_story_service
from .events import daily_event_store
from .market.cache import news_candidate_cache
from .simulation import AdvanceSimulationRequest, SimulationState, simulation_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    day_scheduler.start()
    await day_orchestrator.recover_interrupted_demo()
    yield
    await presentation_clock.stop()
    await day_scheduler.stop()


app = FastAPI(
    title="Wealth Copilot API",
    version="0.9.1",
    description="Provider-neutral portfolio intelligence and TaskMaster interactions.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/simulation", response_model=SimulationState)
async def simulation_state() -> SimulationState:
    return simulation_service.state()


@app.post("/api/v1/simulation/scenarios/{scenario_id}", response_model=SimulationState)
async def load_simulation_scenario(scenario_id: str) -> SimulationState:
    try:
        state = simulation_service.load_scenario(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    news_candidate_cache.clear()
    daily_event_store.clear()
    financial_day_store.clear()
    return state


@app.post("/api/v1/simulation/reset", response_model=SimulationState)
async def reset_simulation() -> SimulationState:
    news_candidate_cache.clear()
    daily_event_store.clear()
    financial_day_store.clear()
    return simulation_service.reset_scenario()


@app.post("/api/v1/simulation/advance", response_model=SimulationState)
async def advance_simulation(request: AdvanceSimulationRequest) -> SimulationState:
    try:
        return simulation_service.advance_to(request.checkpoint)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    """Return immediately from the latest retained or deterministic data."""

    return await dashboard_service.get_dashboard()


@app.post("/api/v1/dashboard/refresh", response_model=RefreshView, status_code=202)
async def refresh_dashboard() -> RefreshView:
    """Enqueue a refresh without holding the page response open for Search."""

    return await dashboard_service.start_refresh()


@app.post(
    "/api/v1/events/{event_id}/actions", response_model=EventActionResponse
)
async def event_action(
    event_id: str, request: EventActionRequest
) -> EventActionResponse:
    result = EventActionResponse.model_validate(save_event_action(event_id, request.action))
    if result.saved and request.action == "save_for_evening":
        daily_interaction_store.save_event(event_id)
        financial_day_store.update(
            lambda state: state.saved_events.append(event_id)
            if event_id not in state.saved_events
            else None
        )
    return result


@app.post("/api/v1/chat", response_model=ConversationResponse)
async def chat(request: ConversationRequest) -> ConversationResponse:
    """Ask the real TaskMaster with retained dashboard context and history."""

    try:
        return await interaction_service.respond(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/research", response_model=ResearchJob, status_code=202)
async def start_research(request: ResearchRequest) -> ResearchJob:
    """Queue deeper Research Agent work without blocking the dashboard."""

    try:
        await resolve_surface_context(
            story_id=request.active_story_id, event_id=request.active_event_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return research_job_manager.start(request)


@app.get("/api/v1/research/{job_id}", response_model=ResearchJob)
async def research_status(job_id: str) -> ResearchJob:
    job = research_job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown research job")
    return job


@app.post("/api/v1/stories/{story_id}/save", response_model=SaveStoryResponse)
async def save_story(story_id: str) -> SaveStoryResponse:
    try:
        await resolve_surface_context(story_id=story_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    today = date.today()
    daily_interaction_store.save_story(story_id, today)
    financial_day_store.update(
        lambda state: state.saved_stories.append(story_id)
        if story_id not in state.saved_stories
        else None,
        today,
    )
    return SaveStoryResponse(story_id=story_id, saved=True, saved_for=today)


@app.get("/api/v1/advisor/profile", response_model=AdvisorProfile)
async def advisor_profile() -> AdvisorProfile:
    return advisor_service.profile()


@app.post("/api/v1/advisor/packets", response_model=AdvisorCase, status_code=201)
async def create_advisor_packet(request: CreateAdvisorPacketRequest) -> AdvisorCase:
    """Create a draft only from intelligence that is already retained."""

    try:
        return await advisor_service.create(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/advisor/packets/{request_id}/ready", response_model=AdvisorCase)
async def ready_advisor_packet(request_id: str) -> AdvisorCase:
    """Record that the exact recipient and email draft were reviewed."""

    try:
        return advisor_service.ready(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/advisor/packets/{request_id}/send", response_model=AdvisorCase)
async def send_advisor_packet(
    request_id: str, request: SendAdvisorPacketRequest
) -> AdvisorCase:
    """Deliver only after a distinct, explicit confirmation."""

    try:
        return advisor_service.send(request_id, confirmed=request.confirmed)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/advisor/packets/{request_id}", response_model=AdvisorCase)
async def advisor_packet_status(request_id: str) -> AdvisorCase:
    try:
        return advisor_service.get(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/day", response_model=FinancialDayState)
async def current_financial_day() -> FinancialDayState:
    """Return the crash-safe state accumulated by today's operations."""

    return day_orchestrator.current_state()


@app.get("/api/v1/day/{trading_date}", response_model=FinancialDayState)
async def financial_day(trading_date: date) -> FinancialDayState:
    return financial_day_store.get(trading_date)


@app.post("/api/v1/day/demo", response_model=FinancialDayState, status_code=202)
async def run_demo_day() -> FinancialDayState:
    """Start the 60–90 second judge-friendly day without blocking the request."""

    return await day_orchestrator.start_demo_day()


@app.get("/api/v1/presentation-clock", response_model=PresentationClockState)
async def presentation_clock_state() -> PresentationClockState:
    """Return the accelerated clock used only by the presentation surface."""

    return presentation_clock.state()


@app.post(
    "/api/v1/presentation-clock/play",
    response_model=PresentationClockState,
    status_code=202,
)
async def play_presentation_clock() -> PresentationClockState:
    return await presentation_clock.play()


@app.post("/api/v1/presentation-clock/pause", response_model=PresentationClockState)
async def pause_presentation_clock() -> PresentationClockState:
    return await presentation_clock.pause()


@app.post(
    "/api/v1/presentation-clock/advance",
    response_model=PresentationClockState,
    status_code=202,
)
async def advance_presentation_clock(
    request: PresentationAdvanceRequest,
) -> PresentationClockState:
    return await presentation_clock.advance(request.minutes)


@app.post(
    "/api/v1/presentation-clock/next",
    response_model=PresentationClockState,
    status_code=202,
)
async def advance_presentation_clock_to_next() -> PresentationClockState:
    return await presentation_clock.advance_to_next()


@app.post("/api/v1/presentation-clock/restart", response_model=PresentationClockState)
async def restart_presentation_clock() -> PresentationClockState:
    return await presentation_clock.restart()


@app.post("/api/v1/day/steps/{step_id}", response_model=FinancialDayState)
async def run_day_step(step_id: str) -> FinancialDayState:
    operations = {
        "morning": day_orchestrator.run_morning_pulse,
        "health": day_orchestrator.run_portfolio_health,
        "event": day_orchestrator.handle_market_event,
        "close": day_orchestrator.run_market_close,
        "evening": day_orchestrator.run_evening_wrap,
        "tomorrow": day_orchestrator.prepare_tomorrow,
        "story": day_orchestrator.generate_daily_story,
    }
    operation = operations.get(step_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Unknown financial-day step")
    return await operation()


@app.get("/api/v1/story/today", response_model=DailyWealthStory)
async def daily_wealth_story() -> DailyWealthStory:
    """Build or reuse a deterministic recap from FinancialDayState only."""

    try:
        return await daily_story_service.prepare()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/story/today/generate", response_model=DailyWealthStory, status_code=202)
async def generate_daily_wealth_story() -> DailyWealthStory:
    """Explicit story generation remains fast and never invokes market Search."""

    try:
        return await daily_story_service.prepare()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/v1/story/today/narration",
    response_model=StoryNarration,
    status_code=202,
)
async def start_story_narration() -> StoryNarration:
    try:
        story = await daily_story_service.prepare()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return story_narration_service.start(story)


@app.get("/api/v1/story/{story_id}/narration", response_model=StoryNarration)
async def story_narration(story_id: str) -> StoryNarration:
    narration = story_narration_service.get(story_id)
    if narration is None:
        raise HTTPException(status_code=404, detail="Narration has not been prepared")
    return narration


@app.get("/api/v1/story/{story_id}/narration/{scene_id}/file")
async def story_scene_audio(story_id: str, scene_id: str) -> FileResponse:
    path = story_narration_service.audio_path(story_id, scene_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Scene narration is not ready")
    return FileResponse(path, media_type="audio/wav", filename=f"{scene_id}.wav")


@app.post("/api/v1/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    if request.target_type not in {"story", "event", "conversation"}:
        raise HTTPException(status_code=422, detail="Unsupported feedback target")
    if request.value not in {"useful", "not_relevant"}:
        raise HTTPException(status_code=422, detail="Unsupported feedback value")
    daily_interaction_store.record_feedback(
        request.target_type, request.target_id, request.value
    )
    return FeedbackResponse(recorded=True, **request.model_dump(exclude={"conversation_id"}))


@app.get("/api/v1/audio/{brief_type}", response_model=AudioBrief)
async def audio_brief(brief_type: AudioBriefType) -> AudioBrief:
    """Return approved text and cached audio state without generating audio."""

    return await media_service.prepare(brief_type)


@app.post(
    "/api/v1/audio/{brief_type}/generate",
    response_model=AudioGenerationResponse,
    status_code=202,
)
async def generate_audio_brief(brief_type: AudioBriefType) -> AudioGenerationResponse:
    """Queue Gemini TTS work; duplicate requests reuse the same brief."""

    return await media_service.start(brief_type)


@app.get("/api/v1/audio/{brief_id}/status", response_model=AudioBrief)
async def audio_status(brief_id: str) -> AudioBrief:
    brief = media_service.get(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Unknown audio brief")
    return brief


@app.get("/api/v1/audio/{brief_id}/file")
async def audio_file(brief_id: str) -> FileResponse:
    path = media_service.audio_path(brief_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Audio is not ready")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"wealth-copilot-{brief_id}.wav",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )
