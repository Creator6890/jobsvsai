"""Generate preliminary occupation estimates for the staged cohort.

Deterministic and zero-cost: no external model is contacted, and `--dry-run` writes nothing.

    docker compose run --rm -e PYTHONPATH=/app/scoring worker \\
        python -m scoring.run_preliminary_estimates --run-version <key> --dry-run

Calibration is measured on every run, against the verified cohort as it stands at that
moment, and stored on the run row. An estimate should always be traceable to the evidence
that justified publishing it, and "we checked once, months ago" is not that.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from .probe_occupation_score import probe as probe_occupation
    from .preliminary_estimates import (
        POLICY_VERSION,
        RelativeEvidence,
        estimate_from_relatives,
        estimate_from_task_evidence,
    )
except ImportError:  # invoked as a bare script; see CLAUDE.md on PYTHONPATH
    from probe_occupation_score import probe as probe_occupation  # type: ignore[no-redef]
    from preliminary_estimates import (  # type: ignore[no-redef]
        POLICY_VERSION,
        RelativeEvidence,
        estimate_from_relatives,
        estimate_from_task_evidence,
    )

STAGED_WITH_TASK_EVIDENCE = """
SELECT ci.id AS identity_id, r.occupation_code, r.title,
       r.ai_exposure::float AS ai_exposure,
       r.replacement_risk::float AS replacement_risk,
       r.weighted_task_coverage::float AS coverage,
       r.confidence::float AS confidence
FROM phase6_launch_triage_results r
JOIN canonical_occupation_identities ci ON ci.current_source_code = r.occupation_code
JOIN occupation_publications p ON p.identity_id = ci.id
WHERE r.triage_run_id = :triage_run
  AND p.activation_status = 'staged'
  AND r.ai_exposure IS NOT NULL
  AND r.replacement_risk IS NOT NULL
"""

STAGED_WITHOUT_TASK_EVIDENCE = """
SELECT ci.id AS identity_id, ci.current_source_code AS occupation_code,
       COALESCE(n.title, ci.current_source_code) AS title
FROM occupation_publications p
JOIN canonical_occupation_identities ci ON ci.id = p.identity_id
LEFT JOIN onet_occupations n ON n.onet_soc_code = ci.current_source_code
WHERE p.activation_status = 'staged'
  AND ci.current_source_code NOT IN (
      SELECT occupation_code FROM phase6_launch_triage_results WHERE triage_run_id = :triage_run)
"""

VERIFIED_RELATIVES = """
SELECT ro.related_occupation_code AS occupation_code,
       COALESCE(n.title, ro.related_title) AS title,
       ro.relatedness_tier AS tier,
       c.ai_exposure::float AS ai_exposure,
       c.replacement_risk::float AS replacement_risk
FROM onet_related_occupations ro
JOIN canonical_occupation_identities ci ON ci.current_source_code = ro.related_occupation_code
JOIN current_production_occupation_scores c ON c.identity_id = ci.id
LEFT JOIN onet_occupations n ON n.onet_soc_code = ro.related_occupation_code
WHERE ro.occupation_code = :soc AND ro.related_occupation_code <> :soc
"""

ALL_VERIFIED = """
SELECT ci.current_source_code AS soc, c.ai_exposure::float AS ai_exposure,
       c.replacement_risk::float AS replacement_risk
FROM current_production_occupation_scores c
JOIN canonical_occupation_identities ci ON ci.id = c.identity_id
"""


def _band(value: float) -> str:
    return ("Very high" if value >= 75 else "High" if value >= 60
            else "Moderate" if value >= 40 else "Low")


FULLY_MAPPED = """
SELECT count(*) FILTER (WHERE t.weighting_eligible) AS eligible,
       count(DISTINCT m.onet_task_id) FILTER (WHERE t.weighting_eligible) AS mapped
FROM onet_tasks t
LEFT JOIN ai_generated_task_mappings m ON m.onet_task_id = t.task_id
WHERE t.occupation_code = :soc AND t.is_current
"""


async def _fully_mapped(conn, soc: str) -> bool:
    """Does every weighting-eligible task already carry a mapping?

    A cheap gate in front of the probe, which loads the whole dependency graph and is far too
    expensive to run speculatively for every unscored occupation.
    """
    row = (await conn.execute(text(FULLY_MAPPED), {"soc": soc})).mappings().first()
    return bool(row and row["eligible"] and row["mapped"] >= row["eligible"])


async def _relatives(conn, soc: str) -> list[RelativeEvidence]:
    rows = (await conn.execute(text(VERIFIED_RELATIVES), {"soc": soc})).mappings().all()
    return [
        RelativeEvidence(
            occupation_code=r["occupation_code"], title=r["title"], tier=r["tier"],
            ai_exposure=r["ai_exposure"], replacement_risk=r["replacement_risk"],
        )
        for r in rows
    ]


async def calibrate(conn) -> dict:
    """Leave-one-out error of the E3 proxy against every verified occupation.

    The occupation's own score is never visible to the estimator: it is reconstructed purely
    from its verified relatives, exactly as a staged occupation's would be.
    """
    verified = (await conn.execute(text(ALL_VERIFIED))).mappings().all()
    errors = {"exposure": [], "replacement": []}
    agree = {"exposure": 0, "replacement": 0}
    scored = 0

    for v in verified:
        relatives = await _relatives(conn, v["soc"])
        estimate = estimate_from_relatives(
            identity_id=0, occupation_code=v["soc"], relatives=relatives)
        if estimate is None:
            continue
        scored += 1
        errors["exposure"].append(abs(v["ai_exposure"] - estimate.ai_exposure))
        errors["replacement"].append(abs(v["replacement_risk"] - estimate.replacement_risk))
        agree["exposure"] += _band(v["ai_exposure"]) == _band(estimate.ai_exposure)
        agree["replacement"] += _band(v["replacement_risk"]) == _band(estimate.replacement_risk)

    def stats(key: str) -> dict:
        e = sorted(errors[key])
        pick = lambda q: e[min(int(len(e) * q), len(e) - 1)]
        return {
            "mae": round(statistics.mean(e), 2),
            "median": round(statistics.median(e), 2),
            "p90": round(pick(0.90), 2),
            "p95": round(pick(0.95), 2),
            "max": round(e[-1], 2),
            "bandAgreementPct": round(agree[key] / len(e) * 100, 1),
        }

    return {
        "method": "E3 leave-one-out against the verified cohort",
        "verifiedOccupations": len(verified),
        "calibrated": scored,
        "aiExposure": stats("exposure"),
        "replacementRisk": stats("replacement"),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", required=True)
    parser.add_argument("--triage-run", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish", action="store_true",
                        help="mark generated estimates published (ignored under --dry-run)")
    args = parser.parse_args()

    started = time.perf_counter()
    engine = create_async_engine(os.environ["DATABASE_URL"])

    async with engine.begin() as conn:
        calibration = await calibrate(conn)

        estimates = []
        tiers: dict[str, int] = {"E1": 0, "E2": 0, "E3": 0, "E4": 0, "insufficient": 0}
        insufficient: list[str] = []
        probe_notes: dict[str, dict] = {}

        with_tasks = (await conn.execute(
            text(STAGED_WITH_TASK_EVIDENCE), {"triage_run": args.triage_run})).mappings().all()
        for row in with_tasks:
            est = estimate_from_task_evidence(
                identity_id=row["identity_id"], occupation_code=row["occupation_code"],
                ai_exposure=row["ai_exposure"], replacement_risk=row["replacement_risk"],
                weighted_task_coverage=row["coverage"], confidence=row["confidence"])
            estimates.append(est)
            tiers[est.method] += 1

        without = (await conn.execute(
            text(STAGED_WITHOUT_TASK_EVIDENCE), {"triage_run": args.triage_run})).mappings().all()
        raw = await conn.get_raw_connection()
        asyncpg_conn = raw.driver_connection
        for row in without:
            # An occupation's own engine evidence always outranks a related-occupation proxy.
            # These occupations were never in a Phase 5 namespace, but a few already carry
            # complete task mappings, and where they do the engine can answer directly.
            # Reaching for relatives while the occupation's own mappings sit unused would mean
            # choosing the weaker evidence because it happened to be easier to reach.
            own = None
            if await _fully_mapped(conn, row["occupation_code"]):
                own = await probe_occupation(asyncpg_conn, row["occupation_code"])
            if own and own.get("weightedTaskCoverage"):
                est = estimate_from_task_evidence(
                    identity_id=row["identity_id"], occupation_code=row["occupation_code"],
                    ai_exposure=float(own["aiExposure"]),
                    replacement_risk=float(own["replacementRisk"]),
                    weighted_task_coverage=float(own["weightedTaskCoverage"]),
                    confidence=float(own["confidence"]))
                probe_notes[row["occupation_code"]] = {
                    "title": own["occupation"],
                    "launchEligible": own["launchEligible"],
                    "blockingFindings": own["blockingFindings"],
                    "maximumAbsoluteScoreImpact": own["maximumAbsoluteScoreImpact"]}
                estimates.append(est)
                tiers[est.method] += 1
                continue
            est = estimate_from_relatives(
                identity_id=row["identity_id"], occupation_code=row["occupation_code"],
                relatives=await _relatives(conn, row["occupation_code"]))
            if est is None:
                tiers["insufficient"] += 1
                insufficient.append(f"{row['occupation_code']} {row['title']}")
                continue
            estimates.append(est)
            tiers[est.method] += 1

        elapsed = time.perf_counter() - started
        summary = {
            "runVersion": args.run_version,
            "policyVersion": POLICY_VERSION,
            "staged": len(with_tasks) + len(without),
            "tiers": tiers,
            "estimatesProduced": len(estimates),
            "insufficientEvidence": tiers["insufficient"],
            "confidence": {
                c: sum(1 for e in estimates if e.confidence == c)
                for c in ("higher", "moderate", "low")
            },
            "rangesShown": sum(1 for e in estimates if e.is_range),
            "calibration": calibration,
            "scoredFromOwnMappings": probe_notes,
            "externalModelCalls": 0,
            "elapsedSeconds": round(elapsed, 2),
            "persisted": not args.dry_run,
        }

        if args.dry_run:
            print(json.dumps(summary, indent=2))
            print("\ninsufficient evidence:")
            for line in insufficient:
                print(f"  {line}")
            return

        run_id = (await conn.execute(text("""
            INSERT INTO occupation_score_estimate_runs
                (run_key, policy_version, source_promotion_run_id, status,
                 estimates_written, tier_totals, calibration, external_model_calls, provenance)
            VALUES (:k, :p,
                    (SELECT promotion_run_id FROM current_production_occupation_scores LIMIT 1),
                    'completed', :n, :t, :c, 0, :prov)
            RETURNING id
        """), {
            "k": args.run_version, "p": POLICY_VERSION, "n": len(estimates),
            "t": json.dumps(tiers), "c": json.dumps(calibration),
            "prov": json.dumps({"triageRunId": args.triage_run,
                                "insufficientEvidence": insufficient,
                                "scoredFromOwnMappings": probe_notes}),
        })).scalar_one()

        for est in estimates:
            await conn.execute(text("""
                INSERT INTO occupation_score_estimates
                    (estimate_run_id, identity_id, occupation_code, estimate_method,
                     estimate_method_detail, estimate_confidence, evidence_coverage,
                     evidence_confidence, supporting_relative_count,
                     ai_exposure_estimate, ai_exposure_low, ai_exposure_high,
                     replacement_risk_estimate, replacement_risk_low, replacement_risk_high,
                     evidence_sources, is_published)
                VALUES (:run, :ident, :code, :method, :detail, :conf, :cov, :econf, :rel,
                        :ae, :ael, :aeh, :rr, :rrl, :rrh, :src, :pub)
            """), {
                "run": run_id, "ident": est.identity_id, "code": est.occupation_code,
                "method": est.method, "detail": est.method_detail, "conf": est.confidence,
                "cov": est.evidence_coverage, "econf": est.evidence_confidence,
                "rel": est.supporting_relative_count,
                "ae": est.ai_exposure, "ael": est.ai_exposure_low, "aeh": est.ai_exposure_high,
                "rr": est.replacement_risk, "rrl": est.replacement_risk_low,
                "rrh": est.replacement_risk_high,
                "src": json.dumps(est.evidence_sources), "pub": args.publish,
            })

        summary["estimateRunId"] = run_id
        print(json.dumps(summary, indent=2))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
