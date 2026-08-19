"""Candidate validation, canonicalization, and deduplication."""

from hashlib import sha256
import re
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError

from .schemas import NewsCandidate


_TRACKING_QUERY_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid"}


def canonical_source_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in _TRACKING_QUERY_KEYS
        ]
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def normalized_headline(headline: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", headline.lower()))


def normalize_candidates(raw: Iterable[NewsCandidate | dict[str, Any]]) -> list[NewsCandidate]:
    """Reject malformed/unsourced rows and remove URL or near-headline duplicates."""

    normalized: list[NewsCandidate] = []
    seen_urls: set[str] = set()
    seen_headlines: list[set[str]] = []
    for item in raw:
        data = item.model_dump() if isinstance(item, NewsCandidate) else dict(item)
        if not data.get("id"):
            digest_source = f"{data.get('headline', '')}|{data.get('source_url', '')}"
            data["id"] = sha256(digest_source.encode("utf-8")).hexdigest()[:16]
        try:
            candidate = NewsCandidate.model_validate(data)
        except (ValidationError, TypeError, ValueError):
            continue
        url_key = canonical_source_url(candidate.source_url)
        headline_tokens = set(normalized_headline(candidate.headline).split())
        near_duplicate = any(
            len(headline_tokens & previous) / max(1, len(headline_tokens | previous)) >= 0.72
            for previous in seen_headlines
        )
        if url_key in seen_urls or near_duplicate:
            continue
        seen_urls.add(url_key)
        seen_headlines.append(headline_tokens)
        grounding_uri = candidate.grounding_uri
        if "vertexaisearch.cloud.google.com" in (urlsplit(url_key).hostname or ""):
            grounding_uri = grounding_uri or url_key
        normalized.append(candidate.model_copy(update={"source_url": url_key, "grounding_uri": grounding_uri}))
    normalized.sort(key=lambda candidate: candidate.published_at, reverse=True)
    return normalized
