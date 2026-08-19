"""Thin, deterministic orchestration for human-advisor handoffs."""

from datetime import date, datetime, timezone
import re
from uuid import uuid4

from ..config import get_settings
from ..day.schemas import FinancialDayState
from ..day.active import ArtifactProvenance
from ..day.store import FinancialDayStore, financial_day_store
from ..interaction.context import resolve_surface_context
from ..interaction.research_jobs import research_job_manager
from .provider import AdvisorDeliveryError, get_advisor_provider
from .schemas import (
    AdvisorCase,
    AdvisorEmailDraft,
    AdvisorPacket,
    AdvisorProfile,
    AdvisorResponse,
    AdvisorStatus,
    CreateAdvisorPacketRequest,
)


_DEFAULT_QUESTION = (
    "Does this development materially change your view of this holding, "
    "or is it something you would currently monitor?"
)


class AdvisorService:
    def __init__(self, store: FinancialDayStore | None = None) -> None:
        self.store = store or financial_day_store

    @staticmethod
    def profile() -> AdvisorProfile:
        settings = get_settings()
        return AdvisorProfile(
            advisor_id="primary-advisor",
            name=settings.advisor_name,
            email=settings.advisor_email,
            firm=settings.advisor_firm,
            provider=settings.advisor_provider,
            connected=settings.advisor_provider == "demo" or bool(settings.advisor_email),
        )

    @staticmethod
    def _matching_fact(facts: list[str], needle: str, fallback: str) -> str:
        return next((fact for fact in facts if needle in fact.lower()), fallback)

    @staticmethod
    def _email_body(packet: AdvisorPacket, profile: AdvisorProfile) -> str:
        facts = "\n".join(f"- {item}" for item in packet.facts)
        interpretations = "\n".join(f"- {item}" for item in packet.interpretations)
        unknowns = "\n".join(f"- {item}" for item in packet.unknowns)
        sources = "\n".join(f"- {item.name}: {item.url}" for item in packet.sources) or "- No external source retained."
        return (
            f"Hello {profile.name},\n\n"
            f"I would like your perspective on: {packet.title}\n\n"
            f"My question\n{packet.user_question}\n\n"
            f"Portfolio context\n- {packet.exposure}\n- {packet.relevance}\n\n"
            f"Retained facts\n{facts}\n\n"
            f"Wealth Copilot interpretation (not advice)\n{interpretations}\n\n"
            f"What remains unknown\n{unknowns}\n\n"
            f"Sources\n{sources}\n\n"
            "Please share your perspective. Wealth Copilot will display your response as advisor commentary, not as its own recommendation."
        )

    async def create(self, request: CreateAdvisorPacketRequest) -> AdvisorCase:
        if request.target_type not in {"story", "event"}:
            raise ValueError("Advisor requests must refer to a story or event")
        context = await resolve_surface_context(
            story_id=request.target_id if request.target_type == "story" else None,
            event_id=request.target_id if request.target_type == "event" else None,
        )
        retained_research = research_job_manager.latest_for(
            story_id=request.target_id if request.target_type == "story" else None,
            event_id=request.target_id if request.target_type == "event" else None,
        )
        interpretations = list(context.interpretation)
        sources = list(context.sources)
        unknowns = list(context.unknowns)
        if retained_research and retained_research.result:
            interpretations.append(
                f"Completed Research Agent result: {retained_research.result.answer}"
            )
            unknowns.extend(
                item
                for item in retained_research.result.context.unknowns
                if item not in unknowns
            )
            known_urls = {item.url for item in sources}
            sources.extend(
                item
                for item in retained_research.result.sources
                if item.url not in known_urls
            )
        now = datetime.now(timezone.utc)
        profile = self.profile()
        current_day = self.store.get()
        packet = AdvisorPacket(
            request_id=f"advisor-{uuid4().hex[:12]}",
            day_id=current_day.day_id,
            run_id=current_day.run_id,
            created_at=now,
            updated_at=now,
            target_type=context.target_type,
            target_id=context.target_id or request.target_id,
            title=context.title,
            exposure=self._matching_fact(context.facts, "exposure", context.portfolio_context),
            relevance=self._matching_fact(context.facts, "relevance", "Relevance is based on retained portfolio context."),
            facts=context.facts,
            interpretations=interpretations,
            unknowns=unknowns,
            sources=sources,
            user_question=request.user_question.strip(),
            suggested_questions=[_DEFAULT_QUESTION],
            provider=profile.provider,
            email=AdvisorEmailDraft(
                to_name=profile.name,
                to_email=profile.email,
                subject=f"Perspective requested: {context.title}",
                body="",
            ),
            provenance=ArtifactProvenance(
                day_id=current_day.day_id,
                run_id=current_day.run_id,
                source_checkpoint=current_day.presentation_active_checkpoint or "interaction",
                source_snapshot_id=context.target_id or request.target_id,
                generated_at=now,
            ),
        )
        packet.email.body = self._email_body(packet, profile)
        self.store.update(lambda state: state.advisor_requests.append(packet), date.today())
        return AdvisorCase(packet=packet)

    def _find(self, request_id: str, trading_date: date | None = None) -> tuple[FinancialDayState, AdvisorPacket]:
        state = self.store.get(trading_date)
        packet = next((item for item in state.advisor_requests if item.request_id == request_id), None)
        if packet is None:
            raise ValueError(f"Unknown advisor request: {request_id}")
        return state, packet

    @staticmethod
    def _upsert_packet(state: FinancialDayState, packet: AdvisorPacket) -> None:
        state.advisor_requests = [
            packet if item.request_id == packet.request_id else item
            for item in state.advisor_requests
        ]

    def ready(self, request_id: str) -> AdvisorCase:
        state, packet = self._find(request_id)
        if packet.status == AdvisorStatus.DRAFT:
            packet.status = AdvisorStatus.READY
            packet.updated_at = datetime.now(timezone.utc)
            self.store.update(lambda current: self._upsert_packet(current, packet), state.trading_date)
        return self.get(request_id)

    def send(self, request_id: str, *, confirmed: bool) -> AdvisorCase:
        if not confirmed:
            raise PermissionError("Review the exact email and confirm before sending")
        state, packet = self._find(request_id)
        if packet.status not in {AdvisorStatus.READY, AdvisorStatus.SENT, AdvisorStatus.REPLIED}:
            raise ValueError("Advisor request must be reviewed before sending")
        if packet.status in {AdvisorStatus.SENT, AdvisorStatus.REPLIED}:
            return self.get(request_id)
        try:
            get_advisor_provider().send(packet)
        except AdvisorDeliveryError as exc:
            packet.send_error = str(exc)
            packet.updated_at = datetime.now(timezone.utc)
            self.store.update(lambda current: self._upsert_packet(current, packet), state.trading_date)
            return AdvisorCase(packet=packet)
        now = datetime.now(timezone.utc)
        packet.status = AdvisorStatus.SENT
        packet.sent_at = now
        packet.updated_at = now
        packet.send_error = None
        self.store.update(lambda current: self._upsert_packet(current, packet), state.trading_date)
        return AdvisorCase(packet=packet)

    @staticmethod
    def _demo_reply(packet: AdvisorPacket, profile: AdvisorProfile) -> AdvisorResponse:
        company = re.sub(r"\s+", " ", packet.title).strip()
        received_at = datetime.now(timezone.utc)
        return AdvisorResponse(
            response_id=f"reply-{packet.request_id.removeprefix('advisor-')}",
            day_id=packet.day_id,
            run_id=packet.run_id,
            request_id=packet.request_id,
            received_at=received_at,
            advisor_name=profile.name,
            message=(
                f"Thanks for sharing the context on {company}. The sector-relative move and your portfolio exposure "
                "make this worth monitoring. The material unknown is still the confirmed cause, so I would review "
                "the next official company or regulatory disclosure before drawing a firmer conclusion."
            ),
            provenance=(
                ArtifactProvenance(
                    day_id=packet.day_id,
                    run_id=packet.run_id,
                    source_checkpoint="advisor_response",
                    source_snapshot_id=packet.request_id,
                    generated_at=received_at,
                )
                if packet.day_id and packet.run_id
                else None
            ),
        )

    def _reconcile(self, state: FinancialDayState, packet: AdvisorPacket) -> tuple[FinancialDayState, AdvisorPacket]:
        settings = get_settings()
        if (
            packet.provider == "demo"
            and packet.status == AdvisorStatus.SENT
            and packet.sent_at is not None
            and (datetime.now(timezone.utc) - packet.sent_at).total_seconds() >= settings.advisor_demo_reply_delay_seconds
        ):
            response = self._demo_reply(packet, self.profile())
            packet.status = AdvisorStatus.REPLIED
            packet.response_id = response.response_id
            packet.updated_at = response.received_at

            def mutate(current: FinancialDayState) -> None:
                self._upsert_packet(current, packet)
                current.advisor_responses = [
                    item for item in current.advisor_responses if item.request_id != packet.request_id
                ]
                current.advisor_responses.append(response)

            state = self.store.update(mutate, state.trading_date)
        return state, packet

    def get(self, request_id: str) -> AdvisorCase:
        state, packet = self._find(request_id)
        state, packet = self._reconcile(state, packet)
        response = next(
            (item for item in state.advisor_responses if item.request_id == request_id), None
        )
        return AdvisorCase(packet=packet, response=response)


advisor_service = AdvisorService()
