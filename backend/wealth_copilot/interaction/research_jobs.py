"""Non-blocking job manager for potentially slow Research Agent work."""

import asyncio
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .schemas import (
    ConversationRequest,
    InteractionMode,
    ResearchJob,
    ResearchRequest,
    ResearchStatus,
)
from .service import InteractionService, interaction_service


class ResearchJobManager:
    def __init__(self, service: InteractionService | None = None) -> None:
        self._service = service or interaction_service
        self._lock = RLock()
        self._jobs: dict[str, ResearchJob] = {}
        self._targets: dict[str, tuple[str | None, str | None]] = {}
        self._tasks: set[asyncio.Task] = set()

    def start(self, request: ResearchRequest) -> ResearchJob:
        job_id = uuid4().hex
        job = ResearchJob(
            job_id=job_id,
            status=ResearchStatus.QUEUED,
            message="Preparing the Research Agent with your current context.",
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[job_id] = job
            self._targets[job_id] = (
                request.active_story_id,
                request.active_event_id,
            )
        task = asyncio.create_task(self._run(job_id, request))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job.model_copy(deep=True)

    async def _run(self, job_id: str, request: ResearchRequest) -> None:
        with self._lock:
            self._jobs[job_id].status = ResearchStatus.RESEARCHING
            self._jobs[job_id].message = "Checking retained context and source-first evidence."
        try:
            result = await self._service.respond(
                ConversationRequest(
                    conversation_id=request.conversation_id,
                    message=request.message,
                    mode=InteractionMode.RESEARCH,
                    active_story_id=request.active_story_id,
                    active_event_id=request.active_event_id,
                )
            )
            with self._lock:
                job = self._jobs[job_id]
                job.result = result
                job.status = ResearchStatus.FALLBACK if result.fallback_used else ResearchStatus.COMPLETE
                job.message = (
                    "Research is ready from retained context; fresh sources were temporarily unavailable."
                    if result.fallback_used
                    else "Source-first research is ready."
                )
                job.completed_at = datetime.now(timezone.utc)
        except Exception:
            with self._lock:
                job = self._jobs[job_id]
                job.status = ResearchStatus.FAILED
                job.message = "Research could not be completed. Existing dashboard context is still available."
                job.completed_at = datetime.now(timezone.utc)

    def get(self, job_id: str) -> ResearchJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def latest_for(
        self, *, story_id: str | None = None, event_id: str | None = None
    ) -> ResearchJob | None:
        """Return completed research already linked to this surface; never starts work."""

        target = (story_id, event_id)
        with self._lock:
            matches = [
                job
                for job_id, job in self._jobs.items()
                if self._targets.get(job_id) == target
                and job.result is not None
                and job.status in {ResearchStatus.COMPLETE, ResearchStatus.FALLBACK}
            ]
            if not matches:
                return None
            return max(matches, key=lambda item: item.completed_at or item.created_at).model_copy(
                deep=True
            )


research_job_manager = ResearchJobManager()
