"""Phase 2 pipeline seams, plus the deterministic pieces that need no provider.

    RSS -> ingest item -> dedupe -> relevance -> generation -> impact -> draft -> review

Fetching and relevance scoring are Protocols only; there is no feed reader yet and this
module makes no network calls. Canonicalisation and hashing are implemented now because
they are pure functions, they define the dedupe contract the schema's UNIQUE constraints
already enforce, and writing them later would mean back-filling hashes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Campaign and referral parameters change per link without changing the article. Stripping
# them is what makes the canonical_url UNIQUE constraint meaningful.
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|source$|at_)")


@dataclass(frozen=True)
class FetchedItem:
    """One entry as a fetcher found it, before any JobsVsAI processing."""

    external_url: str
    original_title: str
    original_excerpt: str | None = None
    source_published_at: str | None = None


def canonicalise_url(url: str) -> str:
    """Reduce a URL to a stable identity: lowercase host, no tracking, no fragment.

    Deliberately keeps the path case-sensitive — plenty of CMSs serve different articles
    from paths differing only in case — and keeps non-tracking query parameters, which can
    select the article on older sites.
    """
    split = urlsplit(url.strip())
    # http and https of the same article are the same article for dedupe purposes, so the
    # scheme is normalised rather than preserved.
    scheme = "https" if split.scheme.lower() in ("", "http", "https") else split.scheme.lower()
    host = split.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    kept = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True)
            if not TRACKING_PARAMS.match(k.lower())]
    path = split.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, urlencode(sorted(kept)), ""))


def content_hash(title: str, excerpt: str | None, source_id: int | None = None) -> str:
    """Identity of the material itself, so a re-published entry collapses to one item.

    Scoped by source when a source is given, matching the schema's
    `UNIQUE (source_id, content_hash)`: the same wording from two different outlets is two
    legitimate pieces of provenance about one event, and collapsing them here would discard
    that. Cross-source overlap is the near-duplicate check's job, not this one's.

    Nothing time-varying is included — no fetched_at — so re-fetching an unchanged entry
    reproduces the same hash and the UNIQUE constraint absorbs it.
    """
    normalised = " ".join(f"{title} {excerpt or ''}".lower().split())
    if source_id is not None:
        normalised = f"{source_id}\x1f{normalised}"
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


class NewsSourceFetcher(Protocol):
    """Phase 2: reads a source's feed and yields entries. No implementation yet."""

    def fetch(self, feed_url: str) -> list[FetchedItem]: ...


class NewsDeduplicator(Protocol):
    """Phase 2: decides whether a fetched item is already known.

    The database already enforces the two hard axes (canonical_url, and content_hash within
    a source). A deduplicator adds the soft axis — near-identical coverage of one event
    across different outlets — which needs judgement the schema cannot express.
    """

    def is_duplicate(self, canonical_url: str, hashed: str) -> bool: ...


class NewsRelevanceFilter(Protocol):
    """Phase 2: cheap deterministic gate before anything reaches a paid or rate-limited API.

    Runs on title and excerpt only. Its job is to reject the obviously irrelevant so the
    generation budget is spent on plausible candidates, not to make editorial judgements.
    """

    def is_relevant(self, title: str, excerpt: str | None) -> bool: ...
