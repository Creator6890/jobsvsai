"""RSS 2.0 and Atom parsing, and the HTTP fetcher that feeds it.

Parsing is deliberately narrow. We need six fields per entry — title, link, summary,
published date, categories — and nothing else, so this reads that subset rather than
modelling the formats. `feedparser` was considered and not used: its liberal coercion of
malformed input is a liability in a pipeline whose defining property is determinism, and it
is a large dependency for a small need.

Security posture for untrusted feed XML:
  * `defusedxml` refuses entity declarations. Stdlib ElementTree expands *internal* entities
    (verified: a billion-laughs document parses), which is a denial-of-service vector on
    input we do not control.
  * Responses are size-capped before parsing, so a hostile or broken feed cannot exhaust
    memory.
  * Summaries are reduced to plain text here, at the boundary. No feed HTML is stored, and
    therefore none can reach a template.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from defusedxml import ElementTree as SafeET

from app.news.pipeline import FetchedItem, canonicalise_url, content_hash

# Identifies us to feed operators, with a contact path. A pipeline reading free feeds should
# be attributable.
USER_AGENT = "JobsVsAI-NewsBot/1.0 (+https://jobsvsai.com/about)"

REQUEST_TIMEOUT_SECONDS = 20.0
# Feeds are metadata documents. Anything past this is not a feed we want to parse; the
# largest seeded feed is ~700KB.
MAX_FEED_BYTES = 5 * 1024 * 1024
# Excerpts are triage context, not content. Long enough to judge relevance, short enough
# that we are plainly not storing an article.
MAX_EXCERPT_CHARS = 600

ATOM_NS = "{http://www.w3.org/2005/Atom}"

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


class FeedError(RuntimeError):
    """A feed could not be fetched or parsed. Never fatal to a run."""


@dataclass(frozen=True)
class ParsedEntry:
    """One normalised feed entry, before dedupe or relevance."""

    external_url: str
    canonical_url: str
    original_title: str
    original_excerpt: str | None
    source_published_at: datetime | None
    content_hash: str
    categories: list[str] = field(default_factory=list)


def to_plain_text(raw: str | None, limit: int = MAX_EXCERPT_CHARS) -> str | None:
    """Reduce feed HTML to bounded plain text.

    Feed descriptions routinely contain markup, tracking pixels and occasionally scripts.
    Stripping at ingestion rather than at render means there is exactly one place to get
    this right, and no stored value that a future template could trust by mistake.
    """
    if not raw:
        return None
    # Decode BEFORE stripping, then strip again after a second decode.
    #
    # The order matters and the obvious order is wrong: stripping first leaves
    # "&lt;script&gt;" untouched, and the subsequent decode turns it into a live "<script>".
    # Decoding first means an entity-encoded tag becomes a real tag while the stripper can
    # still see it. The second pass covers one level of double encoding.
    text = html.unescape(raw)
    text = _SCRIPT_STYLE.sub(" ", text)
    text = _TAGS.sub(" ", text)
    text = _TAGS.sub(" ", html.unescape(text))
    collapsed = _WHITESPACE.sub(" ", text).strip()
    if not collapsed:
        return None
    return collapsed[:limit].rstrip()


def parse_feed_datetime(value: str | None) -> datetime | None:
    """Accept RFC 822 (RSS) and ISO 8601 (Atom); return None rather than guessing.

    A wrong date silently corrupts the lookback window and the near-duplicate window, so an
    unparseable date is treated as absent.
    """
    if not value or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed is None:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _text(element, *names: str) -> str | None:
    for name in names:
        found = element.find(name)
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return None


def _atom_link(entry) -> str | None:
    """Prefer rel="alternate"; fall back to the first link with an href."""
    links = entry.findall(f"{ATOM_NS}link")
    for link in links:
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return link.get("href")
    for link in links:
        if link.get("href"):
            return link.get("href")
    return None


def parse_feed(source_id: int, raw: str | bytes) -> list[ParsedEntry]:
    """Parse an RSS or Atom document into normalised entries.

    A malformed *document* raises FeedError. A malformed *entry* is skipped: one bad item in
    a 1,000-item feed must not cost us the other 999.
    """
    try:
        root = SafeET.fromstring(raw)
    except Exception as error:  # defusedxml raises its own types for entity abuse
        raise FeedError(f"Feed is not parseable XML: {type(error).__name__}: {error}") from error

    tag = root.tag.lower()
    if tag == "rss" or root.find("channel") is not None:
        raw_entries = root.findall(".//item")
        reader = _read_rss_entry
    elif tag == f"{ATOM_NS}feed".lower() or root.tag == f"{ATOM_NS}feed":
        raw_entries = root.findall(f"{ATOM_NS}entry")
        reader = _read_atom_entry
    else:
        raise FeedError(f"Document root {root.tag!r} is neither RSS nor Atom")

    entries: list[ParsedEntry] = []
    for raw_entry in raw_entries:
        try:
            entry = reader(source_id, raw_entry)
        except Exception:  # noqa: BLE001 - a single malformed entry is not a run failure
            continue
        if entry is not None:
            entries.append(entry)
    return entries


def _build(source_id: int, url: str | None, title: str | None, summary: str | None,
           published: str | None, categories: list[str]) -> ParsedEntry | None:
    """An entry without a link or a title is not usable; drop it rather than store a stub."""
    if not url or not url.strip() or not title or not title.strip():
        return None
    clean_title = _WHITESPACE.sub(" ", html.unescape(title)).strip()
    excerpt = to_plain_text(summary)
    return ParsedEntry(
        external_url=url.strip(),
        canonical_url=canonicalise_url(url),
        original_title=clean_title,
        original_excerpt=excerpt,
        source_published_at=parse_feed_datetime(published),
        content_hash=content_hash(clean_title, excerpt, source_id),
        categories=[c for c in categories if c],
    )


def _read_rss_entry(source_id: int, item) -> ParsedEntry | None:
    return _build(
        source_id,
        _text(item, "link", "guid"),
        _text(item, "title"),
        _text(item, "description", "summary"),
        _text(item, "pubDate", "published", "date"),
        [c.text.strip() for c in item.findall("category") if c.text and c.text.strip()],
    )


def _read_atom_entry(source_id: int, entry) -> ParsedEntry | None:
    return _build(
        source_id,
        _atom_link(entry),
        _text(entry, f"{ATOM_NS}title"),
        _text(entry, f"{ATOM_NS}summary", f"{ATOM_NS}content"),
        _text(entry, f"{ATOM_NS}published", f"{ATOM_NS}updated"),
        [c.get("term", "").strip() for c in entry.findall(f"{ATOM_NS}category") if c.get("term")],
    )


class HttpFeedFetcher:
    """Fetches a feed over HTTP. Implements the Phase 1 `NewsSourceFetcher` protocol.

    One feed per call, and every failure mode raises `FeedError` so the orchestrator can
    record it against the source and continue with the next one.
    """

    def __init__(self, timeout: float = REQUEST_TIMEOUT_SECONDS,
                 max_bytes: int = MAX_FEED_BYTES) -> None:
        self._timeout = timeout
        self._max_bytes = max_bytes

    def fetch_raw(self, feed_url: str) -> bytes:
        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5"},
            ) as client:
                with client.stream("GET", feed_url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_bytes:
                            raise FeedError(
                                f"Feed exceeded {self._max_bytes} bytes; refusing to parse"
                            )
                    return bytes(body)
        except FeedError:
            raise
        except httpx.HTTPError as error:
            raise FeedError(f"{type(error).__name__}: {error}") from error

    def fetch(self, feed_url: str, source_id: int = 0) -> list[FetchedItem]:
        """Protocol-shaped entry point, kept for interface compatibility."""
        return [
            FetchedItem(
                external_url=entry.external_url,
                original_title=entry.original_title,
                original_excerpt=entry.original_excerpt,
                source_published_at=(
                    entry.source_published_at.isoformat() if entry.source_published_at else None
                ),
            )
            for entry in self.fetch_entries(feed_url, source_id)
        ]

    def fetch_entries(self, feed_url: str, source_id: int) -> list[ParsedEntry]:
        return parse_feed(source_id, self.fetch_raw(feed_url))
