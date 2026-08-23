"""Phase 7 packet review, confirmation, and durable reply tests."""

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from wealth_copilot.advisor.schemas import (
    AdvisorStatus,
    CreateAdvisorPacketRequest,
)
from wealth_copilot.config import application_today
from wealth_copilot.advisor.service import AdvisorService
from wealth_copilot.day.store import FinancialDayStore
from wealth_copilot.interaction.schemas import SourceReference, SurfaceContext


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AdvisorService:
    async def retained_context(**_):
        return SurfaceContext(
            target_type="event",
            target_id="hdfc-bank-sudden-fall",
            title="HDFC Bank unusual move",
            portfolio_as_of=datetime.fromisoformat("2026-08-18T12:17:00+05:30"),
            source_checkpoint="12:17",
            facts=[
                "HDFC Bank moved -5.4% while its sector moved -0.8%.",
                "At the 12:17 portfolio snapshot, your direct exposure is 17.21% and sector exposure is 27.26%.",
                "Deterministic relevance score: 93.11/100; attention decision: ALERT.",
            ],
            interpretation=["The move is materially different from the broader sector."],
            unknowns=["The retained event data does not establish one confirmed cause."],
            sources=[
                SourceReference(
                    name="NSE",
                    url="https://www.nseindia.com/",
                    authority="event_feed",
                    kind="event",
                )
            ],
            portfolio_context="Portfolio value INR 842000; provider Demo Portfolio.",
        )

    settings = SimpleNamespace(
        advisor_name="Ananya Rao",
        advisor_email="advisor@example.com",
        advisor_firm="Independent Wealth Advisor",
        advisor_provider="demo",
        advisor_demo_reply_delay_seconds=0,
    )
    monkeypatch.setattr("wealth_copilot.advisor.service.resolve_surface_context", retained_context)
    monkeypatch.setattr("wealth_copilot.advisor.service.get_settings", lambda: settings)
    return AdvisorService(FinancialDayStore(tmp_path / "days"))


@pytest.mark.asyncio
async def test_packet_uses_retained_context_and_starts_as_draft(service: AdvisorService) -> None:
    case = await service.create(
        CreateAdvisorPacketRequest(
            target_type="event",
            target_id="hdfc-bank-sudden-fall",
            user_question="What would you monitor next?",
        )
    )

    assert case.packet.status == AdvisorStatus.DRAFT
    assert "17.21%" in case.packet.exposure
    assert case.packet.sources[0].name == "NSE"
    assert "What would you monitor next?" in case.packet.email.body
    assert service.store.get(application_today()).advisor_requests[0].request_id == case.packet.request_id


@pytest.mark.asyncio
async def test_send_requires_review_and_explicit_confirmation(service: AdvisorService) -> None:
    case = await service.create(
        CreateAdvisorPacketRequest(
            target_type="event",
            target_id="hdfc-bank-sudden-fall",
            user_question="Does this change your view?",
        )
    )

    with pytest.raises(PermissionError):
        service.send(case.packet.request_id, confirmed=False)
    with pytest.raises(ValueError):
        service.send(case.packet.request_id, confirmed=True)

    ready = service.ready(case.packet.request_id)
    assert ready.packet.status == AdvisorStatus.READY
    sent = service.send(case.packet.request_id, confirmed=True)
    assert sent.packet.status == AdvisorStatus.SENT


@pytest.mark.asyncio
async def test_demo_response_is_linked_and_persisted(service: AdvisorService) -> None:
    draft = await service.create(
        CreateAdvisorPacketRequest(
            target_type="event",
            target_id="hdfc-bank-sudden-fall",
            user_question="What deserves follow-up?",
        )
    )
    service.ready(draft.packet.request_id)
    service.send(draft.packet.request_id, confirmed=True)

    replied = service.get(draft.packet.request_id)
    persisted = service.store.get(application_today())
    assert replied.packet.status == AdvisorStatus.REPLIED
    assert replied.response is not None
    assert replied.response.request_id == draft.packet.request_id
    assert persisted.advisor_responses[0].response_id == replied.response.response_id
    assert "Advisor perspective" == replied.response.perspective_label
