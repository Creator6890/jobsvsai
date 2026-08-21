def market_resilience(demand: float, openings: float, wage_growth: float) -> float:
    return round(max(0, min(100, demand * 0.5 + openings * 0.3 + wage_growth * 0.2)), 2)
