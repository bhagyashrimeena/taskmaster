"""In-process interaction state plus durable SQLite-backed long-term memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Iterable

from .schemas import DailyInteractionView, SurfaceContext
from ..config import application_today, get_settings
from ..persistence import firestore_persistence


_TOKEN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "us",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}
_FACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("name", re.compile(r"\b(?:my name is|call me|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", re.IGNORECASE)),
    ("location", re.compile(r"\b(?:i live in|i am based in|i'm based in)\s+([A-Za-z][A-Za-z .-]{1,60})", re.IGNORECASE)),
    ("work", re.compile(r"\b(?:i work at|i work for|i'm at)\s+([A-Za-z0-9&.,' -]{2,80})", re.IGNORECASE)),
    ("role", re.compile(r"\b(?:i am a|i'm a|i work as a|my role is)\s+([A-Za-z][A-Za-z0-9 /&-]{2,80})", re.IGNORECASE)),
    ("goal", re.compile(r"\b(?:my goal is|i want to|i need to)\s+([A-Za-z0-9 ,.'&/-]{6,160})", re.IGNORECASE)),
    ("preference", re.compile(r"\b(?:i prefer|i like)\s+([A-Za-z0-9 ,.'&/-]{3,120})", re.IGNORECASE)),
    ("risk", re.compile(r"\b(?:i am|i'm)\s+(conservative|moderate|aggressive)\b", re.IGNORECASE)),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN.findall(text.lower())
        if token.lower() not in _STOPWORDS
    }


def _memory_text(context: SurfaceContext) -> str:
    parts = [
        context.title,
        *context.facts[:4],
        *context.interpretation[:2],
        f"Portfolio context: {context.portfolio_context}",
    ]
    return _normalize_text(" ".join(part for part in parts if part))


def _clean_fact_value(category: str, value: str) -> str:
    cleaned = _normalize_text(value.strip(" .,!"))
    if category == "name":
        parts = []
        for token in cleaned.split():
            if token.lower() in {"and", "but"}:
                break
            if not token[:1].isalpha():
                break
            parts.append(token)
            if len(parts) == 3:
                break
        return " ".join(parts)
    separators = (" and my ", " and i ", " but ", ".", "?", "!")
    lowered = cleaned.lower()
    cutoff = len(cleaned)
    for separator in separators:
        index = lowered.find(separator)
        if index != -1:
            cutoff = min(cutoff, index)
    return cleaned[:cutoff].strip(" ,.")


@dataclass
class ConversationRecord:
    active_story_id: str | None = None
    active_event_id: str | None = None
    history: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievedMemory:
    kind: str
    text: str
    score: float
    created_at: datetime


class ConversationStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, ConversationRecord] = {}

    def get(self, conversation_id: str) -> ConversationRecord:
        with self._lock:
            record = self._records.setdefault(conversation_id, ConversationRecord())
            return ConversationRecord(
                active_story_id=record.active_story_id,
                active_event_id=record.active_event_id,
                history=list(record.history),
            )

    def update_context(
        self, conversation_id: str, *, story_id: str | None, event_id: str | None
    ) -> ConversationRecord:
        with self._lock:
            record = self._records.setdefault(conversation_id, ConversationRecord())
            if story_id:
                record.active_story_id, record.active_event_id = story_id, None
            elif event_id:
                record.active_event_id, record.active_story_id = event_id, None
            return self.get(conversation_id)

    def append(self, conversation_id: str, role: str, text: str) -> None:
        with self._lock:
            record = self._records.setdefault(conversation_id, ConversationRecord())
            record.history.append((role, text))
            record.history[:] = record.history[-12:]
        firestore_persistence.persist_conversation_turn(conversation_id, role, text)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


class DailyInteractionStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._days: dict[str, DailyInteractionView] = {}

    def _day(self, trading_date: date) -> DailyInteractionView:
        return self._days.setdefault(
            trading_date.isoformat(), DailyInteractionView(trading_date=trading_date)
        )

    def save_story(self, story_id: str, trading_date: date | None = None) -> DailyInteractionView:
        with self._lock:
            day = self._day(trading_date or application_today())
            if story_id not in day.saved_story_ids:
                day.saved_story_ids.append(story_id)
            return day.model_copy(deep=True)

    def save_event(self, event_id: str, trading_date: date | None = None) -> DailyInteractionView:
        with self._lock:
            day = self._day(trading_date or application_today())
            if event_id not in day.saved_event_ids:
                day.saved_event_ids.append(event_id)
            return day.model_copy(deep=True)

    def record_feedback(
        self, target_type: str, target_id: str, value: str, trading_date: date | None = None
    ) -> DailyInteractionView:
        with self._lock:
            day = self._day(trading_date or application_today())
            day.feedback[f"{target_type}:{target_id}"] = value
            return day.model_copy(deep=True)

    def get(self, trading_date: date | None = None) -> DailyInteractionView:
        with self._lock:
            return self._day(trading_date or application_today()).model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._days.clear()


class PersistentMemoryStore:
    """SQLite-backed memory store for durable user context and lightweight RAG."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._lock = RLock()
        self._db_path = Path(db_path or get_settings().interaction_memory_db_path)
        self._ensure_db()

    def reconfigure(self, db_path: str | Path) -> None:
        with self._lock:
            self._db_path = Path(db_path)
            self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_text TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_entries_conversation_time
                ON memory_entries (conversation_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_entries_kind
                ON memory_entries (kind)
                """
            )

    def clear(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM memory_entries")

    def remember_exchange(
        self,
        *,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        mode: str,
        context: SurfaceContext,
    ) -> None:
        created_at = _utcnow().isoformat()
        memory_context = _memory_text(context)
        facts = self._extract_user_facts(user_message)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries
                (conversation_id, kind, text, source_text, created_at, metadata_json)
                VALUES (?, 'exchange', ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    _normalize_text(
                        f"User: {user_message}\nAssistant: {assistant_message}\nContext: {memory_context}"
                    ),
                    user_message,
                    created_at,
                    json.dumps(
                        {
                            "mode": mode,
                            "target_type": context.target_type,
                            "target_id": context.target_id,
                        }
                    ),
                ),
            )
            for fact in facts:
                conn.execute(
                    """
                    INSERT INTO memory_entries
                    (conversation_id, kind, text, source_text, created_at, metadata_json)
                    VALUES (?, 'fact', ?, ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        fact["text"],
                        user_message,
                        created_at,
                        json.dumps({"category": fact["category"]}),
                    ),
                )

    def recall(
        self,
        *,
        conversation_id: str,
        query: str,
        context: SurfaceContext,
        limit: int | None = None,
    ) -> list[RetrievedMemory]:
        desired = limit or get_settings().interaction_memory_recall_limit
        query_tokens = _tokenize(
            f"{query} {context.title} {' '.join(context.facts[:2])} {context.portfolio_context}"
        )
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT kind, text, created_at, metadata_json
                FROM memory_entries
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (conversation_id,),
            ).fetchall()
        ranked: list[RetrievedMemory] = []
        for row in rows:
            text = row["text"]
            score = self._score_entry(query_tokens, text, row["kind"])
            if score <= 0:
                continue
            ranked.append(
                RetrievedMemory(
                    kind=row["kind"],
                    text=text,
                    score=score,
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        if not ranked:
            ranked = self._recent_memories(conversation_id, desired)
        ranked.sort(key=lambda item: (item.score, item.created_at.timestamp()), reverse=True)
        unique: list[RetrievedMemory] = []
        seen: set[str] = set()
        for item in ranked:
            key = f"{item.kind}:{item.text}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) >= desired:
                break
        return unique

    def summary(self, conversation_id: str, limit: int = 6) -> str:
        memories = self._recent_memories(conversation_id, limit)
        if not memories:
            return "none"
        lines = [f"- {item.kind}: {item.text}" for item in memories]
        return "\n".join(lines)

    def _recent_memories(self, conversation_id: str, limit: int) -> list[RetrievedMemory]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT kind, text, created_at
                FROM memory_entries
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [
            RetrievedMemory(
                kind=row["kind"],
                text=row["text"],
                score=0.01 if row["kind"] == "exchange" else 0.02,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def _score_entry(self, query_tokens: set[str], text: str, kind: str) -> float:
        entry_tokens = _tokenize(text)
        if not entry_tokens:
            return 0.0
        overlap = len(query_tokens & entry_tokens)
        if not overlap:
            return 0.0
        kind_bonus = 2.5 if kind == "fact" else 1.0
        coverage = overlap / max(1, min(len(query_tokens), 8))
        density = overlap / len(entry_tokens)
        return round(kind_bonus + coverage + density, 4)

    def _extract_user_facts(self, message: str) -> list[dict[str, str]]:
        memories: list[dict[str, str]] = []
        normalized = _normalize_text(message)
        for category, pattern in _FACT_PATTERNS:
            for match in pattern.finditer(normalized):
                value = _clean_fact_value(category, match.group(1))
                if len(value) < 2:
                    continue
                if category == "name":
                    text = f"User's name is {value}."
                elif category == "location":
                    text = f"User is based in {value}."
                elif category == "work":
                    text = f"User works at {value}."
                elif category == "role":
                    text = f"User's role is {value}."
                elif category == "goal":
                    text = f"User goal: {value}."
                elif category == "preference":
                    text = f"User preference: {value}."
                else:
                    text = f"User risk style: {value.lower()}."
                memories.append({"category": category, "text": text})
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in memories:
            key = f"{item['category']}::{item['text']}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped


def format_recalled_memories(memories: Iterable[RetrievedMemory]) -> str:
    lines = []
    for item in memories:
        prefix = "USER FACT" if item.kind == "fact" else "PAST TURN"
        lines.append(f"- {prefix}: {item.text}")
    return "\n".join(lines) if lines else "none"


conversation_store = ConversationStore()
daily_interaction_store = DailyInteractionStore()
persistent_memory_store = PersistentMemoryStore()
