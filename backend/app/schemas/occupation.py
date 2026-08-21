from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(item.capitalize() for item in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TaskImpact(ApiModel):
    onet_task_id: int
    name: str
    importance: str
    exposure: int
    automation_feasibility: int
    augmentation_potential: int


class CareerRelationship(ApiModel):
    """One O*NET-related occupation.

    Carries the relatedness tier and rank O*NET publishes. It deliberately does not carry
    skill overlap, transition difficulty or retraining time: those were hand-seeded for a
    nine-page demo and have no source for the launch cohort.
    """

    slug: str
    title: str
    replacement_risk: int
    relatedness_tier: str
    relatedness_rank: int


class Occupation(ApiModel):
    slug: str
    title: str
    category: str
    summary: str
    verdict: str
    ai_exposure: int
    replacement_risk: int
    task_exposure: float
    ai_capability_proximity: float
    # Numeric 0-100, not the legacy High/Medium/Low band. The engine produces a real
    # confidence value and bucketing it would discard information on the one page that
    # promises transparency.
    confidence: float
    weighted_task_coverage: float
    human_dependency: int
    physical_dependency: int
    adoption_pressure: int
    labour_market_resilience: int
    # Share of replacement-risk weight resting on the provisional regulation/adoption/
    # labour-market models. Surfaced rather than hidden; see the methodology page.
    provisional_weight_share: float
    tasks: list[TaskImpact] = Field(default_factory=list)
    hardest_to_automate_tasks: list[str] = Field(default_factory=list)
    related_careers: list[CareerRelationship] = Field(default_factory=list)
    updated_at: date
    model_version: str
    # Deliberately absent: `trend`, `salary_potential`, `future_demand`. The Phase 5 engine
    # produces none of them and they will not be fabricated. See the Career Finder note in
    # api/careers.py.


class CareerFinderRequest(ApiModel):
    current_occupation_slug: str
    experience_years: int = Field(3, ge=0, le=50)
    skills: list[str] = Field(default_factory=list, max_length=30)
    education: Literal["high_school", "diploma", "bachelors", "masters", "self_taught"] = "bachelors"
    country: str = Field("India", min_length=2, max_length=80)
    salary_expectation: Literal["temporary_decrease", "same_or_higher", "meaningful_increase"] = "same_or_higher"
    retraining_tolerance: Literal["almost_none", "few_months", "six_to_twelve", "major_transition"] = "few_months"


class ScoreFactor(ApiModel):
    key: str
    label: str
    raw_value: float
    transformed_value: float
    transformation: str
    weight: float
    contribution: float
    # Optional so the legacy JVS 1.0.3 derivation endpoint keeps validating. Production
    # snapshots carry both, so provisional-proxy provenance survives promotion instead of
    # being flattened away by the translation into this shape.
    is_provisional_proxy: bool = False
    proxy_model_version: str | None = None


class TaskContribution(ApiModel):
    task_id: int
    task: str
    exposure: float
    importance: float
    frequency: float
    normalized_weight: float
    exposure_contribution: float


class ScoreDerivation(ApiModel):
    score_id: int
    occupation_slug: str
    occupation_title: str
    ai_exposure: float
    replacement_risk: float
    confidence: str
    trend: str
    task_exposure: float
    ai_capability_proximity: float
    model_version: str
    calculated_at: datetime
    calculated_total: float
    input_versions: dict[str, object] = Field(default_factory=dict)
    factors: list[ScoreFactor] = Field(default_factory=list)
    task_contributions: list[TaskContribution] = Field(default_factory=list)


class CareerRecommendation(ApiModel):
    category: str
    slug: str
    title: str
    occupation_category: str
    ai_exposure: int
    replacement_risk: int
    ai_resilience: int
    skill_overlap: int
    transition_difficulty: str
    retraining_months: str
    estimated_months_min: int
    estimated_months_max: int
    salary_direction: str
    future_demand: int
    why_fit: str
    transferable_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    rank_score: float
    score_components: dict[str, float] = Field(default_factory=dict)


class CareerFinderResponse(ApiModel):
    current_occupation_slug: str
    current_occupation_title: str
    method: str
    model_version: str
    constraints: dict[str, object]
    recommendations: list[CareerRecommendation] = Field(default_factory=list)
