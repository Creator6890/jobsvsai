def human_dependency_resistance(value: float) -> float:
    return round(100 - min(100, max(0, value)), 2)
