from dataclasses import dataclass

from .config import DEFAULT_MODEL, ScoringModel


@dataclass(frozen=True)
class ReplacementInputs:
    task_exposure: float
    ai_capability_proximity: float
    human_dependency: float
    physical_dependency: float
    adoption_pressure: float
    market_resilience: float


@dataclass(frozen=True)
class FactorContribution:
    key: str
    label: str
    raw_value: float
    transformed_value: float
    transformation: str
    weight: float
    contribution: float


@dataclass(frozen=True)
class ReplacementDerivation:
    model_version: str
    total: float
    factors: tuple[FactorContribution, ...]


FACTOR_METADATA = {
    "task_exposure": ("Task exposure", "identity"),
    "ai_capability_proximity": ("AI capability proximity", "identity"),
    "human_dependency": ("Human dependency", "inverse: 100 - raw"),
    "physical_dependency": ("Physical dependency", "inverse: 100 - raw"),
    "adoption_pressure": ("Adoption pressure", "identity"),
    "market_resilience": ("Market resilience", "inverse: 100 - raw"),
}


def calculate_replacement_derivation(
    inputs: ReplacementInputs, model: ScoringModel = DEFAULT_MODEL
) -> ReplacementDerivation:
    """Return the exact, versioned factor math used for replacement risk."""
    raw_values = {
        "task_exposure": inputs.task_exposure,
        "ai_capability_proximity": inputs.ai_capability_proximity,
        "human_dependency": inputs.human_dependency,
        "physical_dependency": inputs.physical_dependency,
        "adoption_pressure": inputs.adoption_pressure,
        "market_resilience": inputs.market_resilience,
    }
    if any(value < 0 or value > 100 for value in raw_values.values()):
        raise ValueError("All scoring inputs must be between 0 and 100")

    transformed_values = {
        **raw_values,
        "human_dependency": 100 - inputs.human_dependency,
        "physical_dependency": 100 - inputs.physical_dependency,
        "market_resilience": 100 - inputs.market_resilience,
    }
    factors = tuple(
        FactorContribution(
            key=key,
            label=FACTOR_METADATA[key][0],
            raw_value=round(raw_values[key], 4),
            transformed_value=round(transformed_values[key], 4),
            transformation=FACTOR_METADATA[key][1],
            weight=weight,
            contribution=round(transformed_values[key] * weight, 4),
        )
        for key, weight in model.replacement_weights.items()
    )
    return ReplacementDerivation(
        model_version=model.version,
        total=round(sum(factor.contribution for factor in factors), 2),
        factors=factors,
    )


def calculate_replacement_risk(inputs: ReplacementInputs, model: ScoringModel = DEFAULT_MODEL) -> float:
    """Combine pressure and resilience inputs into explainable replacement risk."""
    return calculate_replacement_derivation(inputs, model).total
