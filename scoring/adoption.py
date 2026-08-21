def adoption_pressure(value: float, regulatory_friction: float = 0) -> float:
    return round(max(0, min(100, value - regulatory_friction * 0.25)), 2)
