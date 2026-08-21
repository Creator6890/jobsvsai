"""Compare one versioned candidate task mapping with a reviewed rubric gold item."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai",
    ).replace("postgresql+asyncpg://", "postgresql://", 1)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Report capability, level, constraint, and confidence deviations from a gold mapping.",
    )
    command.add_argument("candidate_mapping_set_id", type=int)
    command.add_argument("--gold-version", default="gold-v1-representative-test")
    command.add_argument("--max-weight-deviation", type=float, default=0.10)
    command.add_argument("--max-level-deviation", type=float, default=15)
    command.add_argument("--max-constraint-deviation", type=float, default=15)
    command.add_argument("--max-confidence-deviation", type=float, default=20)
    command.add_argument("--fail-on-deviation", action="store_true")
    return command


async def compare(arguments: argparse.Namespace) -> tuple[dict[str, object], bool]:
    connection = await asyncpg.connect(database_url())
    try:
        dataset_id = await connection.fetchval(
            "SELECT id FROM task_capability_gold_datasets WHERE dataset_version=$1",
            arguments.gold_version,
        )
        if dataset_id is None:
            raise ValueError(f"Unknown gold dataset version: {arguments.gold_version}")
        encoded = await connection.fetchval(
            "SELECT compare_task_mapping_to_gold($1,$2)::text",
            arguments.candidate_mapping_set_id,
            dataset_id,
        )
    finally:
        await connection.close()

    report = json.loads(encoded)
    capability_rows = report["capabilityDeviations"]
    constraint_rows = report["constraintDeviations"]
    observed = {
        "maximumWeightDeviation": max((float(row["weight_deviation"]) for row in capability_rows), default=0),
        "maximumLevelDeviation": max((float(row["level_deviation"] or 0) for row in capability_rows), default=0),
        "maximumConstraintDeviation": max((float(row["level_deviation"]) for row in constraint_rows), default=0),
        "maximumConfidenceDeviation": max(
            [float(row["confidence_deviation"] or 0) for row in capability_rows + constraint_rows],
            default=0,
        ),
    }
    thresholds = {
        "maximumWeightDeviation": arguments.max_weight_deviation,
        "maximumLevelDeviation": arguments.max_level_deviation,
        "maximumConstraintDeviation": arguments.max_constraint_deviation,
        "maximumConfidenceDeviation": arguments.max_confidence_deviation,
    }
    passed = all(observed[key] <= thresholds[key] for key in thresholds)
    report["evaluation"] = {"passed": passed, "observed": observed, "thresholds": thresholds}
    return report, passed


async def main() -> int:
    arguments = parser().parse_args()
    try:
        report, passed = await compare(arguments)
    except (asyncpg.PostgresError, ValueError) as error:
        print(json.dumps({"error": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if arguments.fail_on_deviation and not passed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
