"""FastAPI surface for dashboard, interactions, media, and the financial day."""

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .advisor.schemas import (
    AdvisorCase,
    AdvisorProfile,
    CreateAdvisorPacketRequest,
    SendAdvisorPacketRequest,
)
from .advisor.service import advisor_service
from .config import application_today

from .agents.event_watcher import save_event_action
from .dashboard.schemas import (
    DashboardResponse,
    EventActionRequest,
    EventActionResponse,
    RefreshView,
)
from .dashboard.service import dashboard_service
from .interaction.context import resolve_surface_context
from .interaction.memory import conversation_store, daily_interaction_store
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
from .onboarding import onboarding_service
from .onboarding.schemas import (
    OnboardingInferenceRequest,
    OnboardingProfileResponse,
    OnboardingSaveRequest,
    OnboardingSession,
    SuggestedProfile,
)
from .day.orchestrator import day_orchestrator
from .day.presentation import (
    FinancialDayClockState,
    PresentationAdvanceRequest,
    PresentationClockState,
    financial_day_clock,
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
from .readiness import GoogleReadinessReport, google_readiness, log_google_readiness
from .cases.schemas import FinancialCase
from .product_api.schemas import (
    AlertCategory,
    AlertDetailResponse,
    AlertInboxResponse,
    CopilotBootstrapResponse,
    CreateWatchEventRequest,
    PersistenceStatusResponse,
    PortfolioResponse,
    TimelineResponse,
    TodayResponse,
    WatchEventResponse,
)
from .product_api.service import product_api_service
from .product_api.stream import product_event_stream
from .voice import VoiceSessionRequest, VoiceSessionResponse, voice_session_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_google_readiness()
    day_scheduler.start()
    await day_orchestrator.recover_interrupted_demo()
    await financial_day_clock.recover()
    yield
    await financial_day_clock.stop()
    await day_scheduler.stop()


app = FastAPI(
    title="Wealth Copilot API",
    version="1.0.0",
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


async def _clear_scenario_state() -> None:
    """Clear process-local work that is scoped to the active simulation run."""

    await day_orchestrator.cancel_background_run()
    await dashboard_service.clear_transient_state()
    await research_job_manager.clear()
    await media_service.clear()
    await story_narration_service.clear()
    conversation_store.clear()
    daily_interaction_store.clear()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/readiness", response_model=GoogleReadinessReport)
async def readiness() -> GoogleReadinessReport:
    """Return credential-safe configuration readiness for Google capabilities."""

    return google_readiness()


@app.get("/api/v1/simulation", response_model=SimulationState)
async def simulation_state() -> SimulationState:
    return simulation_service.state()


@app.post("/api/v1/simulation/scenarios/{scenario_id}", response_model=SimulationState)
async def load_simulation_scenario(scenario_id: str) -> SimulationState:
    try:
        state = simulation_service.load_scenario(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await financial_day_clock.stop()
    await _clear_scenario_state()
    news_candidate_cache.clear()
    daily_event_store.clear()
    financial_day_store.clear()
    return state


@app.post("/api/v1/simulation/reset", response_model=SimulationState)
async def reset_simulation() -> SimulationState:
    await financial_day_clock.stop()
    await _clear_scenario_state()
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


@app.get("/api/v1/today", response_model=TodayResponse)
async def today() -> TodayResponse:
    """Return only the information the user needs to understand next."""

    return await product_api_service.today()


@app.get("/api/v1/portfolio", response_model=PortfolioResponse)
async def portfolio() -> PortfolioResponse:
    """Return the canonical calculated portfolio view for the Portfolio page."""

    return await product_api_service.portfolio()


@app.get("/api/v1/alerts", response_model=AlertInboxResponse)
async def alerts(category: AlertCategory | None = None) -> AlertInboxResponse:
    """Return the event inbox, optionally filtered by product category."""

    return await product_api_service.alerts(category)


@app.get("/api/v1/alerts/{case_id}", response_model=AlertDetailResponse)
async def alert_detail(case_id: str) -> AlertDetailResponse:
    """Return one financial case with its retained assessment and chart data."""

    try:
        return await product_api_service.alert_detail(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/timeline", response_model=TimelineResponse)
async def timeline() -> TimelineResponse:
    """Return the focused projection of FinancialDayState for the Timeline page."""

    return await product_api_service.timeline()


@app.post("/api/v1/onboarding/infer", response_model=SuggestedProfile)
async def infer_onboarding_profile(request: OnboardingInferenceRequest) -> SuggestedProfile:
    """Suggest editable onboarding defaults from early profile inputs."""

    return onboarding_service.infer(request)


@app.post("/api/v1/onboarding/profile", response_model=OnboardingSession)
async def save_onboarding_profile(request: OnboardingSaveRequest) -> OnboardingSession:
    """Persist selected onboarding values plus suggested defaults and overrides."""

    return onboarding_service.save(request)


@app.get("/api/v1/onboarding/profile", response_model=OnboardingProfileResponse)
async def onboarding_profile(user_id: str = "demo_user") -> OnboardingProfileResponse:
    """Return the saved final onboarding profile when one exists."""

    return OnboardingProfileResponse(session=onboarding_service.get(user_id))


@app.get("/api/v1/copilot", response_model=CopilotBootstrapResponse)
async def copilot_bootstrap(
    conversation_id: str | None = None,
) -> CopilotBootstrapResponse:
    """Return stable day context and prompts before the chat UI mounts."""

    return await product_api_service.copilot_bootstrap(conversation_id)


@app.get("/api/v1/persistence/status", response_model=PersistenceStatusResponse)
async def persistence_status() -> PersistenceStatusResponse:
    """Return whether Firestore mirroring is active without exposing credentials."""

    return product_api_service.persistence_status()


@app.post("/api/v1/watch-events", response_model=WatchEventResponse, status_code=201)
async def create_watch_event(request: CreateWatchEventRequest) -> WatchEventResponse:
    """Create an internal Wealth Copilot watch event; no external calendar write."""

    return product_api_service.create_watch_event(request)


@app.post("/api/v1/copilot", response_model=ConversationResponse)
async def copilot(request: ConversationRequest) -> ConversationResponse:
    """Ask Wealth Copilot while preserving the existing conversation contract."""

    return await chat(request)


@app.post("/api/v1/copilot/voice/session", response_model=VoiceSessionResponse)
async def copilot_voice_session(
    request: VoiceSessionRequest,
) -> VoiceSessionResponse:
    """Mint a short-lived room token without exposing LiveKit credentials."""

    return voice_session_service.create(request)


@app.get("/api/v1/events/stream")
async def events_stream(request: Request, once: bool = False) -> StreamingResponse:
    """Push financial-day changes to clients using server-sent events."""

    return StreamingResponse(
        product_event_stream(request, once=once),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    today = application_today()
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


@app.get("/api/v1/cases", response_model=list[FinancialCase])
async def financial_cases() -> list[FinancialCase]:
    """Return material cases retained for the active financial day."""

    return day_orchestrator.current_state().financial_cases


@app.get("/api/v1/cases/{case_id}", response_model=FinancialCase)
async def financial_case(case_id: str) -> FinancialCase:
    case = next(
        (
            item
            for item in day_orchestrator.current_state().financial_cases
            if item.case_id == case_id
        ),
        None,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown financial case")
    return case


@app.post("/api/v1/day/demo", response_model=FinancialDayState, status_code=202)
async def run_demo_day() -> FinancialDayState:
    """Start the 60–90 second judge-friendly day without blocking the request."""

    return await day_orchestrator.start_demo_day()


@app.get("/api/v1/day/clock", response_model=FinancialDayClockState)
async def financial_day_clock_state() -> FinancialDayClockState:
    """Return the persisted state of the product financial-day clock."""

    return financial_day_clock.state()


@app.post(
    "/api/v1/day/clock/start",
    response_model=FinancialDayClockState,
    status_code=202,
)
async def start_financial_day_clock() -> FinancialDayClockState:
    """Start or resume the current financial day without duplicating work."""

    return await financial_day_clock.play()


@app.post("/api/v1/day/clock/pause", response_model=FinancialDayClockState)
async def pause_financial_day_clock() -> FinancialDayClockState:
    """Pause time after the active idempotent checkpoint settles."""

    return await financial_day_clock.pause()


@app.post(
    "/api/v1/day/clock/restart",
    response_model=FinancialDayClockState,
    status_code=202,
)
async def restart_financial_day_clock() -> FinancialDayClockState:
    """Reset today's simulated state and pause it at 07:00."""

    return await financial_day_clock.restart()


@app.post(
    "/api/v1/day/clock/next",
    response_model=FinancialDayClockState,
    status_code=202,
)
async def advance_financial_day_clock_to_next() -> FinancialDayClockState:
    """Run exactly the next pending financial-day checkpoint."""

    return await financial_day_clock.advance_to_next()


@app.get("/api/v1/presentation-clock", response_model=PresentationClockState)
async def presentation_clock_state() -> PresentationClockState:
    """Compatibility alias for the canonical product day clock."""

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


@app.get("/api/v1/day/{trading_date}", response_model=FinancialDayState)
async def financial_day(trading_date: date) -> FinancialDayState:
    return financial_day_store.get(trading_date)


@app.post("/api/v1/day/steps/{step_id}", response_model=FinancialDayState)
async def run_day_step(step_id: str) -> FinancialDayState:
    operations = {
        "morning": day_orchestrator.run_morning_pulse,
        "health": day_orchestrator.run_portfolio_health,
        "open": day_orchestrator.run_market_open_monitor,
        "watch": day_orchestrator.run_adaptive_market_watch,
        "sector": day_orchestrator.run_sector_deep_dive,
        "event": day_orchestrator.handle_market_event,
        "learning": day_orchestrator.run_contextual_learning,
        "close": day_orchestrator.run_market_close,
        "intelligence": day_orchestrator.run_portfolio_intelligence,
        "actions": day_orchestrator.run_action_queue,
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
