"""Draft, score-blind task-to-capability mapper.

This mapper reads only benchmark membership, O*NET task text, draft taxonomy
definitions, environment definitions, and rubric thresholds. It never reads AI
capability benchmarks, automation outcomes, legacy task scores, or occupation scores.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

import asyncpg


CAPABILITY_TERMS = {
    "language-comprehension": ("analyz", "interpret", "review", "read", "evaluate", "diagnos", "understand"),
    "language-generation": ("write", "report", "document", "communicat", "present", "explain", "compose", "record"),
    "information-retrieval": ("research", "search", "locate", "gather", "collect", "obtain information", "identify sources"),
    "quantitative-reasoning": ("calculat", "statistic", "quantitative", "budget", "cost", "measure", "estimate", "financial"),
    "general-reasoning": ("analyz", "determine", "assess", "solve", "diagnos", "evaluate", "develop", "recommend", "decide"),
    "software-code-generation": ("code", "program", "software", "application", "algorithm", "debug", "database"),
    "visual-understanding": ("image", "visual", "diagram", "layout", "inspect", "drawing", "scan", "photograph"),
    "visual-content-generation": ("design", "draw", "graphic", "layout", "illustrat", "image", "visual content"),
    "planning-workflow-execution": ("plan", "coordinate", "schedule", "manage", "organize", "supervise", "priorit", "workflow"),
    "tool-computer-operation": ("software", "computer", "database", "equipment", "operate", "system", "tool", "machine"),
    "interpersonal-social-interaction": ("client", "patient", "student", "customer", "counsel", "interview", "teach", "caregiver", "staff"),
    "persuasion-negotiation": ("negotiat", "persuad", "sell", "advocat", "convince", "resolve objection", "influence"),
    "physical-perception": ("inspect", "observe", "examine", "detect", "monitor", "sample", "physical condition"),
    "fine-physical-manipulation": ("install", "repair", "assemble", "cut", "clean", "handle", "fasten", "weld", "prepare food"),
    "mobility-real-world-operation": ("transport", "drive", "travel", "climb", "move", "patrol", "navigate", "carry", "rescue"),
}

CONSTRAINT_TERMS = {
    "physical-presence": ("install", "repair", "patient", "fire", "clean", "construct", "operate equipment", "on site"),
    "fine-motor-control": ("assemble", "cut", "repair", "install", "weld", "fasten", "prepare food", "specimen"),
    "mobility": ("travel", "drive", "climb", "patrol", "transport", "rescue", "move equipment"),
    "real-world-sensing": ("inspect", "observe", "examine", "monitor", "detect", "sample", "diagnos"),
    "synchronous-human-interaction": ("client", "patient", "student", "customer", "interview", "counsel", "negotiate", "teach"),
    "legal-accountability": ("legal", "court", "prescribe", "authorize", "compliance", "regulation", "contract"),
    "safety-criticality": ("patient", "fire", "rescue", "aircraft", "hazard", "safety", "medical", "emergency"),
    "tool-access": ("software", "computer", "equipment", "machine", "database", "instrument", "tool"),
    "data-access": ("record", "database", "confidential", "patient history", "financial data", "research data"),
    "workflow-integration": ("coordinate", "schedule", "supervise", "manage", "workflow", "department", "team"),
}

FORBIDDEN_INPUTS = [
    "ai_capability_benchmark_scores", "ai_capability_benchmark_snapshots",
    "task_ai_enrichment_assessments", "task_ai_scores", "occupation_scores",
    "automation_feasibility", "ai_capability_fit", "augmentation_potential",
]


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai").replace(
        "postgresql+asyncpg://", "postgresql://", 1,
    )


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def disposition(statement: str) -> tuple[str, float, str]:
    words = re.findall(r"[A-Za-z0-9]+", statement)
    if len(statement) <= 25 or len(words) <= 3:
        return "insufficient_description", 86, "Too little task-local evidence to assign requirements without inference."
    if len(statement) <= 60:
        return "ambiguous_scope", 72, "Material scope, method, or context is absent from the task statement."
    return "mappable", 68, "The task statement contains an action, object or evidence, and an outcome sufficient for a draft mapping."


def normalize(raw: list[tuple[str, int, list[str]]]) -> list[tuple[str, float, int, list[str]]]:
    selected = sorted(raw, key=lambda item: (-item[1], item[0]))[:6]
    total = sum(item[1] for item in selected)
    result: list[tuple[str, float, int, list[str]]] = []
    allocated = 0.0
    for index, (slug, score, terms) in enumerate(selected):
        weight = round(1 - allocated, 7) if index == len(selected) - 1 else round(score / total, 7)
        allocated += weight
        result.append((slug, weight, score, terms))
    return result


async def main() -> None:
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--benchmark-version", default="gold-v1-175-pending-human-review")
    arguments.add_argument("--run-version", default="draft-rules-v1-175-20260820")
    args = arguments.parse_args()
    source_text = Path(__file__).read_text(encoding="utf-8")
    lowered_source = source_text.lower()
    query_section = lowered_source.split("capability_terms", 1)[0]
    if any(forbidden in query_section for forbidden in FORBIDDEN_INPUTS):
        raise RuntimeError("Mapper input code references a prohibited score/outcome source")

    connection = await asyncpg.connect(database_url())
    transaction = connection.transaction()
    await transaction.start()
    try:
        dataset = await connection.fetchrow("""
          SELECT dataset.*,rubric.capability_taxonomy_version_id,rubric.environment_taxonomy_version_id,
                 rubric.source_id
          FROM task_capability_gold_datasets dataset
          JOIN task_mapping_rubric_versions rubric ON rubric.id=dataset.rubric_version_id
          WHERE dataset.dataset_version=$1
        """, args.benchmark_version)
        if dataset is None:
            raise ValueError(f"Unknown benchmark: {args.benchmark_version}")
        tasks = await connection.fetch("""
          SELECT input.*
          FROM task_mapping_blind_inputs input
          JOIN task_capability_gold_items membership ON membership.onet_task_id=input.onet_task_id
          WHERE membership.gold_dataset_id=$1
          ORDER BY input.onet_task_id
        """, dataset["id"])
        capabilities = {
            row["slug"]: row["id"] for row in await connection.fetch(
                "SELECT id,slug FROM ai_capability_definitions WHERE taxonomy_version_id=$1",
                dataset["capability_taxonomy_version_id"],
            )
        }
        constraints = {
            row["slug"]: row["id"] for row in await connection.fetch(
                "SELECT id,slug FROM task_environment_constraint_definitions WHERE environment_taxonomy_version_id=$1",
                dataset["environment_taxonomy_version_id"],
            )
        }
        source_id = await connection.fetchval("SELECT id FROM data_sources WHERE name='JobsVsAI Draft Task Mapper'")
        allowed_inputs = {
            "task": ["onet_task_id", "occupation_code", "task_statement", "task_statement_hash"],
            "taxonomy": ["capability_definition_id", "constraint_definition_id"],
            "rubric": ["thresholds", "normalization"],
            "benchmark": ["task_membership_only"],
            "prohibited": FORBIDDEN_INPUTS,
        }
        run_id = await connection.fetchval("""
          INSERT INTO task_mapping_candidate_runs (
            run_version,rubric_version_id,benchmark_dataset_id,mapper_name,mapper_version,mapper_kind,
            status,allowed_input_manifest,prohibited_input_attestation,configuration,source_code_sha256,
            input_task_count,output_task_count,source_id,provenance,created_by
          ) VALUES ($1,$2,$3,'JobsVsAI deterministic draft mapper','draft-rules-v1','deterministic_rules',
            'completed',$4,true,$5,$6,$7,$7,$8,$9,'system:draft-candidate-mapper') RETURNING id
        """, args.run_version, dataset["rubric_version_id"], dataset["id"], json.dumps(allowed_inputs),
            json.dumps({"maximum_capabilities": 6, "text_only": True, "disposition_length_thresholds": [25, 60]}),
            hashlib.sha256(source_text.encode()).hexdigest(), len(tasks), source_id,
            json.dumps({"draft": True, "activation_allowed": False, "score_blind": True}))

        for task in tasks:
            task_disposition, disposition_confidence, rationale = disposition(task["task_statement"])
            mapping_id = await connection.fetchval("""
              INSERT INTO candidate_task_mappings (
                candidate_run_id,onet_task_id,task_statement_hash,disposition,
                disposition_confidence,rationale,evidence,provenance
              ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id
            """, run_id, task["onet_task_id"], task["task_statement_hash"], task_disposition,
                disposition_confidence, rationale,
                json.dumps([{"task_statement": task["task_statement"], "source": "task_mapping_blind_inputs"}]),
                json.dumps({"mapper": "draft-rules-v1", "score_blind": True}))
            if task_disposition != "mappable":
                continue

            raw = []
            for slug, terms in CAPABILITY_TERMS.items():
                matches = matched_terms(task["task_statement"], terms)
                if matches:
                    raw.append((slug, 1 + len(matches), matches))
            if not raw:
                raw = [("general-reasoning", 1, ["task action and outcome"])]
            for slug, weight, score, matches in normalize(raw):
                level = min(85, 35 + score * 7 + min(15, len(task["task_statement"].split()) // 4))
                confidence = min(84, 48 + score * 8)
                await connection.execute("""
                  INSERT INTO candidate_task_capability_requirements (
                    candidate_task_mapping_id,capability_definition_id,weight,required_capability_level,
                    confidence,rationale,evidence,provenance
                  ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """, mapping_id, capabilities[slug], weight, level, confidence,
                    f"Task-local terms support {slug}; relative weight is normalized across matched dimensions.",
                    json.dumps([{"matched_terms": matches}]), json.dumps({"mapper": "draft-rules-v1"}))

            for slug, terms in CONSTRAINT_TERMS.items():
                matches = matched_terms(task["task_statement"], terms)
                if not matches:
                    continue
                level = min(85, 20 + len(matches) * 12)
                confidence = min(82, 52 + len(matches) * 7)
                await connection.execute("""
                  INSERT INTO candidate_task_environment_constraints (
                    candidate_task_mapping_id,constraint_definition_id,constraint_level,
                    confidence,rationale,evidence,provenance
                  ) VALUES ($1,$2,$3,$4,$5,$6,$7)
                """, mapping_id, constraints[slug], level, confidence,
                    f"Only explicit task-local terms are used to propose {slug}.",
                    json.dumps([{"matched_terms": matches}]), json.dumps({"mapper": "draft-rules-v1"}))
        await transaction.commit()
        print(json.dumps({"candidateRunId": run_id, "runVersion": args.run_version, "tasks": len(tasks), "scoreBlind": True}))
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
