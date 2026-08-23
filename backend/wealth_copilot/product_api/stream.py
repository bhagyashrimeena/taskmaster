"""Server-sent product events derived from canonical financial-day state."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import Request

from .schemas import ProductEvent, ProductEventType, StreamSnapshot
from .service import ProductApiService, product_api_service


def _event(
    event_type: ProductEventType,
    snapshot: StreamSnapshot,
    *,
    entity_id: str | None = None,
    data: dict[str, object] | None = None,
) -> ProductEvent:
    return ProductEvent(
        event_type=event_type,
        emitted_at=datetime.now(timezone.utc),
        day_id=snapshot.day_id,
        run_id=snapshot.run_id,
        entity_id=entity_id,
        data=data or {},
    )


def events_since(
    previous: StreamSnapshot | None,
    current: StreamSnapshot,
) -> list[ProductEvent]:
    if previous is None or previous.run_id != current.run_id:
        return [
            _event(
                ProductEventType.SNAPSHOT,
                current,
                data=current.model_dump(mode="json"),
            )
        ]

    events: list[ProductEvent] = []
    for step_id in current.completed_steps:
        if step_id not in previous.completed_steps:
            events.append(_event(
                ProductEventType.CHECKPOINT_COMPLETED,
                current,
                entity_id=step_id,
                data={"step_id": step_id, "status": "complete"},
            ))
    for event_id in current.alert_event_ids:
        if event_id not in previous.alert_event_ids:
            events.append(_event(
                ProductEventType.EVENT_ALERT_CREATED,
                current,
                entity_id=event_id,
                data={"event_id": event_id},
            ))
    for case_id, updated_at in current.case_versions.items():
        if previous.case_versions.get(case_id) != updated_at:
            events.append(_event(
                ProductEventType.FINANCIAL_CASE_UPDATED,
                current,
                entity_id=case_id,
                data={"case_id": case_id, "updated_at": updated_at.isoformat()},
            ))
    for brief_id in current.ready_audio_ids:
        if brief_id not in previous.ready_audio_ids:
            events.append(_event(
                ProductEventType.AUDIO_READY,
                current,
                entity_id=brief_id,
                data={"brief_id": brief_id},
            ))
    return events


def format_sse(event: ProductEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
    return f"event: {event.event_type.value}\ndata: {payload}\n\n"


async def product_event_stream(
    request: Request,
    *,
    service: ProductApiService = product_api_service,
    once: bool = False,
    poll_seconds: float = 2.0,
) -> AsyncIterator[str]:
    previous: StreamSnapshot | None = None
    while True:
        current = service.stream_snapshot()
        for event in events_since(previous, current):
            yield format_sse(event)
        previous = current
        if once or await request.is_disconnected():
            return
        await asyncio.sleep(poll_seconds)
