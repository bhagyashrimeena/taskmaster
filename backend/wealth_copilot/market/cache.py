"""Small in-process candidate cache with stale-on-error resilience."""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from pathlib import Path
import hashlib

from ..config import get_settings
from .schemas import CanonicalUrlResolution, MarketBriefSnapshot, NewsCandidateBatch


@dataclass(frozen=True)
class NewsCacheSnapshot:
    batch: NewsCandidateBatch
    fetched_at: datetime
    age_seconds: float
    refresh_required: bool


class NewsCandidateCache:
    def __init__(self, snapshot_file: Path | None = None) -> None:
        self._lock = RLock()
        self._batch: NewsCandidateBatch | None = None
        self._cached_at = 0.0
        self._fetched_at: datetime | None = None
        self._refresh_required = False
        self._canonical_urls: dict[str, CanonicalUrlResolution] = {}
        self._snapshot_file = snapshot_file or Path(get_settings().market_snapshot_file)
        self._load_persisted()

    def _load_persisted(self) -> None:
        if not self._snapshot_file.exists():
            return
        try:
            snapshot = MarketBriefSnapshot.model_validate_json(
                self._snapshot_file.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return
        elapsed = max(
            0.0,
            (datetime.now(timezone.utc) - snapshot.retrieved_at).total_seconds(),
        )
        self._batch = snapshot.batch.model_copy(deep=True)
        self._fetched_at = snapshot.retrieved_at
        self._cached_at = monotonic() - elapsed
        self._canonical_urls = snapshot.canonical_urls

    def _persist_live(self, batch: NewsCandidateBatch) -> None:
        if not batch.is_live:
            return
        retrieved_at = datetime.now(timezone.utc)
        identity = f"{batch.source}:{batch.generated_at.isoformat()}:{len(batch.candidates)}"
        snapshot = MarketBriefSnapshot(
            snapshot_id=f"market-{hashlib.sha256(identity.encode()).hexdigest()[:16]}",
            generated_at=batch.generated_at,
            retrieved_at=retrieved_at,
            provider=batch.source,
            status="live",
            candidate_count=len(batch.candidates),
            batch=batch,
            canonical_urls=self._canonical_urls,
        )
        self._snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._snapshot_file.with_suffix(".json.tmp")
        temporary.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self._snapshot_file)

    def snapshot(self) -> NewsCacheSnapshot | None:
        """Return the retained batch even when it is expired or invalidated."""

        with self._lock:
            if self._batch is None or self._fetched_at is None:
                return None
            return NewsCacheSnapshot(
                batch=self._batch.model_copy(deep=True),
                fetched_at=self._fetched_at,
                age_seconds=max(0.0, monotonic() - self._cached_at),
                refresh_required=self._refresh_required,
            )

    def get(self, *, ttl_seconds: int) -> NewsCandidateBatch | None:
        with self._lock:
            if self._batch is None or ttl_seconds <= 0 or self._refresh_required:
                return None
            if monotonic() - self._cached_at > ttl_seconds:
                return None
            return self._batch.model_copy(deep=True)

    def set(self, batch: NewsCandidateBatch) -> None:
        with self._lock:
            self._batch = batch.model_copy(deep=True)
            self._cached_at = monotonic()
            self._fetched_at = datetime.now(timezone.utc)
            self._refresh_required = False
            self._persist_live(batch)

    def canonical_urls(self) -> dict[str, CanonicalUrlResolution]:
        with self._lock:
            return {key: value.model_copy(deep=True) for key, value in self._canonical_urls.items()}

    def update_canonical_urls(self, resolutions: dict[str, CanonicalUrlResolution]) -> None:
        with self._lock:
            self._canonical_urls.update(resolutions)
            if self._batch is not None:
                self._persist_live(self._batch)

    def request_refresh(self) -> None:
        """Make the next lookup miss while retaining a stale fallback copy."""

        with self._lock:
            self._refresh_required = True

    def finish_failed_refresh(self) -> None:
        """Stop forcing refresh after stale data has safely served the request."""

        with self._lock:
            self._refresh_required = False
            self._canonical_urls = {}

    def clear(self) -> None:
        with self._lock:
            self._batch = None
            self._cached_at = 0.0
            self._fetched_at = None
            self._refresh_required = False


news_candidate_cache = NewsCandidateCache()


def refresh_news() -> dict[str, object]:
    """Force Search next time while preserving the last batch for failure fallback."""

    snapshot = news_candidate_cache.snapshot()
    news_candidate_cache.request_refresh()
    return {
        "status": "ok",
        "stale_fallback_available": snapshot is not None,
        "message": "News refresh requested. The next daily brief will fetch fresh candidates.",
    }
