"""Stable contracts for reviewable human-advisor handoffs."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..interaction.schemas import SourceReference
from ..day.active import ArtifactProvenance


class AdvisorModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AdvisorStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT = "SENT"
    REPLIED = "REPLIED"
    CLOSED = "CLOSED"


class AdvisorProfile(AdvisorModel):
    advisor_id: str
    name: str
    email: str
    firm: str
    provider: str
    connected: bool


class AdvisorEmailDraft(AdvisorModel):
    to_name: str
    to_email: str
    subject: str
    body: str


class AdvisorPacket(AdvisorModel):
    request_id: str
    day_id: str | None = None
    run_id: str | None = None
    created_at: datetime
    updated_at: datetime
    target_type: str
    target_id: str
    title: str
    exposure: str
    relevance: str
    facts: list[str]
    interpretations: list[str]
    unknowns: list[str]
    sources: list[SourceReference]
    user_question: str
    suggested_questions: list[str]
    status: AdvisorStatus = AdvisorStatus.DRAFT
    provider: str
    email: AdvisorEmailDraft
    sent_at: datetime | None = None
    response_id: str | None = None
    send_error: str | None = None
    provenance: ArtifactProvenance | None = None


class AdvisorResponse(AdvisorModel):
    response_id: str
    day_id: str | None = None
    run_id: str | None = None
    request_id: str
    received_at: datetime
    advisor_name: str
    message: str
    perspective_label: str = "Advisor perspective"
    provenance: ArtifactProvenance | None = None


class AdvisorCase(AdvisorModel):
    packet: AdvisorPacket
    response: AdvisorResponse | None = None


class CreateAdvisorPacketRequest(AdvisorModel):
    target_type: str
    target_id: str
    user_question: str = Field(min_length=1, max_length=1200)


class SendAdvisorPacketRequest(AdvisorModel):
    confirmed: bool = False
