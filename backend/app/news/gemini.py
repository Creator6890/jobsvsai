"""Gemini implementation of `NewsGenerationProvider`.

The only module in the codebase that imports the Gemini SDK. Everything above it consumes
`GeneratedBrief`, so replacing Gemini is a registry entry — `register_provider` — and not a
change to the service, the repository, the API or the worker.

Secret handling: the key is read from settings at construction, passed to the SDK client,
and never logged, never included in an exception message, and never returned in a result.
`GeminiError` messages are built from status codes and exception *types*, not from raw
provider payloads, because a provider error body can echo request material back.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

from app.news.generation import (
    PROMPT_VERSION,
    GeneratedBrief,
    GenerationInput,
    InvalidGeneratedBrief,
    ProviderNotConfigured,
    parse_provider_response,
)
from app.news.impact_policy import InvalidImpactFactors
from app.news.prompts import RESPONSE_SCHEMA, build_system_instruction, build_user_content

# Verified against ai.google.dev on 2026-08-23: a current Gemini 3 Flash model, documented
# as the primary structured-output example. Overridable via NEWS_LLM_MODEL — a flash-lite
# variant is cheaper if volume ever grows, at some cost to judgement quality on the impact
# rubric.
DEFAULT_MODEL = "gemini-3.7-flash"

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.5


class GeminiError(RuntimeError):
    """A Gemini call failed. Message is safe to show an admin and to store."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class GeminiGenerationProvider:
    """One structured call per candidate."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 45.0,
        sleep=time.sleep,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ProviderNotConfigured(
                "NEWS_LLM_API_KEY is not set. Configure it in the environment before "
                "enabling Gemini generation."
            )
        self.model = model or DEFAULT_MODEL
        self.prompt_version = PROMPT_VERSION
        self._timeout = timeout_seconds
        self._sleep = sleep
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Import and construct lazily.

        Keeps `google-genai` off the import path for every process that never generates —
        the API server, the ingestion job, the test suite — so an absent or broken SDK
        cannot break unrelated work.
        """
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - environment issue, not logic
                raise ProviderNotConfigured(
                    "The google-genai package is not installed."
                ) from exc
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    # ------------------------------------------------------------------ classification

    @staticmethod
    def _classify(error: Exception) -> GeminiError:
        """Decide retryable vs not, from the exception type and any status code.

        Deliberately narrow: only transient transport-level problems are retried. A
        schema-invalid response, a safety refusal or a bad request will fail identically on
        every attempt, so retrying them only burns free-tier quota.
        """
        status = getattr(error, "code", None) or getattr(error, "status_code", None)
        name = type(error).__name__

        if status in (429,) or "ResourceExhausted" in name or "RateLimit" in name:
            return GeminiError("Rate limited by provider (429)", retryable=True)
        if isinstance(status, int) and 500 <= status < 600:
            return GeminiError(f"Provider server error ({status})", retryable=True)
        if any(token in name for token in ("Timeout", "Deadline", "Connection", "Unavailable")):
            return GeminiError(f"Transient transport failure ({name})", retryable=True)
        if isinstance(status, int) and status in (401, 403):
            # Never echo the provider's message here; it can contain request material.
            return GeminiError(
                f"Provider rejected credentials ({status}). Check NEWS_LLM_API_KEY.",
                retryable=False,
            )
        if isinstance(status, int) and 400 <= status < 500:
            return GeminiError(f"Provider rejected the request ({status})", retryable=False)
        return GeminiError(f"Provider call failed ({name})", retryable=False)

    # ------------------------------------------------------------------------- the call

    def _call_once(self, payload: GenerationInput) -> dict[str, Any]:
        """One structured call on the stable `models.generate_content` surface.

        Not `client.interactions.create`, which the current docs feature: that API is marked
        experimental by the SDK itself and changed incompatibly in May 2026 (it now requires
        google-genai >= 2.0.0 and rejects earlier callers with a 400). `generate_content` is
        the long-standing structured-output surface and is the safer dependency for code
        meant to run unattended.
        """
        from google.genai import types

        client = self._get_client()
        response = client.models.generate_content(
            model=self.model,
            contents=build_user_content(payload),
            config=types.GenerateContentConfig(
                system_instruction=build_system_instruction(),
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                http_options=types.HttpOptions(timeout=int(self._timeout * 1000)),
            ),
        )

        text = getattr(response, "text", None) or getattr(response, "output_text", None)
        if not text or not str(text).strip():
            raise GeminiError(
                "Provider returned an empty response (possible safety refusal)",
                retryable=False,
            )
        try:
            parsed = json.loads(str(text))
        except json.JSONDecodeError as exc:
            # Do not include the body: it is untrusted model output that may be large.
            raise GeminiError(
                f"Provider returned non-JSON output ({exc.msg})", retryable=False
            ) from exc

        # Token accounting. `total_token_count` exceeds prompt + candidates because Gemini 3
        # bills reasoning tokens separately (`thoughts_token_count`), so output is derived
        # from the total rather than read from candidates alone — otherwise the recorded
        # spend would understate the bill.
        usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_token_count", None) or getattr(
                usage, "input_tokens", None
            )
            total_tokens = getattr(usage, "total_token_count", None)
            if isinstance(prompt_tokens, int):
                parsed["_input_tokens"] = prompt_tokens
                if isinstance(total_tokens, int):
                    parsed["_output_tokens"] = max(0, total_tokens - prompt_tokens)
                else:
                    candidates = getattr(usage, "candidates_token_count", None)
                    if isinstance(candidates, int):
                        parsed["_output_tokens"] = candidates
        return parsed

    def generate_news_brief(self, payload: GenerationInput) -> GeneratedBrief:
        """Call Gemini once, with bounded retries on transient failures only."""
        last: GeminiError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return parse_provider_response(self._call_once(payload))
            except (InvalidGeneratedBrief, InvalidImpactFactors) as exc:
                # A structurally wrong answer is the model misunderstanding, not a blip.
                # Retrying produces the same answer and spends quota to get it.
                raise GeminiError(f"Invalid response schema: {exc}", retryable=False) from exc
            except GeminiError as exc:
                last = exc
                if not exc.retryable or attempt == MAX_ATTEMPTS:
                    raise
            except Exception as exc:  # noqa: BLE001 - SDK exception types vary by version
                classified = self._classify(exc)
                last = classified
                if not classified.retryable or attempt == MAX_ATTEMPTS:
                    raise classified from exc
            # Exponential backoff with jitter, so a batch does not retry in lockstep.
            self._sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
        raise last or GeminiError("Generation failed", retryable=False)
