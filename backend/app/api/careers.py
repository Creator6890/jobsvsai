"""Career Finder — INTERNAL ONLY, excluded from the initial public launch.

This endpoint still reads the legacy `occupation_scores` columns rather than the production
score store, and that is deliberate. Its ranking depends on `salary_potential`,
`future_demand` (both legacy hand-authored columns) and `market_signals.location_demand`
(seeded demo data). None of the three exists anywhere in the Phase 5 engine, and none will
be fabricated to force a migration.

Consequently `/career-finder` is removed from public navigation, from the sitemap, and is
disallowed in robots.txt. The route still functions for internal use and future
redevelopment. The publication gate is deliberately retained below so that even internally
this endpoint can never surface an unpublished occupation.

Resolving this needs a scoping decision, not an implementation: reweight the ranking without
salary/demand, source them properly, or keep the feature out of launch. Do not silently pick
one here.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.publication import public_occupation_predicate
from app.schemas.occupation import CareerFinderRequest, CareerFinderResponse, CareerRecommendation

router = APIRouter(prefix="/careers", tags=["career finder"])

EDUCATION_RANK = {"self_taught": 1, "high_school": 1, "diploma": 2, "bachelors": 3, "masters": 4}
RETRAINING_LIMIT = {"almost_none": 2, "few_months": 6, "six_to_twelve": 12, "major_transition": 48}
COUNTRY_CODES = {
    "india": "IN", "in": "IN", "united states": "US", "usa": "US", "us": "US",
    "united kingdom": "GB", "uk": "GB", "canada": "CA", "australia": "AU",
}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _country_code(value: str) -> str:
    normalized = _normalize(value)
    return COUNTRY_CODES.get(normalized, normalized[:2].upper())


def _parse_months(value: str | None, overlap: float) -> tuple[int, int]:
    if value:
        numbers = [int(number) for number in re.findall(r"\d+", value)]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        if len(numbers) == 1:
            return numbers[0], numbers[0]
    if overlap >= 75:
        return 1, 3
    if overlap >= 60:
        return 3, 6
    if overlap >= 45:
        return 6, 12
    return 12, 24


def _difficulty(months_max: int) -> str:
    if months_max <= 2:
        return "Easy"
    if months_max <= 6:
        return "Easy–Moderate"
    if months_max <= 12:
        return "Moderate"
    return "Major transition"


def _salary_fit(expectation: str, current: float, target: float) -> tuple[float, str]:
    delta = target - current
    direction = "Higher" if delta >= 8 else "Lower" if delta <= -8 else "Similar"
    if expectation == "temporary_decrease":
        return 100.0, direction
    if expectation == "same_or_higher":
        return max(0.0, 100.0 if delta >= 0 else 100.0 + delta * 8), direction
    return max(0.0, 100.0 if delta >= 8 else 100.0 - (8 - delta) * 8), direction


@router.post("/recommendations", response_model=CareerFinderResponse, response_model_by_alias=True)
async def recommendations(
    payload: CareerFinderRequest, session: AsyncSession = Depends(get_session)
) -> CareerFinderResponse:
    country_code = _country_code(payload.country)
    current = (await session.execute(text("""
      SELECT occupation.id, occupation.slug, occupation.title, occupation.education_requirement,
             score.salary_potential::float salary_potential,
             coalesce(jsonb_agg(DISTINCT skill.name) FILTER (WHERE skill.id IS NOT NULL), '[]') skills
      FROM occupations occupation
      JOIN LATERAL (
        SELECT * FROM occupation_scores WHERE occupation_id=occupation.id
        ORDER BY calculated_at DESC, id DESC LIMIT 1
      ) score ON true
      LEFT JOIN occupation_skills occupation_skill ON occupation_skill.occupation_id=occupation.id
      LEFT JOIN skills skill ON skill.id=occupation_skill.skill_id
      WHERE occupation.slug=:slug AND """ + public_occupation_predicate("occupation") + """
      GROUP BY occupation.id, score.salary_potential
    """), {"slug": payload.current_occupation_slug})).mappings().first()
    if current is None:
        raise HTTPException(status_code=404, detail="Current occupation not found")

    model_version = (await session.execute(text("""
      SELECT version FROM scoring_model_versions WHERE is_active ORDER BY created_at DESC LIMIT 1
    """))).scalar_one_or_none()
    rows = (await session.execute(text("""
      SELECT target.slug, target.title, category.name occupation_category,
             target.education_requirement,
             round(latest.ai_exposure)::int ai_exposure,
             round(latest.replacement_risk)::int replacement_risk,
             round(latest.salary_potential)::int salary_potential,
             round(latest.future_demand)::int future_demand,
             relation.skill_overlap::float relationship_overlap,
             relation.transition_difficulty relationship_difficulty,
             relation.retraining_months relationship_months,
             relation.fit_score::float relationship_fit,
             coalesce(market.value::float, latest.future_demand::float) location_demand,
             coalesce(jsonb_agg(jsonb_build_object('name', skill.name, 'importance', occupation_skill.importance))
               FILTER (WHERE skill.id IS NOT NULL), '[]') target_skills
      FROM occupations target
      JOIN occupation_categories category ON category.id=target.category_id
      JOIN LATERAL (
        SELECT * FROM occupation_scores WHERE occupation_id=target.id
        ORDER BY calculated_at DESC, id DESC LIMIT 1
      ) latest ON true
      LEFT JOIN career_relationships relation
        ON relation.source_occupation_id=:source_id
       AND relation.target_occupation_id=target.id
       AND relation.relationship_type='adjacent'
      LEFT JOIN LATERAL (
        SELECT value FROM market_signals
        WHERE occupation_id=target.id AND country_code=:country_code AND signal_type='demand_index'
        ORDER BY observed_at DESC LIMIT 1
      ) market ON true
      LEFT JOIN occupation_skills occupation_skill ON occupation_skill.occupation_id=target.id
      LEFT JOIN skills skill ON skill.id=occupation_skill.skill_id
      WHERE target.id<>:source_id AND """ + public_occupation_predicate("target") + """
      GROUP BY target.id, category.name, latest.ai_exposure, latest.replacement_risk,
               latest.salary_potential, latest.future_demand, relation.skill_overlap,
               relation.transition_difficulty, relation.retraining_months,
               relation.fit_score, market.value
    """), {"source_id": current["id"], "country_code": country_code})).mappings().all()

    supplied_skills = {_normalize(skill) for skill in payload.skills if _normalize(skill)}
    available_skills = supplied_skills | {_normalize(skill) for skill in current["skills"]}
    education_rank = EDUCATION_RANK[payload.education]
    tolerance_max = RETRAINING_LIMIT[payload.retraining_tolerance]
    candidates: list[dict[str, object]] = []

    for row in rows:
        target_skills = list(row["target_skills"])
        total_importance = sum(float(item["importance"]) for item in target_skills) or 1.0
        transferable = [item["name"] for item in target_skills if _normalize(item["name"]) in available_skills]
        missing = [item["name"] for item in target_skills if _normalize(item["name"]) not in available_skills]
        measured_overlap = 100 * sum(
            float(item["importance"]) for item in target_skills if _normalize(item["name"]) in available_skills
        ) / total_importance
        relationship_overlap = row["relationship_overlap"]
        skill_overlap = measured_overlap if relationship_overlap is None else measured_overlap * .45 + float(relationship_overlap) * .55

        months_min, months_max = _parse_months(row["relationship_months"], skill_overlap)
        education_gap = max(0, int(row["education_requirement"]) - education_rank)
        months_min += education_gap * 3
        months_max += education_gap * 6
        experience_discount = min(2, payload.experience_years // 5)
        months_min = max(0, months_min - experience_discount)
        months_max = max(months_min, months_max - experience_discount)
        if months_max > tolerance_max:
            continue

        education_readiness = 100.0 if education_gap == 0 else max(20.0, 100.0 - education_gap * 35)
        experience_readiness = min(100.0, 40.0 + payload.experience_years * 6)
        salary_fit, salary_direction = _salary_fit(
            payload.salary_expectation, float(current["salary_potential"]), float(row["salary_potential"])
        )
        retraining_fit = max(0.0, 100.0 - (months_max / max(tolerance_max, 1)) * 65)
        components = {
            "skillFit": round(skill_overlap, 2),
            "aiResilience": round(100 - float(row["replacement_risk"]), 2),
            "futureDemand": round(float(row["future_demand"]), 2),
            "locationDemand": round(float(row["location_demand"]), 2),
            "salaryFit": round(salary_fit, 2),
            "retrainingFit": round(retraining_fit, 2),
            "educationReadiness": round(education_readiness, 2),
            "experienceReadiness": round(experience_readiness, 2),
        }
        rank_score = (
            components["skillFit"] * .22 + components["aiResilience"] * .20 +
            components["futureDemand"] * .15 + components["locationDemand"] * .10 +
            components["salaryFit"] * .10 + components["retrainingFit"] * .12 +
            components["educationReadiness"] * .06 + components["experienceReadiness"] * .05
        )
        skill_sentence = ", ".join(transferable[:2]) if transferable else "your existing professional foundation"
        candidates.append({
            **dict(row),
            "skill_overlap": round(skill_overlap),
            "ai_resilience": 100 - int(row["replacement_risk"]),
            "estimated_months_min": months_min,
            "estimated_months_max": months_max,
            "retraining_months": f"{months_min}–{months_max} months" if months_min != months_max else f"{months_max} months",
            "transition_difficulty": row["relationship_difficulty"] or _difficulty(months_max),
            "salary_direction": salary_direction,
            "transferable_skills": transferable,
            "missing_skills": missing[:5],
            "rank_score": round(rank_score, 2),
            "score_components": components,
            "why_fit": f"Builds on {skill_sentence}, stays within your {payload.retraining_tolerance.replace('_', ' ')} limit, and reflects demand in {payload.country}.",
        })

    candidates.sort(key=lambda item: float(item["rank_score"]), reverse=True)
    selections: list[tuple[str, dict[str, object]]] = []
    remaining = list(candidates)
    selectors = [
        ("Best overall move", lambda item: float(item["rank_score"]), True),
        ("Safest move", lambda item: float(item["replacement_risk"]), False),
        ("Easiest transition", lambda item: (int(item["estimated_months_max"]), -int(item["skill_overlap"])), False),
        ("Highest upside", lambda item: float(item["salary_potential"]) + float(item["future_demand"]), True),
    ]
    for category, key, reverse in selectors:
        if not remaining:
            break
        selected = sorted(remaining, key=key, reverse=reverse)[0]
        selections.append((category, selected))
        remaining = [item for item in remaining if item["slug"] != selected["slug"]]

    recommendations_out = [CareerRecommendation(
        category=category,
        slug=str(item["slug"]),
        title=str(item["title"]),
        occupation_category=str(item["occupation_category"]),
        ai_exposure=int(item["ai_exposure"]),
        replacement_risk=int(item["replacement_risk"]),
        ai_resilience=int(item["ai_resilience"]),
        skill_overlap=int(item["skill_overlap"]),
        transition_difficulty=str(item["transition_difficulty"]),
        retraining_months=str(item["retraining_months"]),
        estimated_months_min=int(item["estimated_months_min"]),
        estimated_months_max=int(item["estimated_months_max"]),
        salary_direction=str(item["salary_direction"]),
        future_demand=int(item["future_demand"]),
        why_fit=str(item["why_fit"]),
        transferable_skills=list(item["transferable_skills"]),
        missing_skills=list(item["missing_skills"]),
        rank_score=float(item["rank_score"]),
        score_components=dict(item["score_components"]),
    ) for category, item in selections]

    return CareerFinderResponse(
        current_occupation_slug=str(current["slug"]),
        current_occupation_title=str(current["title"]),
        method="structured_rank_v2",
        model_version=model_version or "unknown",
        constraints={
            "experienceYears": payload.experience_years,
            "skills": payload.skills,
            "education": payload.education,
            "country": payload.country,
            "countryCode": country_code,
            "salaryExpectation": payload.salary_expectation,
            "retrainingTolerance": payload.retraining_tolerance,
            "maxRetrainingMonths": tolerance_max,
        },
        recommendations=recommendations_out,
    )
