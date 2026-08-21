def coverage_confidence(task_coverage: float, source_recency: float, agreement: float) -> tuple[float, str]:
    value = round(max(0, min(100, task_coverage * 0.5 + source_recency * 0.25 + agreement * 0.25)), 2)
    return value, "High" if value >= 80 else "Medium" if value >= 60 else "Low"
