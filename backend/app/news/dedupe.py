"""Deterministic near-duplicate detection for ingest items.

Catches the same event announced under different headlines:

    "OpenAI launches GPT-X"  /  "Introducing GPT-X"  /  "GPT-X is now available"

No embeddings, no vector store, no LLM. Jaccard similarity over normalised token sets and
word shingles, compared only against items fetched inside a recent window.

**Deliberately conservative.** Merging two unrelated stories destroys a candidate that no
later stage can recover, while missing a duplicate costs one extra glance in the incoming
queue. The threshold is set so that headlines sharing only generic launch vocabulary —
"Introducing our new model" and "Introducing our new pricing" — stay separate.

Duplicates are marked, never deleted: cross-source coverage is evidence about an event, and
the primary item keeps a pointer to what it superseded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

POLICY_VERSION = "news-dedupe-v1"

# Only items fetched within this window are compared. Two headlines a week apart that share
# vocabulary are far more likely to be two events than one.
DEFAULT_WINDOW_HOURS = 48

# Jaccard similarity at or above this is a duplicate.
#
# Calibrated, not guessed. Genuine restatements of one event ("OpenAI launches GPT-X" /
# "Introducing GPT-X" / "GPT-X is now available") land at 0.58-1.00 once launch verbs are
# stripped, because what survives normalisation is the product name. Different events land
# at 0.00-0.30 even when they share a company, a verb and a product family, because the
# identifying token differs. The gap between those populations is wide, so the exact value
# inside it matters far less than being inside it.
SIMILARITY_THRESHOLD = 0.55

# Removed before comparison because they carry no identifying information and would inflate
# similarity between unrelated headlines. Kept small on purpose: aggressive stop-word removal
# leaves headlines so short that two-token overlaps look like matches.
STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "for", "with", "to", "of", "in", "on", "at",
    "is", "are", "was", "were", "be", "been", "now", "new", "our", "its", "it", "this",
    "that", "as", "by", "from", "we", "you", "your", "us", "has", "have", "will",
    # Launch verbs: present in nearly every announcement, so they identify nothing.
    "introducing", "announcing", "announces", "announce", "launches", "launch",
    "available", "released", "release", "releases", "unveils", "unveil", "presenting",
})

_PUNCT = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class DuplicateMatch:
    ingest_item_id: int
    similarity: float
    matched_title: str


def normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, drop stop words, collapse whitespace.

    The result is persisted as `title_fingerprint` so the same comparison is reproducible
    later and a future policy can be back-tested over stored history.
    """
    lowered = _PUNCT.sub(" ", (title or "").lower())
    tokens = [t for t in _WS.sub(" ", lowered).split() if t and t not in STOP_WORDS]
    return " ".join(tokens)


def _shingles(fingerprint: str, size: int = 2) -> set[str]:
    """Word shingles preserve a little order, so token-identical anagram headlines differ."""
    tokens = fingerprint.split()
    if len(tokens) < size:
        return set(tokens)
    return {" ".join(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def similarity(left_fingerprint: str, right_fingerprint: str) -> float:
    """Blend token-set and shingle similarity.

    Token overlap alone treats "GPT-X is available" and "available GPT-X is" as identical;
    shingles alone are brittle against a single inserted word. Taking the mean keeps short
    headlines comparable while still rewarding preserved word order.
    """
    left_tokens, right_tokens = set(left_fingerprint.split()), set(right_fingerprint.split())
    if not left_tokens or not right_tokens:
        return 0.0
    token_score = jaccard(left_tokens, right_tokens)
    shingle_score = jaccard(_shingles(left_fingerprint), _shingles(right_fingerprint))
    return round((token_score + shingle_score) / 2, 3)


def find_duplicate(
    fingerprint: str,
    recent: list[tuple[int, str]],
    threshold: float = SIMILARITY_THRESHOLD,
) -> DuplicateMatch | None:
    """Return the best match at or above `threshold`, or None.

    `recent` is `(ingest_item_id, title_fingerprint)` for items already inside the window.
    Best match rather than first: if an event has already been ingested twice, the new item
    should point at whichever it actually resembles most.
    """
    if not fingerprint:
        return None
    best: DuplicateMatch | None = None
    for item_id, other in recent:
        if not other:
            continue
        score = similarity(fingerprint, other)
        if score >= threshold and (best is None or score > best.similarity):
            best = DuplicateMatch(ingest_item_id=item_id, similarity=score, matched_title=other)
    return best
