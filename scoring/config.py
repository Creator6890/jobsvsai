from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringModel:
    version: str
    replacement_weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if abs(sum(self.replacement_weights.values()) - 1.0) > 1e-9:
            raise ValueError("Scoring weights must sum to 1.0")


DEFAULT_MODEL = ScoringModel(
    version="JVS 1.0.3",
    replacement_weights={
        "task_exposure": 0.45,
        "ai_capability_proximity": 0.15,
        "human_dependency": 0.15,
        "physical_dependency": 0.10,
        "adoption_pressure": 0.10,
        "market_resilience": 0.05,
    },
)
