"""Replaceable delivery providers for reviewed advisor requests."""

import base64
from dataclasses import dataclass
from email.message import EmailMessage
import json
from typing import Protocol
from urllib.request import Request as UrlRequest, urlopen

from ..config import get_settings
from .schemas import AdvisorPacket


class AdvisorDeliveryError(RuntimeError):
    """A reviewed request could not be delivered."""


@dataclass(frozen=True)
class DeliveryReceipt:
    provider_message_id: str


class AdvisorProvider(Protocol):
    def send(self, packet: AdvisorPacket) -> DeliveryReceipt: ...


class DemoAdvisorProvider:
    """Records delivery locally; the service materializes a deterministic reply."""

    def send(self, packet: AdvisorPacket) -> DeliveryReceipt:
        return DeliveryReceipt(provider_message_id=f"demo-{packet.request_id}")


class GmailAdvisorProvider:
    """Small Gmail REST adapter kept separate from packet orchestration.

    It uses ADC with the gmail.send scope only when ADVISOR_PROVIDER=gmail.
    Any credential or transport failure is converted to a safe delivery error.
    """

    _scope = "https://www.googleapis.com/auth/gmail.send"
    _endpoint = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    def send(self, packet: AdvisorPacket) -> DeliveryReceipt:
        try:
            import google.auth
            from google.auth.transport.requests import Request as AuthRequest

            credentials, _ = google.auth.default(scopes=[self._scope])
            credentials.refresh(AuthRequest())
            if not credentials.token:
                raise RuntimeError("ADC did not return an access token")

            settings = get_settings()
            message = EmailMessage()
            message["To"] = packet.email.to_email
            message["From"] = settings.advisor_sender_email or "me"
            message["Subject"] = packet.email.subject
            message.set_content(packet.email.body)
            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
            request = UrlRequest(
                self._endpoint,
                data=json.dumps({"raw": encoded}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {credentials.token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=settings.advisor_send_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return DeliveryReceipt(provider_message_id=str(payload.get("id", "gmail")))
        except Exception as exc:
            raise AdvisorDeliveryError(
                "Gmail is not connected for advisor requests. The reviewed draft is still saved."
            ) from exc


def get_advisor_provider() -> AdvisorProvider:
    return GmailAdvisorProvider() if get_settings().advisor_provider == "gmail" else DemoAdvisorProvider()

