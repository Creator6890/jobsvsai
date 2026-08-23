"""Phase 2 ingestion: parsing, normalisation, dedupe, relevance and the run orchestrator.

No test opens a network connection. Feed documents are fixtures and the fetcher is injected,
so the whole pipeline is exercised deterministically.
"""

import pytest

from app.news import dedupe, relevance
from app.news.feeds import (
    FeedError,
    parse_feed,
    parse_feed_datetime,
    to_plain_text,
)
from app.news.pipeline import canonicalise_url, content_hash
from tests.fixtures.feeds import (
    ATOM_VALID,
    ENTITY_BOMB,
    MALFORMED_XML,
    NOT_A_FEED,
    RSS_HOSTILE_HTML,
    RSS_VALID,
)

# ------------------------------------------------------------------------------- parsing


def test_valid_rss_parses_every_usable_entry() -> None:
    entries = parse_feed(1, RSS_VALID)
    assert len(entries) == 3
    first = entries[0]
    assert first.original_title == "Introducing GPT-Pytest"
    assert first.source_published_at is not None
    assert first.source_published_at.year == 2026
    assert first.categories == ["Research", "Models"]
    # CDATA HTML is reduced to plain text at the boundary.
    assert "<b>" not in (first.original_excerpt or "")
    assert "frontier model" in (first.original_excerpt or "")


def test_valid_atom_parses_and_prefers_alternate_link() -> None:
    entries = parse_feed(2, ATOM_VALID)
    # The entry with no link is skipped, not stored as a stub.
    assert len(entries) == 1
    assert entries[0].external_url == "https://pytest-atom.example.com/agent-computer-use"
    assert entries[0].categories == ["agents"]
    assert entries[0].source_published_at is not None


def test_malformed_document_raises_rather_than_returning_junk() -> None:
    with pytest.raises(FeedError):
        parse_feed(1, MALFORMED_XML)
    with pytest.raises(FeedError):
        parse_feed(1, NOT_A_FEED)


def test_entity_expansion_is_refused() -> None:
    """defusedxml must reject the billion-laughs document.

    Stdlib ElementTree expands internal entities, which is why this parser does not use it.
    """
    with pytest.raises(FeedError):
        parse_feed(1, ENTITY_BOMB)


def test_one_malformed_entry_does_not_lose_the_others() -> None:
    entries = parse_feed(2, ATOM_VALID)
    assert [entry.original_title for entry in entries] == [
        "Our AI agent can now use a computer to complete tasks"
    ]


@pytest.mark.parametrize(
    ("raw", "expected_year"),
    [
        ("Fri, 21 Aug 2026 10:00:00 GMT", 2026),   # RFC 822, RSS
        ("2026-08-21T12:00:00Z", 2026),            # ISO 8601, Atom
        ("2026-08-21T12:00:00+02:00", 2026),
    ],
)
def test_both_feed_date_formats_parse(raw: str, expected_year: int) -> None:
    parsed = parse_feed_datetime(raw)
    assert parsed is not None and parsed.year == expected_year
    assert parsed.tzinfo is not None


def test_unparseable_date_becomes_none_rather_than_a_guess() -> None:
    assert parse_feed_datetime("last Tuesday") is None
    assert parse_feed_datetime("") is None
    assert parse_feed_datetime(None) is None


# ------------------------------------------------------------------------- sanitisation


def test_feed_html_becomes_plain_text() -> None:
    entries = parse_feed(1, RSS_HOSTILE_HTML)
    excerpt = entries[0].original_excerpt or ""
    for forbidden in ("<script", "</script", "<style", "<img", "onerror", "steal()"):
        assert forbidden not in excerpt, f"{forbidden!r} survived sanitisation"
    assert "Real text & entities" in excerpt


def test_entities_are_decoded_after_tags_are_stripped() -> None:
    """An entity-encoded tag must not become a live tag once decoded."""
    assert "<script>" not in (to_plain_text("&lt;script&gt;alert(1)&lt;/script&gt;") or "")


def test_excerpts_are_length_limited() -> None:
    assert len(to_plain_text("word " * 5000) or "") <= 600


# -------------------------------------------------------------------- URL normalisation


def test_tracking_parameters_are_removed() -> None:
    dirty = ("https://example.com/post?utm_source=rss&utm_medium=feed&utm_campaign=x"
             "&utm_term=t&utm_content=c&gclid=g&fbclid=f")
    assert canonicalise_url(dirty) == "https://example.com/post"


def test_fragments_and_host_case_are_normalised() -> None:
    assert canonicalise_url("HTTPS://WWW.Example.COM/a/b/#section") == "https://example.com/a/b"


def test_meaningful_query_parameters_are_preserved() -> None:
    assert canonicalise_url("https://example.com/article?id=42&page=2") == \
        "https://example.com/article?id=42&page=2"
    assert canonicalise_url("https://example.com/a?id=7&utm_source=x") == \
        "https://example.com/a?id=7"


def test_distinct_urls_do_not_collapse() -> None:
    """Over-normalisation is worse than under-normalisation: it merges real stories."""
    assert canonicalise_url("https://example.com/a") != canonicalise_url("https://example.com/b")
    assert canonicalise_url("https://example.com/a?id=1") != \
        canonicalise_url("https://example.com/a?id=2")
    # Path case is preserved: plenty of CMSs serve different articles from it.
    assert canonicalise_url("https://example.com/Alpha") != canonicalise_url("https://example.com/alpha")


# --------------------------------------------------------------------------- content hash


def test_content_hash_is_stable_and_source_scoped() -> None:
    assert content_hash("Title", "Body", 1) == content_hash("title  body".replace("  body", ""), "Body", 1)
    assert content_hash("Title", "Body", 1) != content_hash("Title", "Body", 2)
    assert content_hash("Title", "Body", 1) != content_hash("Title", "Other", 1)


def test_content_hash_excludes_changing_metadata() -> None:
    """Re-fetching an unchanged entry must reproduce the same hash."""
    assert content_hash("A", "B", 3) == content_hash("A", "B", 3)


# ------------------------------------------------------------------------- near dedupe


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("OpenAI launches GPT-X", "Introducing GPT-X"),
        ("Introducing GPT-X", "GPT-X is now available"),
        ("OpenAI launches GPT-X", "GPT-X is now available"),
        ("Gemini 3 Flash is here", "Introducing Gemini 3 Flash"),
    ],
)
def test_restatements_of_one_event_are_near_duplicates(left: str, right: str) -> None:
    score = dedupe.similarity(dedupe.normalise_title(left), dedupe.normalise_title(right))
    assert score >= dedupe.SIMILARITY_THRESHOLD, f"{left!r} vs {right!r} scored {score}"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("OpenAI launches GPT-X", "OpenAI launches Sora 2"),
        ("Google DeepMind releases Gemini 3", "Google DeepMind releases AlphaFold 4"),
        ("Introducing our new model", "Introducing our new pricing"),
        ("NVIDIA announces H200 GPU", "NVIDIA announces B300 GPU"),
        ("AI agents automate customer support", "AI agents automate warehouse logistics"),
        ("Claude 4 benchmark results", "GPT-5 benchmark results"),
        ("Humanoid robot picks warehouse orders", "AI model writes code"),
    ],
)
def test_different_events_stay_separate(left: str, right: str) -> None:
    """Shared company, verb and product family must not merge two announcements."""
    score = dedupe.similarity(dedupe.normalise_title(left), dedupe.normalise_title(right))
    assert score < dedupe.SIMILARITY_THRESHOLD, f"{left!r} vs {right!r} scored {score}"


def test_generic_launch_vocabulary_alone_does_not_merge() -> None:
    """Stop words strip the launch verbs, so nothing identifying is left to match on."""
    assert dedupe.normalise_title("Introducing our new thing") == "thing"
    assert dedupe.similarity(
        dedupe.normalise_title("Introducing our new model"),
        dedupe.normalise_title("Announcing our new pricing"),
    ) == 0.0


def test_find_duplicate_returns_the_best_match_not_the_first() -> None:
    recent = [
        (1, dedupe.normalise_title("GPT-X gets a minor update")),
        (2, dedupe.normalise_title("Introducing GPT-X")),
    ]
    match = dedupe.find_duplicate(dedupe.normalise_title("GPT-X is now available"), recent)
    assert match is not None and match.ingest_item_id == 2


def test_empty_fingerprint_never_matches() -> None:
    assert dedupe.find_duplicate("", [(1, "anything")]) is None


# ---------------------------------------------------------------------------- relevance


def test_relevance_policy_version_and_thresholds_are_explicit() -> None:
    assert relevance.POLICY_VERSION == "news-relevance-v1"
    assert relevance.CANDIDATE_THRESHOLD == 40
    assert relevance.CONFIDENT_THRESHOLD == 60


@pytest.mark.parametrize(
    ("title", "excerpt", "tier", "ai_source"),
    [
        ("Introducing GPT-5, our most capable model", "A new frontier model with improved reasoning.", 1, True),
        ("Our AI agent can now use a computer to complete tasks", "Agentic tool use for developer workflows.", 1, True),
        ("Humanoid robot learns warehouse picking autonomously", "Robotics system automates order fulfilment.", 1, True),
        ("New benchmark shows LLM agents automating support tasks", "Study measures automation of customer support.", 2, False),
    ],
)
def test_capability_stories_score_confidently(title, excerpt, tier, ai_source) -> None:
    result = relevance.assess(title, excerpt, [], tier, ai_source)
    assert result.outcome == "candidate"
    assert result.confident, f"{title!r} scored only {result.score}"


@pytest.mark.parametrize(
    ("title", "excerpt", "tier", "ai_source"),
    [
        ("AI company raises $5B in Series D funding", "Valuation reaches $80B after the round.", 2, False),
        ("OpenAI appoints new chief financial officer", "The company names a new CFO.", 1, True),
        ("Nvidia shares fall after quarterly earnings report", "Stock drops on revenue miss.", 2, False),
        ("Fashion model announces new agency partnership", "A model signs with an agency.", 3, False),
        ("Lab opens new office in Dublin", "The company expands its European headquarters.", 1, True),
    ],
)
def test_corporate_and_non_capability_stories_are_ignored(title, excerpt, tier, ai_source) -> None:
    result = relevance.assess(title, excerpt, [], tier, ai_source)
    assert result.outcome == "ignored", f"{title!r} scored {result.score}"


def test_authoritative_source_floats_an_opaque_headline() -> None:
    """The spec's own case: 'Introducing Operator' from a frontier lab is a launch."""
    boosted = relevance.assess("Introducing Operator", "A new product from our team.", [], 1, True)
    assert boosted.outcome == "candidate"

    generic = relevance.assess("Introducing Operator", "A new product from our team.", [], 3, False)
    assert generic.outcome == "ignored"


def test_source_floor_lifts_a_weak_but_positive_first_party_item() -> None:
    """The floor covers the case where the only capability signal is outside the title."""
    result = relevance.assess("Operator", "Now in preview for all users.", [], 1, True)
    assert result.signals["sourceFloorApplied"] is True
    assert result.outcome == "candidate"


def test_source_floor_needs_a_positive_signal_not_just_a_trusted_origin() -> None:
    result = relevance.assess(
        "Lab opens new office in Dublin", "The company expands its European headquarters.",
        [], 1, True,
    )
    assert result.signals["sourceFloorApplied"] is False
    assert result.outcome == "ignored"


def test_source_floor_does_not_rescue_a_corporate_story() -> None:
    """Origin alone must not float a funding or appointment post."""
    result = relevance.assess(
        "Lab raises $5B in Series C funding", "Valuation reaches $80B.", [], 1, True
    )
    assert result.outcome == "ignored"
    assert result.signals["sourceFloorApplied"] is False


def test_ambiguous_words_need_supporting_context() -> None:
    """'model' and 'agent' carry no weight without AI context or an AI-specific source."""
    vague = relevance.assess("The model and the agent met the assistant", None, [], 3, False)
    assert vague.outcome == "ignored"
    supported = relevance.assess(
        "The model is a large language model", "Machine learning research.", [], 1, True
    )
    assert supported.outcome == "candidate"


def test_a_funding_story_that_also_ships_a_model_survives() -> None:
    """Negative signals are down-weighting, never disqualifying."""
    result = relevance.assess(
        "OpenAI raises $5B and launches GPT-6 frontier model", "New model ships today.", [], 1, True
    )
    assert result.outcome == "candidate" and result.confident


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "ignored"), (39, "ignored"), (40, "candidate"), (59, "candidate"), (100, "candidate")],
)
def test_threshold_boundaries(score: int, expected: str) -> None:
    outcome = "candidate" if score >= relevance.CANDIDATE_THRESHOLD else "ignored"
    assert outcome == expected


# --- Regression cases from the supervised live run of 2026-08-23.
#
# Every headline below is a real one that news-relevance-v1 scored wrongly before the
# vocabulary was extended. They are pinned here so the two gaps the live data exposed —
# missing model family names, and exact-token matching that could not see morphological
# variants — cannot silently reopen.


@pytest.mark.parametrize(
    ("title", "excerpt", "tier", "ai_source", "was"),
    [
        # Model family names were entirely absent from the vocabulary, so a headline naming
        # a model but never the word "model" matched nothing at all. Scored 15.
        ("Replit expands access to software creation with GPT-5.6 Luna",
         "Replit introduces Free Mode, powered by GPT-5.6 Luna, so anyone can turn ideas "
         "into working software.", 1, True, 15),
        # Token matching is exact: "robotic" did not match "robot", and "autonomy" did not
        # match "autonomous", so an automation-of-manufacturing story was ignored. Scored 26.
        ("Former SpaceX engineers are building a robotic factory for making steel parts",
         "We're not necessarily building in a dogmatic fashion towards full autonomy.",
         2, False, 26),
        # An AI security story whose only AI vocabulary sat in the excerpt. Scored 26.
        ("Grok exfiltrates user data when malicious instructions are encrypted",
         "Cryptographic Context Injection is only the latest way to break an LLM safety "
         "guardrail.", 2, False, 26),
    ],
)
def test_live_false_negatives_are_now_candidates(title, excerpt, tier, ai_source, was) -> None:
    result = relevance.assess(title, excerpt, [], tier, ai_source)
    assert result.outcome == "candidate", (
        f"{title!r} scored {result.score}; it scored {was} before the live-run fix"
    )


def test_model_family_names_are_recognised_as_ai_terms() -> None:
    """The single largest source of false negatives on live data."""
    for name in ("GPT-5", "Claude", "Gemini", "Llama", "Grok", "Codex", "Sora"):
        result = relevance.assess(f"{name} update ships today", None, [], 2, False)
        assert result.signals["aiTerms"], f"{name!r} matched no AI term"


def test_versioned_model_names_match_their_family() -> None:
    """Real headlines write "GPT-5.6", never bare "GPT". Exact token matching missed them."""
    for title in ("GPT-5 update ships today", "Claude 4 Opus benchmarks",
                  "Llama3 released", "Gemini-1.5 Flash is here"):
        assert relevance.assess(title, None, [], 2, False).signals["aiTerms"], title


def test_version_suffix_matching_does_not_over_match() -> None:
    """Only a digit, hyphen or dot may follow a family name, so ordinary words are safe."""
    for title in ("First aid training course", "Sorafenib trial results",
                  "Aids research funding", "Grokking the basics of pottery"):
        assert relevance.assess(title, None, [], 3, False).signals["aiTerms"] == [], title


def test_morphological_variants_match() -> None:
    """Exact token matching missed 'robotic' where 'robot' was in the vocabulary."""
    robotic = relevance.assess(
        "A robotic factory automates steel production", "Full autonomy is the goal.",
        [], 2, False,
    )
    assert robotic.outcome == "candidate"
    assert "robotic" in robotic.signals["aiTerms"]


def test_live_negative_controls_did_not_regress() -> None:
    """The vocabulary grew; the things that must stay ignored must stay ignored."""
    for title, excerpt, tier, ai_source in [
        ("OpenAI appoints new chief financial officer", "The company names a new CFO.", 1, True),
        ("AI company raises $5B in Series D funding", "Valuation reaches $80B.", 2, False),
        ("Fashion model announces new agency partnership", "A model signs with an agency.", 3, False),
        ("Lab opens new office in Dublin", "The company expands its European headquarters.", 1, True),
    ]:
        assert relevance.assess(title, excerpt, [], tier, ai_source).outcome == "ignored", title


def test_assessment_is_deterministic_and_versioned() -> None:
    args = ("Introducing GPT-5", "A new frontier model.", [], 1, True)
    first, second = relevance.assess(*args), relevance.assess(*args)
    assert first.score == second.score
    assert first.policy_version == relevance.POLICY_VERSION
    assert first.signals["points"] == second.signals["points"]
