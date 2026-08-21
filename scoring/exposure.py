from dataclasses import dataclass


@dataclass(frozen=True)
class TaskScore:
    exposure: float
    importance: float
    frequency: float = 100.0


def calculate_exposure(tasks: list[TaskScore]) -> float:
    """Return importance/frequency-weighted task exposure on a 0–100 scale."""
    if not tasks:
        raise ValueError("At least one task score is required")
    weighted = [(task.exposure, max(0.0, task.importance) * max(0.0, task.frequency)) for task in tasks]
    total_weight = sum(weight for _, weight in weighted)
    if total_weight == 0:
        raise ValueError("Task weights must contain a positive value")
    return round(sum(value * weight for value, weight in weighted) / total_weight, 2)
