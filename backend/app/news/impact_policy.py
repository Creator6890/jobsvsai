"""news-impact-v1 — the deterministic Jobs Impact policy.

A generation provider returns five factor readings. It does NOT return a level: asking a
model for "high/medium/low" directly produces a judgement with no auditable basis and no
way to recalibrate later without regenerating every article. Here the model supplies
evidence and this module supplies the arithmetic, so the same five numbers always yield the
same score and the same level, forever, for a given policy version.

Jobs Impact is a news-significance indicator. It is not AI Exposure and not Replacement
Risk; it describes an event, not an occupation, and nothing here can affect an occupation
score.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Mapping

POLICY_VERSION = "news-impact-v1"

ImpactLevel = Literal["low", "medium", "high"]

# Ordered so the reasoning and the admin UI can present factors the same way every time.
FACTOR_WEIGHTS: dict[str, Decimal] = {
    "capability_advancement": Decimal("0.30"),
    "commercial_deployability": Decimal("0.25"),
    "breadth_of_affected_work": Decimal("0.20"),
    "adoption_speed": Decimal("0.15"),
    "human_work_reduction_potential": Decimal("0.10"),
}

FACTOR_LABELS: dict[str, str] = {
    "capability_advancement": "Capability advancement",
    "commercial_deployability": "Commercial deployability",
    "breadth_of_affected_work": "Breadth of affected work",
    "adoption_speed": "Adoption speed",
    "human_work_reduction_potential": "Human work reduction potential",
}

# Boundaries are inclusive at the lower edge of each band: 0-34 low, 35-69 medium,
# 70-100 high. 34.5 rounds to 35 and is therefore medium, which is why rounding is
# defined before classification rather than after.
LOW_MAX = Decimal("34")
HIGH_MIN = Decimal("70")

# Below this, an article cannot be auto-published and must sit in review.
MINIMUM_PUBLISH_CONFIDENCE = Decimal("0.80")


class InvalidImpactFactors(ValueError):
    """A factor was missing, non-numeric, or outside 0-100."""


@dataclass(frozen=True)
class ImpactAssessment:
    score: Decimal
    level: ImpactLevel
    policy_version: str
    factors: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "impact_score": float(self.score),
            "impact_level": self.level,
            "impact_policy_version": self.policy_version,
            **self.factors,
        }


def _coerce_factor(name: str, raw: object) -> int:
    if raw is None or isinstance(raw, bool):
        raise InvalidImpactFactors(f"{name} is required and must be a number 0-100")
    try:
        value = Decimal(str(raw))
    except Exception as exc:  # noqa: BLE001 - any parse failure is the same error here
        raise InvalidImpactFactors(f"{name} must be a number 0-100, got {raw!r}") from exc
    if value != value.to_integral_value():
        raise InvalidImpactFactors(f"{name} must be a whole number 0-100, got {raw!r}")
    if not (0 <= value <= 100):
        raise InvalidImpactFactors(f"{name} must be within 0-100, got {raw!r}")
    return int(value)


def classify(score: Decimal | float | int) -> ImpactLevel:
    """Map an already-rounded score to its band."""
    value = Decimal(str(score))
    if value <= LOW_MAX:
        return "low"
    if value >= HIGH_MIN:
        return "high"
    return "medium"


def assess(factors: Mapping[str, object]) -> ImpactAssessment:
    """Compute the Jobs Impact score and level from the five factors.

    Rounding is explicit: the weighted sum is rounded half-up to two decimal places, which
    is the precision the column stores. Classification then runs on that stored value, so
    the level shown can never disagree with the score recorded beside it.
    """
    validated = {name: _coerce_factor(name, factors.get(name)) for name in FACTOR_WEIGHTS}

    total = sum(
        (Decimal(validated[name]) * weight for name, weight in FACTOR_WEIGHTS.items()),
        start=Decimal("0"),
    )
    score = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return ImpactAssessment(
        score=score,
        level=classify(score),
        policy_version=POLICY_VERSION,
        factors=validated,
    )


def requires_review(confidence: Decimal | float | None) -> bool:
    """True when confidence is too low for the article to bypass editorial review.

    A missing confidence is treated as too low. An assessment that cannot state how sure it
    is has not earned the benefit of the doubt.
    """
    if confidence is None:
        return True
    return Decimal(str(confidence)) < MINIMUM_PUBLISH_CONFIDENCE
