"""The single deterministic path to production score currency.

Every public consumer of scores composes its query from the fragments in this module.
No caller writes its own "latest score" clause.

That rule exists because the legacy readers did write their own, and disagreed:
`repositories/occupations.py`, `api/rankings.py` and the related-careers query ordered by
`calculated_at DESC` with no tiebreak, while `api/careers.py` and the admin derivation added
`id DESC`. `occupation_scores` only forbids a timestamp tie *within* one model version, and
rows written in a single transaction share `now()` — so two readers could resolve the same
occupation to different rows. Currency is now decided once, in
`current_production_occupation_scores`, with a fully deterministic ordering.

Publication is a separate concern and lives in `publication.py`. A production score does not
make an occupation public.
"""

# occupations -> canonical identity -> current snapshot -> model version.
#
# Scores are keyed on the canonical identity because that is what the engine scores. The
# editorial `occupations` row is what the public site renders, so a public page requires
# both to exist; occupations without a promoted snapshot simply do not appear.
PRODUCTION_SCORE_JOIN = """
FROM occupations o
JOIN occupation_categories c ON c.id = o.category_id
JOIN canonical_occupation_identities score_identity
  ON score_identity.jobs_vs_ai_occupation_id = o.id
JOIN current_production_occupation_scores score
  ON score.identity_id = score_identity.id
JOIN scoring_model_versions v ON v.id = score.scoring_model_version_id
"""

# Occupation-level factor values, pivoted out of the normalized derivation table.
#
# The resistance factors are stored as the engine computed them (already inverted), so the
# public "dependency" figures are recovered by inverting back. `provisional_weight` is the
# share of replacement-risk weight resting on the provisional regulation/adoption/labour
# models — surfaced rather than hidden, because it is the largest known weakness in the
# current methodology.
FACTOR_LATERAL = """
LEFT JOIN LATERAL (
  SELECT
    max(value) FILTER (WHERE factor_key = 'taskAutomationExposure')            AS task_exposure,
    max(value) FILTER (WHERE factor_key = 'aiCapabilityProximity')             AS ai_capability_proximity,
    max(value) FILTER (WHERE factor_key = 'humanDependencyResistance')         AS human_dependency_resistance,
    max(value) FILTER (WHERE factor_key = 'physicalDependencyResistance')      AS physical_dependency_resistance,
    max(value) FILTER (WHERE factor_key = 'adoptionPressure')                  AS adoption_pressure,
    max(value) FILTER (WHERE factor_key = 'labourMarketResilienceResistance')  AS labour_market_resilience_resistance,
    coalesce(sum(weight) FILTER (WHERE is_provisional_proxy), 0)               AS provisional_weight
  FROM production_score_factor_contributions
  WHERE snapshot_id = score.id
) factor ON true
"""

# Columns shared by the occupation list, detail and search projections.
PRODUCTION_SCORE_COLUMNS = """
       score.id AS snapshot_id,
       round(score.ai_exposure)::int AS ai_exposure,
       round(score.replacement_risk)::int AS replacement_risk,
       score.confidence::float AS confidence,
       score.weighted_task_coverage::float AS weighted_task_coverage,
       factor.task_exposure::float AS task_exposure,
       factor.ai_capability_proximity::float AS ai_capability_proximity,
       round(100 - factor.human_dependency_resistance)::int AS human_dependency,
       round(100 - factor.physical_dependency_resistance)::int AS physical_dependency,
       round(factor.adoption_pressure)::int AS adoption_pressure,
       round(100 - factor.labour_market_resilience_resistance)::int AS labour_market_resilience,
       round(factor.provisional_weight * 100)::float AS provisional_weight_share,
       score.calculated_at::date AS updated_at,
       v.version AS model_version
"""


def production_replacement_risk_scalar(alias: str) -> str:
    """Current production replacement risk for the occupation aliased as `alias`.

    Used where only the one number is needed (related careers). It resolves through the
    same view as everything else, so it cannot drift from the detail page.
    """
    if alias not in {"target", "o"}:
        raise ValueError(f"Unsupported occupation alias for the production score lookup: {alias!r}")
    return f"""
        (SELECT round(inner_score.replacement_risk)::int
         FROM canonical_occupation_identities inner_identity
         JOIN current_production_occupation_scores inner_score
           ON inner_score.identity_id = inner_identity.id
         WHERE inner_identity.jobs_vs_ai_occupation_id = {alias}.id)
    """.strip()
