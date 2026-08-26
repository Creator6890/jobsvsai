"""consumer-search-normalize-v1 — query normalisation for occupation search.

Deterministic, tiny, and applied identically at index time and query time. No LLM, no
network, no per-query model call.

Two jobs:

* `normalise` reduces a query to the same shape the materialised term corpus is stored in,
  so an exact match is a plain index lookup rather than a similarity computation.
* `expand_abbreviations` rewrites a handful of career initialisms that O*NET does not carry.

The expansion map is deliberately small and is **not** a synonym ontology. O*NET already
supplies 57,543 alternate titles and 3,316 short titles; anything it knows is read from the
corpus rather than retyped here. What remains are initialisms a person types and no taxonomy
records — "swe", "ml engineer", "soc analyst". Each entry earns its place by being a term a
consumer actually types that resolves to nothing at all without it.
"""

from __future__ import annotations

import re

POLICY_VERSION = "consumer-search-normalize-v1"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise(value: str | None) -> str:
    """Lowercase, replace every non-alphanumeric run with a single space, trim.

    Must stay identical to the `normalized_term` expression in migration 034. If the two ever
    diverge, exact matching silently degrades into fuzzy matching and nothing fails loudly —
    which is why a test compares this function against the migration's own SQL.
    """
    if not value:
        return ""
    return _NON_ALNUM.sub(" ", value.lower()).strip()


# Whole-phrase rewrites, applied before token expansion. These are phrases where expanding
# token by token would produce nonsense: "pen" alone is not "penetration".
_PHRASES: dict[str, str] = {
    "pen tester": "penetration tester",
    "pen testing": "penetration testing",
    "soc analyst": "security operations center analyst",
    "sre": "site reliability engineer",
}

# Single-token expansions. A token is replaced only when it stands alone, so "ai" expands but
# the "ai" inside "aide" cannot.
_TOKENS: dict[str, str] = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "swe": "software engineer",
    "ux": "user experience",
    "ui": "user interface",
    "seo": "search engine optimization",
    "hr": "human resources",
    "it": "information technology",
    "qa": "quality assurance",
    "pm": "project manager",
    "sysadmin": "systems administrator",
    "devops": "development operations",
    "vet": "veterinarian",
}


def expand_abbreviations(normalised_query: str) -> str:
    """Rewrite career initialisms in an already-normalised query.

    Returns the expanded form, which the caller searches *in addition to* the original — never
    instead of it. "it support" must still match the literal term "IT Support" in the O*NET
    corpus, so replacing the query outright would lose more than it gains.
    """
    if not normalised_query:
        return ""

    text = normalised_query
    for phrase, replacement in _PHRASES.items():
        if phrase in text:
            text = text.replace(phrase, replacement)

    tokens = text.split()
    return " ".join(_TOKENS.get(token, token) for token in tokens)


def _plural_variants(form: str) -> list[str]:
    """Singular/plural variants of the final token.

    O*NET titles are plural ("Medical Assistants", "Carpenters", "Economists") and people type
    the singular. Without this, "medical assistant" matched no term exactly and fell through to
    token matching, which reached Health Specialties Teachers — the classic best-of-a-bad-field
    substitution this design exists to prevent.

    Deliberately crude: -s, -es and -ies only. This is orthography, not stemming; a real
    stemmer would conflate distinct occupations ("Bakers"/"Baking") and is not wanted here.
    """
    tokens = form.split()
    if not tokens:
        return []
    head, last = tokens[:-1], tokens[-1]
    variants: list[str] = []

    def add(word: str) -> None:
        candidate = " ".join(head + [word])
        if candidate != form and candidate not in variants:
            variants.append(candidate)

    if last.endswith("ies") and len(last) > 4:
        add(last[:-3] + "y")
    elif last.endswith("es") and len(last) > 3:
        add(last[:-2])
        add(last[:-1])
    elif last.endswith("s") and len(last) > 2:
        add(last[:-1])
    else:
        add(last + "s")
        if last.endswith(("s", "x", "z", "ch", "sh")):
            add(last + "es")
        if last.endswith("y") and len(last) > 2 and last[-2] not in "aeiou":
            add(last[:-1] + "ies")
    return variants


def query_forms(raw: str) -> list[str]:
    """Every normalised form worth looking up, most literal first, de-duplicated.

    Order matters: the caller tries these in sequence and stops at the first tier that
    matches, so the literal query always wins over its expansion.
    """
    base = normalise(raw)
    if not base:
        return []
    forms = [base]
    expanded = expand_abbreviations(base)
    if expanded and expanded != base:
        forms.append(expanded)
    # Plural variants come last: the literal query and its abbreviation expansion both get to
    # match exactly before orthography is guessed at.
    for source in list(forms):
        for variant in _plural_variants(source):
            if variant not in forms:
                forms.append(variant)
    return forms
