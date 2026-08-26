"""Public contract for preliminary occupation estimates.

A separate model from `Occupation`, not a variant of it, and that is the point. `Occupation`
carries task exposure, capability proximity, six replacement-risk factor contributions and a
verified confidence — none of which exist for an estimate. Reusing it would mean filling
those fields with zeros or averages, which is precisely the "missing data is not zero" failure
the project's frozen decisions forbid.

Keeping the shapes distinct also means a client cannot render an estimate as a verified score
by forgetting to check a flag. The two never arrive in the same field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _camel(value: str) -> str:
    head, *rest = value.split("_")
    return head + "".join(part.capitalize() for part in rest)


class EstimatedOccupation(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)

    # Constant, and present in every payload. A consumer of this API should not have to infer
    # the score class from which fields happen to be populated.
    score_status: str = Field(default="estimated", frozen=True)

    slug: str
    title: str
    category: str
    summary: str

    # Integers. The calibrated p90 error is around ten points for the proxy tier; rendering a
    # decimal would assert precision the method does not have.
    ai_exposure: int
    replacement_risk: int

    # Present together or not at all. When present the UI must render a range rather than a
    # point: these are the estimates whose evidence does not support a single number.
    ai_exposure_low: int | None = None
    ai_exposure_high: int | None = None
    replacement_risk_low: int | None = None
    replacement_risk_high: int | None = None

    estimate_method: str
    estimate_method_detail: str
    estimate_confidence: str
    confidence_label: str

    # Weighted task coverage where task evidence exists; null for the proxy tier, where the
    # measure does not apply. Null rather than 0, because 0 would read as "we looked and found
    # no coverage" instead of "coverage is not the relevant measure here".
    evidence_coverage: float | None = None
    supporting_relative_count: int | None = None

    # The verified occupations a proxy estimate borrowed from, so a reader can see the warrant
    # rather than take the number on trust.
    based_on: list[str] = Field(default_factory=list)

    disclaimer: str
