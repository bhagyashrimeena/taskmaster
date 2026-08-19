"""Bounded canonical publisher URL resolution for the selected Top 5."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .schemas import CanonicalUrlResolution, PersonalizedNews


_PUBLISHER_HOSTS = {
    "business standard": ("business-standard.com",),
    "economic times": ("economictimes.indiatimes.com",),
    "the hindu": ("thehindu.com",),
    "globenewswire": ("globenewswire.com",),
    "prnewswire": ("prnewswire.com",),
    "kotak neo": ("kotaksecurities.com", "kotakneo.com"),
    "angel one": ("angelone.in",),
    "national law review": ("natlawreview.com",),
}


def story_identity(story: PersonalizedNews) -> str:
    value = f"{story.headline.strip().lower()}|{story.source_name.strip().lower()}"
    return sha256(value.encode("utf-8")).hexdigest()[:24]


def _publisher_hosts(source_name: str) -> tuple[str, ...]:
    key = source_name.strip().lower()
    return _PUBLISHER_HOSTS.get(key, ())


def _is_rejected(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.lower()
    return (
        parts.scheme not in {"http", "https"}
        or not host
        or "vertexaisearch.cloud.google.com" in host
        or host in {"news.google.com", "google.com", "www.google.com"}
        or path in {"", "/"}
        or "/search" in path
        or "/news" == path.rstrip("/")
    )


def _domain_matches(url: str, source_name: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    expected = _publisher_hosts(source_name)
    return bool(expected) and any(host == domain or host.endswith(f".{domain}") for domain in expected)


def _resolve_sync(story: PersonalizedNews) -> str | None:
    query = quote_plus(f'"{story.headline}" "{story.source_name}"')
    request = Request(
        f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en",
        headers={"User-Agent": "WealthCopilot/1.0"},
    )
    try:
        with urlopen(request, timeout=4) as response:
            root = ElementTree.fromstring(response.read())
    except Exception:
        return None

    for item in root.findall("./channel/item")[:5]:
        title = unescape(item.findtext("title") or "")
        link = item.findtext("link") or ""
        source = item.find("source")
        source_url = source.get("url", "") if source is not None else ""
        candidate = link
        if not title or story.source_name.lower() not in title.lower() and not _domain_matches(candidate, story.source_name):
            continue
        if _is_rejected(candidate) or not _domain_matches(candidate, story.source_name):
            continue
        try:
            with urlopen(Request(candidate, headers={"User-Agent": "WealthCopilot/1.0"}), timeout=4) as response:
                final_url = response.geturl()
        except Exception:
            continue
        if not _is_rejected(final_url) and _domain_matches(final_url, story.source_name):
            return final_url
    return None


async def resolve_canonical_urls(stories: list[PersonalizedNews]) -> dict[str, CanonicalUrlResolution]:
    import asyncio

    resolved: dict[str, CanonicalUrlResolution] = {}
    for story in stories:
        url = await asyncio.to_thread(_resolve_sync, story)
        resolved[story_identity(story)] = CanonicalUrlResolution(
            canonical_url=url,
            status="verified" if url else "unavailable",
            resolved_at=datetime.now(timezone.utc),
        )
    return resolved
