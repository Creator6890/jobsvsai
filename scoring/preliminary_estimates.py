"""preliminary-estimates-v1 — deterministic preliminary score estimation.

An *estimate* is a score we are willing to show but not willing to call verified. It exists
because 405 occupations have real evidence of varying strength and returning nothing for all
of them serves nobody, while returning them silently alongside verified scores would be a lie
of presentation.

Nothing here calls an external model. Every tier is a deterministic function of data already
imported, and the same inputs always produce the same output.

## The evidence hierarchy

E1  Full task evidence. The validated engine already computed this occupation's score over
    weighted task coverage >= 80 with confidence >= 75. It is not published because it fails
    a *publication* gate — provisional input sensitivity, review-readiness, or a flagged
    anomaly — not because the score could not be computed. This is the strongest possible
    estimate: it is the engine's own answer.

E2  Partial task evidence. The engine computed a score, but over coverage below the 80 launch
    gate. The number is real; the evidence beneath it is thinner.

E3  Related-occupation proxy. No task evidence exists for this occupation. Its score is
    borrowed from the verified occupations O*NET itself asserts are related, weighted by
    relatedness tier. This is the only tier that is genuinely an inference rather than a
    measurement, and it is the only tier that always renders as a range.

E4  Occupation-characteristic archetype. Defined in the vocabulary and deliberately unused:
    no staged occupation lacks verified relatives while still carrying the element ratings an
    archetype would need. Building an unexercised tier would mean shipping untested code and
    an uncalibrated method, so it is not built. See the report.

## What is deliberately not here

There is no title-similarity tier. "Software Developer sounds automatable" is not evidence,
and a plausible number attached to no warrant is worse than an absent one — it is
indistinguishable, to the reader, from a measured result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

POLICY_VERSION = "preliminary-estimates-v1"

# O*NET's own relatedness assertions, weighted by how tight the assertion is. These are the
# only relatedness inputs used: a proxy chosen by title text would reintroduce exactly the
# lexical-coincidence failure that Search V2 exists to remove.
TIER_WEIGHT: dict[str, float] = {
    "Primary-Short": 3.0,
    "Primary-Long": 2.0,
    "Supplemental": 1.0,
}

# The launch gate. An occupation at or above this had complete-enough evidence for the engine
# to stand behind; below it, the engine's answer is real but thinly supported.
FULL_COVERAGE_GATE = 80.0
# Below this, task evidence is thin enough that the estimate renders as a range.
THIN_COVERAGE = 70.0
# Fewer verified relatives than this and the proxy is materially less reliable — leave-one-out
# calibration puts p90 error at 17.8 for 3-5 relatives against 10.0 for 10 or more.
SPARSE_RELATIVES = 6

Confidence = Literal["higher", "moderate", "low"]

# Half-widths for rendered ranges, taken from the leave-one-out p90 error of the tier that
# produces them, rounded up to a whole point. A range narrower than the observed p90 error
# would understate the uncertainty it exists to communicate.
RANGE_HALF_WIDTH: dict[str, dict[str, int]] = {
    "E2": {"exposure": 8, "replacement": 6},
    "E3_dense": {"exposure": 10, "replacement": 8},
    "E3_sparse": {"exposure": 18, "replacement": 12},
}


@dataclass
class RelativeEvidence:
    """One verified occupation a proxy estimate borrows from."""

    occupation_code: str
    title: str
    tier: str
    ai_exposure: float
    replacement_risk: float

    @property
    def weight(self) -> float:
        return TIER_WEIGHT.get(self.tier, 1.0)


@dataclass
class Estimate:
    identity_id: int
    occupation_code: str
    method: str
    method_detail: str
    confidence: Confidence
    ai_exposure: int
    replacement_risk: int
    ai_exposure_low: int | None = None
    ai_exposure_high: int | None = None
    replacement_risk_low: int | None = None
    replacement_risk_high: int | None = None
    evidence_coverage: float | None = None
    evidence_confidence: float | None = None
    supporting_relative_count: int | None = None
    evidence_sources: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_range(self) -> bool:
        return self.ai_exposure_low is not None


def _clamp(value: float) -> int:
    """Round to a whole point and hold inside the index bounds.

    Estimates are integers everywhere. Rendering 72.43 for a number whose p90 error is ten
    points asserts a precision the calibration does not support.
    """
    return max(0, min(100, round(value)))


def _band(low: float, high: float, centre: int, half: int) -> tuple[int, int]:
    del low, high
    return max(0, centre - half), min(100, centre + half)


def estimate_from_task_evidence(
    *,
    identity_id: int,
    occupation_code: str,
    ai_exposure: float,
    replacement_risk: float,
    weighted_task_coverage: float,
    confidence: float,
) -> Estimate:
    """E1 / E2 — the engine already answered; we are deciding how firmly to say it.

    The number is not recomputed and not adjusted. Adjusting a validated engine output because
    we are less sure of it would produce a third quantity that is neither the engine's answer
    nor an honest estimate. What varies is the confidence label and whether a range is shown.
    """
    centre_exposure = _clamp(ai_exposure)
    centre_replacement = _clamp(replacement_risk)

    if weighted_task_coverage >= FULL_COVERAGE_GATE:
        # E1: complete evidence. The occupation is unpublished for policy reasons, not
        # evidential ones, so the estimate is the engine's own number shown as a point.
        return Estimate(
            identity_id=identity_id,
            occupation_code=occupation_code,
            method="E1",
            method_detail=(
                "Validated engine score over complete task evidence; withheld from the "
                "verified cohort by a publication gate rather than by missing evidence."
            ),
            confidence="higher",
            ai_exposure=centre_exposure,
            replacement_risk=centre_replacement,
            evidence_coverage=weighted_task_coverage,
            evidence_confidence=confidence,
        )

    if weighted_task_coverage >= THIN_COVERAGE:
        return Estimate(
            identity_id=identity_id,
            occupation_code=occupation_code,
            method="E2",
            method_detail=(
                "Validated engine score over partial task evidence "
                f"({weighted_task_coverage:.0f}% weighted coverage)."
            ),
            confidence="moderate",
            ai_exposure=centre_exposure,
            replacement_risk=centre_replacement,
            evidence_coverage=weighted_task_coverage,
            evidence_confidence=confidence,
        )

    half = RANGE_HALF_WIDTH["E2"]
    exp_lo, exp_hi = _band(0, 0, centre_exposure, half["exposure"])
    rep_lo, rep_hi = _band(0, 0, centre_replacement, half["replacement"])
    return Estimate(
        identity_id=identity_id,
        occupation_code=occupation_code,
        method="E2",
        method_detail=(
            "Validated engine score over limited task evidence "
            f"({weighted_task_coverage:.0f}% weighted coverage); shown as a range."
        ),
        confidence="low",
        ai_exposure=centre_exposure,
        replacement_risk=centre_replacement,
        ai_exposure_low=exp_lo,
        ai_exposure_high=exp_hi,
        replacement_risk_low=rep_lo,
        replacement_risk_high=rep_hi,
        evidence_coverage=weighted_task_coverage,
        evidence_confidence=confidence,
    )


def estimate_from_relatives(
    *,
    identity_id: int,
    occupation_code: str,
    relatives: list[RelativeEvidence],
) -> Estimate | None:
    """E3 — borrow from the verified occupations O*NET says are related.

    Always a range. A point value would present a borrowed number with the same visual
    authority as a measured one, and the leave-one-out p90 error of ten points says that is
    not warranted. Returns None when there is nothing verified to borrow from; an estimate
    with no source is not a weaker estimate, it is a fabrication.
    """
    if not relatives:
        return None

    total_weight = sum(r.weight for r in relatives)
    exposure = sum(r.ai_exposure * r.weight for r in relatives) / total_weight
    replacement = sum(r.replacement_risk * r.weight for r in relatives) / total_weight

    centre_exposure = _clamp(exposure)
    centre_replacement = _clamp(replacement)

    dense = len(relatives) >= SPARSE_RELATIVES
    half = RANGE_HALF_WIDTH["E3_dense" if dense else "E3_sparse"]
    exp_lo, exp_hi = _band(0, 0, centre_exposure, half["exposure"])
    rep_lo, rep_hi = _band(0, 0, centre_replacement, half["replacement"])

    return Estimate(
        identity_id=identity_id,
        occupation_code=occupation_code,
        method="E3",
        method_detail=(
            f"Weighted average of {len(relatives)} verified related occupations, "
            "weighted by O*NET relatedness tier. No task evidence exists for this occupation."
        ),
        confidence="moderate" if dense else "low",
        ai_exposure=centre_exposure,
        replacement_risk=centre_replacement,
        ai_exposure_low=exp_lo,
        ai_exposure_high=exp_hi,
        replacement_risk_low=rep_lo,
        replacement_risk_high=rep_hi,
        supporting_relative_count=len(relatives),
        evidence_sources=[
            {
                "occupationCode": r.occupation_code,
                "title": r.title,
                "relatednessTier": r.tier,
                "weight": r.weight,
                "aiExposure": r.ai_exposure,
                "replacementRisk": r.replacement_risk,
            }
            for r in sorted(relatives, key=lambda r: (-r.weight, r.occupation_code))
        ],
    )


PUBLIC_CONFIDENCE_LABEL: dict[str, str] = {
    # Deliberately avoids "High confidence": that phrase invites confusion with a verified
    # score, which is a different kind of claim rather than a more confident one.
    "higher": "Higher-confidence estimate",
    "moderate": "Moderate-confidence estimate",
    "low": "Low-confidence estimate",
}

DISCLAIMER = (
    "This occupation does not yet have enough validated task-level evidence for a full "
    "JobsVsAI score. This preliminary estimate uses available occupational data and "
    "related-work evidence."
)
