"""Provider reliability and per-run usage accounting.

Two production incidents drive this file.

The first supervised batch failed twice against Gemini — a 504 then a 503 — with every failing
attempt running 41-45s against a 45s client deadline while the only call that ever succeeded
took 10.1s. Attempts pinned to the deadline are the client cutting the request off, not the
provider being down.

The second is quieter and was found while reading the audit rows afterwards: those failed runs
recorded token counts they never spent. A run read its usage back from the ingest items at the
end, and an item keeps the counts of whatever call last succeeded on it, so two failed retries
each claimed the 1469/615 tokens of the successful call before them. The sum over run rows
reached 4407/1845 against a true 1469/615.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.news import gemini
from app.news.gemini import GeminiError, GeminiGenerationProvider
from app.news.generation_service import GenerationCounters, ItemOutcome, decide_status


class _Status(Exception):
    """Stands in for an SDK error carrying an HTTP status."""

    def __init__(self, code: int) -> None:
        super().__init__(f"status {code}")
        self.code = code


class _Named(Exception):
    """Stands in for an SDK error identified by its type name rather than a status."""


def outcome(item_id: int, result: str, **kwargs) -> ItemOutcome:
    """Build an ItemOutcome with the identity fields the service always supplies."""
    return ItemOutcome(
        ingest_item_id=item_id,
        source_name="Fixture Source",
        original_title="Fixture title",
        relevance_score=81,
        outcome=result,
        **kwargs,
    )


# --- 1 & 2. per-run usage accounting -------------------------------------------------------


def _sum_usage(outcomes: list[ItemOutcome]) -> tuple[int, int]:
    """The accounting the service performs when it closes a run."""
    return (sum(o.input_tokens or 0 for o in outcomes),
            sum(o.output_tokens or 0 for o in outcomes))


def test_successful_run_records_its_own_usage() -> None:
    accepted = outcome(1, "accepted", input_tokens=1469, output_tokens=615)
    assert _sum_usage([accepted]) == (1469, 615)


def test_failed_run_does_not_inherit_previous_item_tokens() -> None:
    """The production defect, reproduced exactly.

    Item 25 had 1469/615 from one successful call. Two later attempts failed with no usage
    returned. Each failed run must report zero, not the item's history.
    """
    failed = outcome(25, "failed", error="Provider server error (503)", error_kind="server_error")
    assert failed.input_tokens is None and failed.output_tokens is None
    assert _sum_usage([failed]) == (0, 0)


def test_run_totals_do_not_accumulate_across_repeated_failures() -> None:
    """Three runs against one item: one success, two failures. The sum must be 1469/615."""
    success = outcome(25, "rejected", input_tokens=1469, output_tokens=615)
    fail_504 = outcome(25, "failed", error_kind="timeout")
    fail_503 = outcome(25, "failed", error_kind="server_error")

    total_in = total_out = 0
    for run in ([success], [fail_504], [fail_503]):
        got_in, got_out = _sum_usage(run)
        total_in += got_in
        total_out += got_out

    assert (total_in, total_out) == (1469, 615), (
        "run rows summed to the production figure 4407/1845 before this fix")


def test_mixed_batch_counts_only_the_calls_that_returned_usage() -> None:
    outcomes = [
        outcome(1, "accepted", input_tokens=1000, output_tokens=400),
        outcome(2, "failed", error_kind="server_error"),
        outcome(3, "rejected", input_tokens=500, output_tokens=100),
    ]
    assert _sum_usage(outcomes) == (1500, 500)


def test_service_no_longer_reads_usage_back_from_the_items() -> None:
    """The mechanism of the bug, asserted directly so it cannot quietly return."""
    import inspect

    from app.news import generation_service
    from app.repositories import news_ingest

    source = inspect.getsource(generation_service)
    assert "token_totals_for_items" not in source
    assert not hasattr(news_ingest, "token_totals_for_items")
    assert "sum(o.input_tokens or 0 for o in outcomes)" in source


def test_counters_start_at_zero() -> None:
    counters = GenerationCounters()
    assert counters.input_tokens == 0 and counters.output_tokens == 0


# --- 3 & 4. retry classification -----------------------------------------------------------


@pytest.mark.parametrize("status,kind", [
    (429, "rate_limited"),
    (500, "server_error"),
    (503, "server_error"),
    (504, "timeout"),
])
def test_transient_statuses_are_retryable(status: int, kind: str) -> None:
    error = GeminiGenerationProvider._classify(_Status(status))
    assert error.retryable is True
    assert error.kind == kind


def test_504_is_classified_as_a_deadline_not_an_outage() -> None:
    """503 and 504 need different operator responses, so they carry different kinds.

    503 means wait for the provider. 504 means the request did not finish inside the deadline
    it was given, which is a client-side knob.
    """
    overload = GeminiGenerationProvider._classify(_Status(503))
    deadline = GeminiGenerationProvider._classify(_Status(504))
    assert overload.kind == "server_error"
    assert deadline.kind == "timeout"
    assert overload.retryable and deadline.retryable


def test_deadline_exceeded_by_type_name_is_a_timeout() -> None:
    error = GeminiGenerationProvider._classify(type("DeadlineExceeded", (_Named,), {})())
    assert error.retryable is True
    assert error.kind == "timeout"


@pytest.mark.parametrize("name", ["Timeout", "ConnectionError", "ServiceUnavailable"])
def test_transport_failures_are_retryable(name: str) -> None:
    assert GeminiGenerationProvider._classify(type(name, (_Named,), {})()).retryable is True


@pytest.mark.parametrize("status,kind", [
    (400, "provider_error"),
    (401, "credentials"),
    (403, "credentials"),
    (404, "provider_error"),
])
def test_client_errors_are_not_retried(status: int, kind: str) -> None:
    """Retrying these fails identically every time and only spends quota."""
    error = GeminiGenerationProvider._classify(_Status(status))
    assert error.retryable is False
    assert error.kind == kind


def test_credential_errors_never_echo_the_provider_message() -> None:
    message = str(GeminiGenerationProvider._classify(_Status(401)))
    assert "NEWS_LLM_API_KEY" in message
    assert "status 401" not in message


def test_unknown_errors_are_not_retried() -> None:
    error = GeminiGenerationProvider._classify(_Named("something odd"))
    assert error.retryable is False
    assert error.kind == "unknown"


def test_retries_stay_bounded_with_backoff_and_jitter() -> None:
    assert gemini.MAX_ATTEMPTS == 3
    assert gemini.BACKOFF_BASE_SECONDS > 0
    import inspect

    source = inspect.getsource(GeminiGenerationProvider)
    assert "random.uniform" in source, "backoff must carry jitter"
    assert "attempt == MAX_ATTEMPTS" in source, "the loop must terminate"
    assert "while True" not in source


# --- 5. the deadline itself -----------------------------------------------------------------


def test_timeout_is_raised_but_still_bounded() -> None:
    """90s: about nine times the observed successful latency, not unlimited waiting."""
    assert gemini.DEFAULT_TIMEOUT_SECONDS == 90.0
    assert get_settings().news_llm_timeout_seconds == 90

    worst_case = gemini.MAX_ATTEMPTS * gemini.DEFAULT_TIMEOUT_SECONDS + sum(
        gemini.BACKOFF_BASE_SECONDS * (2 ** i) for i in range(gemini.MAX_ATTEMPTS - 1))
    assert worst_case < 300, "a single candidate must stay under five minutes"


def test_timeout_is_operator_configurable() -> None:
    provider = GeminiGenerationProvider(api_key="test-key", timeout_seconds=30.0)
    assert provider._timeout == 30.0


# --- 6. a semantic rejection is not a provider failure --------------------------------------


def test_semantic_rejection_is_not_a_provider_failure() -> None:
    """A rejection is a completed call: it returns usage and carries no error kind."""
    rejection = outcome(25, "rejected", input_tokens=1469, output_tokens=615)
    assert rejection.error_kind is None
    assert rejection.error is None
    assert _sum_usage([rejection]) == (1469, 615)


def test_rejection_and_failure_are_distinct_outcomes() -> None:
    failure = outcome(25, "failed", error_kind="server_error")
    rejection = outcome(25, "rejected", input_tokens=10, output_tokens=5)
    assert failure.outcome != rejection.outcome
    assert failure.input_tokens is None and rejection.input_tokens == 10


# --- 7 & 8. the safety surface is untouched --------------------------------------------------


def test_generation_disabled_reaches_no_provider() -> None:
    import inspect

    from app.news import generation_service

    source = inspect.getsource(generation_service)
    assert source.count("generation_enabled") >= 3
    assert "NEWS_GENERATION_ENABLED is false" in source


def test_auto_publish_remains_impossible() -> None:
    import inspect

    from app.news import generation_service

    source = inspect.getsource(generation_service)
    assert source.count(".publish(") == 0
    assert "news_auto_publish" not in source
    assert '"published"' not in inspect.getsource(decide_status)


def test_no_code_branches_on_free_versus_paid_tier() -> None:
    """Nothing may depend on the billing tier; the same integration serves both."""
    import inspect

    from app.news import gemini as gemini_module
    from app.news import generation_service

    for module in (gemini_module, generation_service):
        body = inspect.getsource(module).lower()
        for forbidden in ("free_tier", "is_free", "paid_tier", "billing"):
            assert forbidden not in body, f"{module.__name__} branches on tier: {forbidden}"


def test_pricing_stays_operator_supplied() -> None:
    """Rates move. A constant in business logic would quietly go stale."""
    settings = get_settings()
    assert settings.news_llm_cost_per_1m_input is None
    assert settings.news_llm_cost_per_1m_output is None
