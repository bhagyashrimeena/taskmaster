"""Optional Firestore mirror for Wealth Copilot product state.

Firestore stores product memory; deterministic engines and TaskMaster remain the brain.
When Firestore is not configured, every method becomes a safe no-op and the app
continues with the existing JSON/in-memory stores.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from threading import Thread
from typing import Any

from ..config import get_settings


logger = logging.getLogger(__name__)


class FirestorePersistence:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._checked = False
        self._disabled_reason = "Firestore has not been initialized."

    @property
    def disabled_reason(self) -> str:
        self._ensure_client()
        if self._client is None and self._disabled_reason == "Firestore has not been initialized.":
            settings = get_settings()
            if not settings.firestore_enabled:
                return "Firestore is disabled; using local demo persistence."
            return "Firestore is not connected; using local demo persistence."
        return self._disabled_reason

    def configured(self) -> bool:
        return self._ensure_client() is not None

    def _ensure_client(self):
        if self._checked:
            return self._client
        self._checked = True
        settings = get_settings()
        if not settings.firestore_enabled:
            self._disabled_reason = "Firestore is disabled; using local demo persistence."
            logger.info(self._disabled_reason)
            return None
        project = settings.firestore_project_id or settings.google_cloud_project
        if not project:
            self._disabled_reason = "Firestore is enabled but no project id is configured; using local demo persistence."
            logger.warning(self._disabled_reason)
            return None
        try:
            from google.cloud import firestore  # type: ignore

            self._client = firestore.Client(project=project, database=settings.firestore_database)
            self._disabled_reason = ""
            logger.info("Firestore persistence enabled project=%s database=%s", project, settings.firestore_database)
        except Exception as exc:  # pragma: no cover - depends on local credentials
            self._client = None
            self._disabled_reason = f"Firestore unavailable ({type(exc).__name__}); using local demo persistence."
            logger.warning(self._disabled_reason)
        return self._client

    @staticmethod
    def _json(value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return value
        return {"value": value}

    def _collection(self, name: str):
        client = self._ensure_client()
        if client is None:
            return None
        prefix = get_settings().firestore_collection_prefix.strip()
        return client.collection(f"{prefix}_{name}" if prefix else name)

    def upsert(self, collection: str, document_id: str, payload: Any) -> None:
        target = self._collection(collection)
        if target is None:
            return
        data = self._json(payload)
        data["_persisted_at"] = datetime.now(timezone.utc).isoformat()
        try:
            target.document(document_id).set(
                data,
                merge=True,
                timeout=get_settings().firestore_timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - depends on network/credentials
            self._client = None
            self._disabled_reason = f"Firestore write unavailable ({type(exc).__name__}); using local demo persistence."
            logger.warning("Firestore write skipped collection=%s document=%s error=%s", collection, document_id, type(exc).__name__)

    def _background(self, label: str, fn) -> None:
        def run() -> None:
            try:
                fn()
            except Exception as exc:  # pragma: no cover
                logger.warning("Firestore background mirror skipped label=%s error=%s", label, type(exc).__name__)

        Thread(target=run, name=f"firestore-{label}", daemon=True).start()

    def persist_financial_day(self, state) -> None:
        if not get_settings().firestore_enabled:
            self._ensure_client()
            return

        def write() -> None:
            self.upsert("financial_day_states", state.day_id, state)
            for case in state.financial_cases:
                self.upsert("financial_cases", case.case_id, case)
            for packet in state.advisor_requests:
                self.upsert("advisor_handoffs", packet.request_id, packet)
            for snapshot in state.news_snapshots:
                self.upsert("news_snapshots", snapshot.story_id, snapshot)
            for scenario in state.likely_scenarios:
                self.upsert("likely_scenarios", scenario.scenario_id, scenario)
            for event in state.calendar_watch_events:
                self.upsert("calendar_watch_events", event.event_id, event)

        self._background("financial-day", write)

    def persist_conversation_turn(self, conversation_id: str, role: str, text: str, *, mode: str | None = None) -> None:
        payload = {
            "conversation_id": conversation_id,
            "role": role,
            "text": text,
            "mode": mode,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        def write() -> None:
            target = self._collection("copilot_conversations")
            if target is None:
                return
            try:
                target.document(conversation_id).collection("turns").add(
                    payload,
                    timeout=get_settings().firestore_timeout_seconds,
                )
                target.document(conversation_id).set(
                    {"conversation_id": conversation_id, "updated_at": payload["created_at"]},
                    merge=True,
                    timeout=get_settings().firestore_timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Firestore conversation write skipped conversation=%s error=%s", conversation_id, type(exc).__name__)

        if get_settings().firestore_enabled:
            self._background("conversation", write)
        else:
            self._ensure_client()

    def persist_onboarding_session(self, session) -> None:
        if not get_settings().firestore_enabled:
            self._ensure_client()
            return

        def write() -> None:
            self.upsert("onboarding_sessions", session.user_id, session)
            self.upsert("user_profiles", session.user_id, {
                "user_id": session.user_id,
                "raw_inputs": session.raw_inputs.model_dump(mode="json"),
                "suggested_profile": session.suggested_profile.model_dump(mode="json"),
                "final_profile": session.final_profile,
                "overrides": [item.model_dump(mode="json") for item in session.overrides],
                "updated_at": session.updated_at.isoformat(),
            })
            self.upsert("user_preferences", session.user_id, {
                "user_id": session.user_id,
                "agent_preferences": session.final_profile.get("agent_preferences", {}),
                "updated_at": session.updated_at.isoformat(),
            })

        self._background("onboarding", write)


firestore_persistence = FirestorePersistence()
