from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

import asyncpg


IMPORTER_VERSION = "onet-v3-promotion-lifecycle"
BASE_SOURCE_URL = "https://www.onetcenter.org/dl_files/database"
DEFAULT_VERSION = "30.3"
CROSSWALK_FILE = "2010_to_2019_crosswalk.csv"
CROSSWALK_URL = "https://www.onetcenter.org/taxonomy/2019/walk/2010_to_2019_Crosswalk.csv?fmt=csv"
SOC_2018_URL = "https://www.bls.gov/soc/2018/major_groups.htm"
TASK_RATING_POLICY_VERSION = "onet-task-rating-v1"
IDENTITY_POLICY_VERSION = "occupation-identity-v1"
LIFECYCLE_POLICY_VERSION = "occupation-lifecycle-v1"
SCORING_READINESS_POLICY_VERSION = "source-coverage-v1"

DATASET_FILES = {
    "occupation_data": "occupation_data.csv",
    "job_titles": "job_titles.csv",
    "task_statements": "task_statements.csv",
    "task_ratings": "task_ratings.csv",
    "essential_skills": "essential_skills.csv",
    "transferable_skills": "transferable_skills.csv",
    "abilities": "abilities.csv",
    "work_activities": "work_activities.csv",
    "work_context": "work_context.csv",
    "work_context_categories": "work_context_categories.csv",
    "related_occupations": "related_occupations.csv",
    "content_model_reference": "content_model_reference.csv",
    "scales_reference": "scales_reference.csv",
}

SOC_2018_MAJOR_GROUPS = {
    "11": "Management Occupations",
    "13": "Business and Financial Operations Occupations",
    "15": "Computer and Mathematical Occupations",
    "17": "Architecture and Engineering Occupations",
    "19": "Life, Physical, and Social Science Occupations",
    "21": "Community and Social Service Occupations",
    "23": "Legal Occupations",
    "25": "Educational Instruction and Library Occupations",
    "27": "Arts, Design, Entertainment, Sports, and Media Occupations",
    "29": "Healthcare Practitioners and Technical Occupations",
    "31": "Healthcare Support Occupations",
    "33": "Protective Service Occupations",
    "35": "Food Preparation and Serving Related Occupations",
    "37": "Building and Grounds Cleaning and Maintenance Occupations",
    "39": "Personal Care and Service Occupations",
    "41": "Sales and Related Occupations",
    "43": "Office and Administrative Support Occupations",
    "45": "Farming, Fishing, and Forestry Occupations",
    "47": "Construction and Extraction Occupations",
    "49": "Installation, Maintenance, and Repair Occupations",
    "51": "Production Occupations",
    "53": "Transportation and Material Moving Occupations",
    "55": "Military Specific Occupations",
}

RATING_DATASETS = {
    "essential_skills": ("skill", "essential"),
    "transferable_skills": ("skill", "transferable"),
    "abilities": ("ability", "ability"),
    "work_activities": ("work_activity", "work_activity"),
    "work_context": ("work_context", "work_context"),
}

# These are bridge links only. The importer never writes O*NET tasks or ratings
# into production tables and never schedules score recalculation.
PRODUCT_OCCUPATION_LINKS = {
    "27-1024.00": "graphic-designer",
    "13-2011.00": "accountant",
    "15-1252.00": "software-developer",
    "15-1212.00": "cybersecurity-analyst",
    "13-2052.00": "financial-advisor",
    "29-1171.00": "nurse-practitioner",
    "49-3011.00": "aircraft-mechanic",
    "15-1255.00": "ux-researcher",
    "11-2021.00": "brand-strategist",
}


@dataclass(frozen=True)
class RawRecord:
    dataset: str
    natural_key: str
    source_uri: str
    row_hash: str
    payload: dict[str, str]
    source_key: str = "onet"
    dataset_version: str | None = None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _canonical_hash(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record(dataset: str, version: str, natural_key: str, payload: dict[str, str]) -> RawRecord:
    filename = DATASET_FILES[dataset]
    return RawRecord(
        dataset=dataset,
        natural_key=natural_key,
        source_uri=f"{BASE_SOURCE_URL}/db_{version.replace('.', '_')}_csv/{filename}",
        row_hash=_canonical_hash(payload),
        payload=payload,
        dataset_version=version,
    )


def _crosswalk_record(payload: dict[str, str]) -> RawRecord:
    return RawRecord(
        dataset="occupation_succession_2010_2019",
        natural_key=_natural_key("occupation_succession_2010_2019", payload),
        source_uri=CROSSWALK_URL,
        row_hash=_canonical_hash(payload),
        payload=payload,
        source_key="crosswalk",
        dataset_version="2010-to-2019",
    )


def _soc_group_record(code: str, title: str) -> RawRecord:
    payload = {"SOC 2018 Major Group": code, "Title": title}
    return RawRecord(
        dataset="soc_2018_major_groups",
        natural_key=code,
        source_uri=SOC_2018_URL,
        row_hash=_canonical_hash(payload),
        payload=payload,
        source_key="soc2018",
        dataset_version="2018",
    )


def _integer(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(Decimal(value))


def _decimal(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid numeric O*NET value: {value!r}") from error


def _boolean(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    return value.strip().upper() in {"Y", "YES", "TRUE", "1"}


def normalize_scale(value: Decimal | None, minimum: Decimal | None, maximum: Decimal | None) -> Decimal | None:
    if value is None or minimum is None or maximum is None or maximum == minimum:
        return None
    normalized = (value - minimum) / (maximum - minimum) * Decimal(100)
    return max(Decimal(0), min(Decimal(100), normalized)).quantize(Decimal("0.0001"))


def _natural_key(dataset: str, row: dict[str, str]) -> str:
    code = row.get("O*NET-SOC Code", "")
    if dataset == "occupation_data":
        return code
    if dataset == "job_titles":
        return "|".join((code, row["Job Title"], row.get("Short Title", "")))
    if dataset == "task_statements":
        return f"{code}|{row['Task ID']}"
    if dataset == "task_ratings":
        return "|".join((code, row["Task ID"], row["Scale ID"], row.get("Category", "") or "-1"))
    if dataset in RATING_DATASETS:
        return "|".join((code, row["Element ID"], row["Scale ID"], row.get("Category", "") or "-1"))
    if dataset == "work_context_categories":
        return "|".join((row["Element ID"], row["Scale ID"], row["Category"]))
    if dataset == "related_occupations":
        return "|".join((code, row["Related O*NET-SOC Code"], row["Relatedness Tier"], row["Index"]))
    if dataset == "content_model_reference":
        return row["Element ID"]
    if dataset == "scales_reference":
        return row["Scale ID"]
    if dataset == "occupation_succession_2010_2019":
        return "|".join((row["O*NET-SOC 2010 Code"], row["O*NET-SOC 2019 Code"]))
    if dataset == "soc_2018_major_groups":
        return row["SOC 2018 Major Group"]
    raise ValueError(f"No natural key for {dataset}")


def succession_mapping_type(
    row: dict[str, str], predecessor_counts: Counter[str], successor_counts: Counter[str],
) -> str:
    predecessor = row["O*NET-SOC 2010 Code"]
    successor = row["O*NET-SOC 2019 Code"]
    if predecessor_counts[predecessor] > 1 and successor_counts[successor] > 1:
        return "complex"
    if predecessor_counts[predecessor] > 1:
        return "split"
    if successor_counts[successor] > 1:
        return "merge"
    if predecessor != successor:
        return "recoded"
    if row["O*NET-SOC 2010 Title"] != row["O*NET-SOC 2019 Title"]:
        return "renamed"
    return "unchanged"


def _public_slug(title: str, occupation_code: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "occupation"
    return f"{base}-{occupation_code.lower().replace('.', '-')}"


def _title_review_reasons(title: str) -> list[str]:
    lowered = title.lower()
    reasons: list[str] = []
    if "all other" in lowered or "except " in lowered:
        reasons.append("source_title_is_taxonomic_or_exclusionary")
    if any(term in lowered for term in ("federal", "state government", "postal service", "legislator")):
        reasons.append("source_title_is_us_specific")
    if len(title) > 80 or "/" in title:
        reasons.append("source_title_needs_clarity_review")
    return reasons


def _dedupe(records: Iterable[RawRecord]) -> list[RawRecord]:
    unique: dict[tuple[str, str], RawRecord] = {}
    for record in records:
        key = (record.dataset, record.natural_key)
        existing = unique.get(key)
        if existing and existing.row_hash != record.row_hash:
            raise ValueError(f"Conflicting rows for {record.dataset}:{record.natural_key}")
        unique[key] = record
    return list(unique.values())


def load_subset(data_dir: Path, version: str, subset_codes: set[str]) -> tuple[dict[str, list[dict[str, str]]], list[RawRecord], dict[str, str]]:
    required_files = [*DATASET_FILES.values(), CROSSWALK_FILE]
    missing = [filename for filename in required_files if not (data_dir / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing O*NET source files: {', '.join(missing)}")

    rows: dict[str, list[dict[str, str]]] = {}
    rows["occupation_data"] = [row for row in _read_csv(data_dir / DATASET_FILES["occupation_data"]) if row["O*NET-SOC Code"] in subset_codes]
    found_codes = {row["O*NET-SOC Code"] for row in rows["occupation_data"]}
    if found_codes != subset_codes:
        raise ValueError(f"Subset codes not found in O*NET {version}: {sorted(subset_codes - found_codes)}")

    for dataset in (
        "job_titles", "task_statements", "task_ratings", "essential_skills", "transferable_skills",
        "abilities", "work_activities", "work_context", "related_occupations",
    ):
        rows[dataset] = [row for row in _read_csv(data_dir / DATASET_FILES[dataset]) if row["O*NET-SOC Code"] in subset_codes]

    element_ids = {
        row["Element ID"]
        for dataset in RATING_DATASETS
        for row in rows[dataset]
    }
    rows["content_model_reference"] = [
        row for row in _read_csv(data_dir / DATASET_FILES["content_model_reference"])
        if row["Element ID"] in element_ids
    ]
    content_ids = {row["Element ID"] for row in rows["content_model_reference"]}
    if content_ids != element_ids:
        raise ValueError(f"Content Model definitions missing for: {sorted(element_ids - content_ids)}")

    work_context_ids = {row["Element ID"] for row in rows["work_context"]}
    rows["work_context_categories"] = [
        row for row in _read_csv(data_dir / DATASET_FILES["work_context_categories"])
        if row["Element ID"] in work_context_ids
    ]
    rows["scales_reference"] = _read_csv(data_dir / DATASET_FILES["scales_reference"])

    full_crosswalk = _read_csv(data_dir / CROSSWALK_FILE)
    rows["occupation_succession_2010_2019"] = [
        row for row in full_crosswalk if row["O*NET-SOC 2019 Code"] in subset_codes
    ]
    rows["succession_predecessor_counts"] = [dict(Counter(
        row["O*NET-SOC 2010 Code"] for row in full_crosswalk
    ))]
    rows["succession_successor_counts"] = [dict(Counter(
        row["O*NET-SOC 2019 Code"] for row in full_crosswalk
    ))]
    major_groups = sorted({code[:2] for code in subset_codes})
    rows["soc_2018_major_groups"] = [
        {"SOC 2018 Major Group": code, "Title": SOC_2018_MAJOR_GROUPS[code]}
        for code in major_groups
    ]

    onet_records = _dedupe(
        _record(dataset, version, _natural_key(dataset, row), row)
        for dataset, dataset_rows in rows.items()
        if dataset in DATASET_FILES
        for row in dataset_rows
    )
    raw_records = [
        *onet_records,
        *(_crosswalk_record(row) for row in rows["occupation_succession_2010_2019"]),
        *(_soc_group_record(row["SOC 2018 Major Group"], row["Title"]) for row in rows["soc_2018_major_groups"]),
    ]
    file_hashes = {
        filename: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest()
        for filename in required_files
    }
    return rows, raw_records, file_hashes


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://jobsvsai:change-me@localhost:5432/jobsvsai")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _score_fingerprint(connection: asyncpg.Connection) -> dict[str, Any]:
    row = await connection.fetchrow("""
      SELECT
        (SELECT count(*) FROM occupation_scores) score_count,
        (SELECT md5(coalesce(string_agg(
          concat_ws('|', id, occupation_id, model_version_id, ai_exposure, replacement_risk, calculated_at),
          ',' ORDER BY id), '')) FROM occupation_scores) score_hash,
        (SELECT count(*) FROM scoring_jobs) scoring_job_count,
        (SELECT count(*) FROM task_ai_scores) task_ai_score_count,
        (SELECT count(*) FROM ai_capabilities) ai_capability_count,
        (SELECT count(*) FROM occupation_categories) editorial_category_count,
        (SELECT md5(coalesce(string_agg(concat_ws('|', id, slug, name), ',' ORDER BY id), ''))
          FROM occupation_categories) editorial_category_hash,
        (SELECT count(*) FROM occupations) production_occupation_count,
        (SELECT md5(coalesce(string_agg(
          concat_ws('|', id, slug, title, category_id, is_active, search_aliases), ',' ORDER BY id), ''))
          FROM occupations) production_occupation_hash,
        (SELECT count(*) FROM career_relationships) career_relationship_count
    """)
    return dict(row)


async def _stage_source_versions(
    connection: asyncpg.Connection,
    source_id: int,
    run_id: int,
    version: str,
    records: list[RawRecord],
) -> tuple[dict[tuple[str, str], int], int]:
    await connection.execute("DROP TABLE IF EXISTS onet_source_stage")
    await connection.execute("""
      CREATE TEMP TABLE onet_source_stage (
        dataset_name TEXT NOT NULL,
        natural_key TEXT NOT NULL,
        dataset_version TEXT NOT NULL,
        source_uri TEXT NOT NULL,
        row_hash CHAR(64) NOT NULL,
        payload JSONB NOT NULL
      ) ON COMMIT DROP
    """)
    await connection.copy_records_to_table(
        "onet_source_stage",
        records=((
            r.dataset, r.natural_key, r.dataset_version or version,
            r.source_uri, r.row_hash, json.dumps(r.payload),
        ) for r in records),
        columns=("dataset_name", "natural_key", "dataset_version", "source_uri", "row_hash", "payload"),
    )
    new_count = int(await connection.fetchval("""
      SELECT count(*) FROM onet_source_stage stage
      LEFT JOIN source_record_versions existing
        ON existing.source_id=$1 AND existing.dataset_name=stage.dataset_name
       AND existing.natural_key=stage.natural_key AND existing.row_hash=stage.row_hash
      WHERE existing.id IS NULL
    """, source_id))
    await connection.execute("""
      UPDATE source_record_versions existing
      SET is_current=false, superseded_at=now()
      FROM onet_source_stage stage
      WHERE existing.source_id=$1 AND existing.dataset_name=stage.dataset_name
        AND existing.natural_key=stage.natural_key AND existing.is_current
        AND existing.row_hash<>stage.row_hash
    """, source_id)
    await connection.execute("""
      UPDATE source_record_versions existing
      SET is_current=true, superseded_at=NULL, last_seen_run_id=$2, last_seen_at=now(),
          source_version=$3, dataset_version=stage.dataset_version
      FROM onet_source_stage stage
      WHERE existing.source_id=$1 AND existing.dataset_name=stage.dataset_name
        AND existing.natural_key=stage.natural_key AND existing.row_hash=stage.row_hash
    """, source_id, run_id, version)
    await connection.execute("""
      INSERT INTO source_record_versions (
        source_id, first_seen_run_id, last_seen_run_id, dataset_name, natural_key,
        source_version, dataset_version, source_uri, row_hash, payload
      )
      SELECT $1, $2, $2, stage.dataset_name, stage.natural_key, $3, stage.dataset_version,
             stage.source_uri, stage.row_hash, stage.payload
      FROM onet_source_stage stage
      ON CONFLICT (source_id, dataset_name, natural_key, row_hash) DO NOTHING
    """, source_id, run_id, version)
    reference_rows = await connection.fetch("""
      SELECT stage.dataset_name, stage.natural_key, version.id
      FROM onet_source_stage stage
      JOIN source_record_versions version
        ON version.source_id=$1 AND version.dataset_name=stage.dataset_name
       AND version.natural_key=stage.natural_key AND version.row_hash=stage.row_hash
    """, source_id)
    return {(row["dataset_name"], row["natural_key"]): row["id"] for row in reference_rows}, new_count


def _ref(source_records: dict[tuple[str, str], int], dataset: str, row: dict[str, str]) -> int:
    return source_records[(dataset, _natural_key(dataset, row))]


async def _deactivate_scope(connection: asyncpg.Connection, codes: list[str], context_ids: list[str]) -> None:
    for table in (
        "onet_alternate_titles", "onet_tasks", "onet_task_ratings",
        "onet_element_ratings", "onet_related_occupations",
    ):
        await connection.execute(f"UPDATE {table} SET is_current=false WHERE occupation_code=ANY($1::text[])", codes)
    if context_ids:
        await connection.execute(
            "UPDATE onet_work_context_categories SET is_current=false WHERE element_id=ANY($1::text[])", context_ids,
        )


async def _upsert_canonical(
    connection: asyncpg.Connection,
    rows: dict[str, list[dict[str, str]]],
    source_records: dict[tuple[str, str], int],
    source_id: int,
    run_id: int,
    version: str,
    subset_name: str,
) -> None:
    codes = [row["O*NET-SOC Code"] for row in rows["occupation_data"]]
    product_rows = await connection.fetch("SELECT id, slug FROM occupations WHERE slug=ANY($1::text[])", list(PRODUCT_OCCUPATION_LINKS.values()))
    product_ids = {row["slug"]: row["id"] for row in product_rows}
    context_ids = sorted({row["Element ID"] for row in rows["work_context"]})
    await _deactivate_scope(connection, codes, context_ids)

    await connection.executemany("""
      INSERT INTO onet_occupations (
        onet_soc_code, title, description, jobs_vs_ai_occupation_id, source_id,
        import_run_id, source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
      ON CONFLICT (onet_soc_code) DO UPDATE SET
        title=EXCLUDED.title, description=EXCLUDED.description,
        jobs_vs_ai_occupation_id=COALESCE(EXCLUDED.jobs_vs_ai_occupation_id, onet_occupations.jobs_vs_ai_occupation_id),
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata,
        is_current=true, updated_at=now()
    """, [
        (
            row["O*NET-SOC Code"], row["Title"], row["Description"],
            product_ids.get(PRODUCT_OCCUPATION_LINKS.get(row["O*NET-SOC Code"], "")),
            source_id, run_id, _ref(source_records, "occupation_data", row), version,
            _canonical_hash(row), json.dumps({"scope": subset_name, "promotion": "staged_only"}),
        )
        for row in rows["occupation_data"]
    ])

    await connection.executemany("""
      INSERT INTO onet_alternate_titles (
        occupation_code, job_title, short_title, title_sources, source_id, import_run_id,
        source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
      ON CONFLICT (occupation_code, job_title, short_title) DO UPDATE SET
        title_sources=EXCLUDED.title_sources, source_id=EXCLUDED.source_id,
        import_run_id=EXCLUDED.import_run_id, source_record_id=EXCLUDED.source_record_id,
        source_version=EXCLUDED.source_version, row_hash=EXCLUDED.row_hash,
        source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            row["O*NET-SOC Code"], row["Job Title"], row.get("Short Title", ""), row.get("Source(s)", ""),
            source_id, run_id, _ref(source_records, "job_titles", row), version,
            _canonical_hash(row), json.dumps({"dataset": "job_titles"}),
        )
        for row in rows["job_titles"]
    ])

    await connection.executemany("""
      INSERT INTO onet_tasks (
        task_id, occupation_code, statement, task_type, incumbents_responding, observed_date,
        domain_source, source_id, import_run_id, source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb)
      ON CONFLICT (task_id) DO UPDATE SET
        occupation_code=EXCLUDED.occupation_code, statement=EXCLUDED.statement,
        task_type=EXCLUDED.task_type, incumbents_responding=EXCLUDED.incumbents_responding,
        observed_date=EXCLUDED.observed_date, domain_source=EXCLUDED.domain_source,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            int(row["Task ID"]), row["O*NET-SOC Code"], row["Task"], row.get("Task Type") or None,
            _integer(row.get("Incumbents Responding")), row.get("Date") or None, row.get("Domain Source") or None,
            source_id, run_id, _ref(source_records, "task_statements", row), version,
            _canonical_hash(row), json.dumps({"dataset": "task_statements"}),
        )
        for row in rows["task_statements"]
    ])

    scale_rows = {row["Scale ID"]: row for row in rows["scales_reference"]}
    scales = {
        key: (_decimal(row.get("Minimum")), _decimal(row.get("Maximum")))
        for key, row in scale_rows.items()
    }
    await connection.executemany("""
      INSERT INTO onet_scales (
        scale_id, scale_name, minimum, maximum, source_id, import_run_id,
        source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
      ON CONFLICT (scale_id) DO UPDATE SET
        scale_name=EXCLUDED.scale_name, minimum=EXCLUDED.minimum, maximum=EXCLUDED.maximum,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            row["Scale ID"], row["Scale Name"], _decimal(row.get("Minimum")), _decimal(row.get("Maximum")),
            source_id, run_id, _ref(source_records, "scales_reference", row), version,
            _canonical_hash(row), json.dumps({"dataset": "scales_reference"}),
        )
        for row in rows["scales_reference"]
    ])
    await connection.executemany("""
      INSERT INTO onet_task_ratings (
        occupation_code, task_id, scale_id, scale_name, category, data_value, normalized_value,
        sample_size, standard_error, lower_ci, upper_ci, recommend_suppress, observed_date,
        domain_source, source_id, import_run_id, source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20::jsonb)
      ON CONFLICT (occupation_code, task_id, scale_id, category) DO UPDATE SET
        scale_name=EXCLUDED.scale_name, data_value=EXCLUDED.data_value,
        normalized_value=EXCLUDED.normalized_value, sample_size=EXCLUDED.sample_size,
        standard_error=EXCLUDED.standard_error, lower_ci=EXCLUDED.lower_ci, upper_ci=EXCLUDED.upper_ci,
        recommend_suppress=EXCLUDED.recommend_suppress, observed_date=EXCLUDED.observed_date,
        domain_source=EXCLUDED.domain_source, source_id=EXCLUDED.source_id,
        import_run_id=EXCLUDED.import_run_id, source_record_id=EXCLUDED.source_record_id,
        source_version=EXCLUDED.source_version, row_hash=EXCLUDED.row_hash,
        source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            row["O*NET-SOC Code"], int(row["Task ID"]), row["Scale ID"], row["Scale Name"],
            _integer(row.get("Category")) or -1, _decimal(row.get("Data Value")),
            normalize_scale(_decimal(row.get("Data Value")), *scales.get(row["Scale ID"], (None, None))),
            _integer(row.get("N")), _decimal(row.get("Standard Error")), _decimal(row.get("Lower CI Bound")),
            _decimal(row.get("Upper CI Bound")), bool(_boolean(row.get("Recommend Suppress"))),
            row.get("Date") or None, row.get("Domain Source") or None, source_id, run_id,
            _ref(source_records, "task_ratings", row), version, _canonical_hash(row),
            json.dumps({"dataset": "task_ratings"}),
        )
        for row in rows["task_ratings"]
    ])

    content_rows = {row["Element ID"]: row for row in rows["content_model_reference"]}
    element_types: dict[tuple[str, str], dict[str, str]] = {}
    element_sources: dict[tuple[str, str], set[str]] = {}
    for dataset, (element_type, _) in RATING_DATASETS.items():
        for row in rows[dataset]:
            key = (element_type, row["Element ID"])
            element_types[key] = content_rows[row["Element ID"]]
            element_sources.setdefault(key, set()).add(dataset)
    await connection.executemany("""
      INSERT INTO onet_elements (
        element_type, element_id, element_name, description, source_id, import_run_id,
        source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
      ON CONFLICT (element_type, element_id) DO UPDATE SET
        element_name=EXCLUDED.element_name, description=EXCLUDED.description,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            element_type, element_id, content["Element Name"], content.get("Description", ""),
            source_id, run_id, _ref(source_records, "content_model_reference", content), version,
            _canonical_hash(content), json.dumps({"rating_datasets": sorted(element_sources[(element_type, element_id)])}),
        )
        for (element_type, element_id), content in element_types.items()
    ])

    element_rating_values: list[tuple[Any, ...]] = []
    for dataset, (element_type, element_group) in RATING_DATASETS.items():
        for row in rows[dataset]:
            data_value = _decimal(row.get("Data Value"))
            element_rating_values.append((
                row["O*NET-SOC Code"], element_type, row["Element ID"], row["Scale ID"], row["Scale Name"],
                _integer(row.get("Category")) or -1, data_value,
                normalize_scale(data_value, *scales.get(row["Scale ID"], (None, None))),
                _integer(row.get("N")), _decimal(row.get("Standard Error")), _decimal(row.get("Lower CI Bound")),
                _decimal(row.get("Upper CI Bound")), bool(_boolean(row.get("Recommend Suppress"))),
                _boolean(row.get("Not Relevant")), row.get("Date") or None, row.get("Domain Source") or None,
                source_id, run_id, _ref(source_records, dataset, row), version, _canonical_hash(row),
                element_group if element_type == "skill" else None,
                json.dumps({"dataset": dataset, "element_group": element_group}),
            ))
    await connection.executemany("""
      INSERT INTO onet_element_ratings (
        occupation_code, element_type, element_id, scale_id, scale_name, category,
        data_value, normalized_value, sample_size, standard_error, lower_ci, upper_ci,
        recommend_suppress, not_relevant, observed_date, domain_source, source_id,
        import_run_id, source_record_id, source_version, row_hash, skill_classification, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23::jsonb)
      ON CONFLICT (occupation_code, element_type, element_id, scale_id, category) DO UPDATE SET
        scale_name=EXCLUDED.scale_name, data_value=EXCLUDED.data_value,
        normalized_value=EXCLUDED.normalized_value, sample_size=EXCLUDED.sample_size,
        standard_error=EXCLUDED.standard_error, lower_ci=EXCLUDED.lower_ci, upper_ci=EXCLUDED.upper_ci,
        recommend_suppress=EXCLUDED.recommend_suppress, not_relevant=EXCLUDED.not_relevant,
        observed_date=EXCLUDED.observed_date, domain_source=EXCLUDED.domain_source,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, skill_classification=EXCLUDED.skill_classification,
        source_metadata=EXCLUDED.source_metadata, is_current=true
    """, element_rating_values)

    await connection.executemany("""
      INSERT INTO onet_work_context_categories (
        element_id, scale_id, category, element_name, scale_name, category_description,
        source_id, import_run_id, source_record_id, source_version, row_hash
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
      ON CONFLICT (element_id, scale_id, category) DO UPDATE SET
        element_name=EXCLUDED.element_name, scale_name=EXCLUDED.scale_name,
        category_description=EXCLUDED.category_description, source_id=EXCLUDED.source_id,
        import_run_id=EXCLUDED.import_run_id, source_record_id=EXCLUDED.source_record_id,
        source_version=EXCLUDED.source_version, row_hash=EXCLUDED.row_hash, is_current=true
    """, [
        (
            row["Element ID"], row["Scale ID"], int(row["Category"]), row["Element Name"],
            row["Scale Name"], row["Category Description"], source_id, run_id,
            _ref(source_records, "work_context_categories", row), version, _canonical_hash(row),
        )
        for row in rows["work_context_categories"]
    ])

    await connection.executemany("""
      INSERT INTO onet_related_occupations (
        occupation_code, related_occupation_code, related_title, relatedness_tier,
        relatedness_rank, source_id, import_run_id, source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
      ON CONFLICT (occupation_code, related_occupation_code, relatedness_tier, relatedness_rank) DO UPDATE SET
        related_title=EXCLUDED.related_title, source_id=EXCLUDED.source_id,
        import_run_id=EXCLUDED.import_run_id, source_record_id=EXCLUDED.source_record_id,
        source_version=EXCLUDED.source_version, row_hash=EXCLUDED.row_hash,
        source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            row["O*NET-SOC Code"], row["Related O*NET-SOC Code"], row["Related Title"],
            row["Relatedness Tier"], int(row["Index"]), source_id, run_id,
            _ref(source_records, "related_occupations", row), version, _canonical_hash(row),
            json.dumps({"target_in_subset": row["Related O*NET-SOC Code"] in set(codes)}),
        )
        for row in rows["related_occupations"]
    ])

    await connection.execute("""
      UPDATE onet_tasks SET importance_score=NULL, frequency_score=NULL
      WHERE occupation_code=ANY($1::text[])
    """, codes)
    await connection.execute("""
      UPDATE onet_tasks task SET importance_score=rating.normalized_value
      FROM onet_task_ratings rating
      WHERE rating.task_id=task.task_id AND rating.scale_id='IM' AND rating.category=-1 AND rating.is_current
        AND task.occupation_code=ANY($1::text[])
    """, codes)
    await connection.execute("""
      WITH frequency AS (
        SELECT task_id,
          round(greatest(0, least(100,
            ((sum(category * data_value) / nullif(sum(data_value), 0)) - 1) / 6 * 100
          )), 4) frequency_score
        FROM onet_task_ratings
        WHERE scale_id='FT' AND category BETWEEN 1 AND 7 AND is_current
        GROUP BY task_id
      )
      UPDATE onet_tasks task SET frequency_score=frequency.frequency_score
      FROM frequency
      WHERE frequency.task_id=task.task_id AND task.occupation_code=ANY($1::text[])
    """, codes)
    await connection.execute("""
      UPDATE onet_tasks
      SET rating_status = CASE
            WHEN importance_score IS NULL AND frequency_score IS NULL THEN 'missing_both'
            WHEN importance_score IS NULL THEN 'missing_importance'
            WHEN frequency_score IS NULL THEN 'missing_frequency'
            ELSE 'complete'
          END,
          weighting_eligible = importance_score IS NOT NULL AND frequency_score IS NOT NULL,
          rating_policy_version = $2,
          missing_rating_fields = ARRAY_REMOVE(ARRAY[
            CASE WHEN importance_score IS NULL THEN 'importance' END,
            CASE WHEN frequency_score IS NULL THEN 'frequency' END
          ], NULL)
      WHERE occupation_code=ANY($1::text[])
    """, codes, TASK_RATING_POLICY_VERSION)


async def _upsert_source_models(
    connection: asyncpg.Connection,
    rows: dict[str, list[dict[str, str]]],
    source_records: dict[tuple[str, str], int],
    source_ids: dict[str, int],
    run_id: int,
    version: str,
) -> None:
    occupation_rows = rows["occupation_data"]
    crosswalk_rows = rows["occupation_succession_2010_2019"]
    group_rows = rows["soc_2018_major_groups"]
    codes = [row["O*NET-SOC Code"] for row in occupation_rows]
    predecessor_counts = Counter(rows["succession_predecessor_counts"][0])
    successor_counts = Counter(rows["succession_successor_counts"][0])

    taxonomy_specs = {
        "onet2019": (
            "ONET_SOC", "O*NET-SOC 2019", "occupation", "2019", source_ids["onet"],
            "https://www.onetcenter.org/taxonomy.html", occupation_rows[0], "occupation_data", version,
        ),
        "onet2010": (
            "ONET_SOC", "O*NET-SOC 2010", "occupation", "2010", source_ids["crosswalk"],
            CROSSWALK_URL, crosswalk_rows[0], "occupation_succession_2010_2019", "2010-to-2019",
        ),
        "soc2018": (
            "SOC", "Standard Occupational Classification 2018", "category", "2018", source_ids["soc2018"],
            SOC_2018_URL, group_rows[0], "soc_2018_major_groups", "2018",
        ),
    }
    taxonomy_ids: dict[str, int] = {}
    for key, spec in taxonomy_specs.items():
        code, name, kind, taxonomy_version, source_id, source_uri, source_row, dataset, source_version = spec
        taxonomy_ids[key] = int(await connection.fetchval("""
          INSERT INTO source_taxonomies (
            taxonomy_code, name, taxonomy_kind, taxonomy_version, source_id, source_uri,
            import_run_id, source_record_id, source_version, row_hash, source_metadata
          ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
          ON CONFLICT (taxonomy_code, taxonomy_version) DO UPDATE SET
            name=EXCLUDED.name, taxonomy_kind=EXCLUDED.taxonomy_kind, source_id=EXCLUDED.source_id,
            source_uri=EXCLUDED.source_uri, import_run_id=EXCLUDED.import_run_id,
            source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
            row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
          RETURNING id
        """, code, name, kind, taxonomy_version, source_id, source_uri, run_id,
             _ref(source_records, dataset, source_row), source_version, _canonical_hash(source_row),
             json.dumps({"scope": "representative_subset", "editorial": False})))

    await connection.execute(
        "UPDATE source_occupation_titles SET is_current=false WHERE taxonomy_id=$1 AND occupation_code=ANY($2::text[])",
        taxonomy_ids["onet2019"], codes,
    )
    title_values: list[tuple[Any, ...]] = []
    for row in occupation_rows:
        title_values.append((
            taxonomy_ids["onet2019"], row["O*NET-SOC Code"], row["Title"], "preferred", "en", "Title",
            source_ids["onet"], run_id, _ref(source_records, "occupation_data", row), version,
            _canonical_hash(row), json.dumps({"dataset": "occupation_data"}),
        ))
    for row in rows["job_titles"]:
        common = (
            taxonomy_ids["onet2019"], row["O*NET-SOC Code"], "en", source_ids["onet"], run_id,
            _ref(source_records, "job_titles", row), version, _canonical_hash(row),
        )
        title_values.append((common[0], common[1], row["Job Title"], "alternate", common[2], "Job Title",
                             common[3], common[4], common[5], common[6], common[7],
                             json.dumps({"dataset": "job_titles", "source_codes": row.get("Source(s)", "")})))
        if row.get("Short Title", "").strip():
            title_values.append((common[0], common[1], row["Short Title"], "short", common[2], "Short Title",
                                 common[3], common[4], common[5], common[6], common[7],
                                 json.dumps({"dataset": "job_titles", "source_codes": row.get("Source(s)", "")})))
    for row in crosswalk_rows:
        if row["O*NET-SOC 2010 Title"] == row["O*NET-SOC 2019 Title"]:
            continue
        title_values.append((
            taxonomy_ids["onet2010"], row["O*NET-SOC 2010 Code"], row["O*NET-SOC 2010 Title"],
            "historical", "en", "O*NET-SOC 2010 Title", source_ids["crosswalk"], run_id,
            _ref(source_records, "occupation_succession_2010_2019", row), "2010-to-2019",
            _canonical_hash(row), json.dumps({
                "dataset": "occupation_succession_2010_2019",
                "successor_code": row["O*NET-SOC 2019 Code"],
            }),
        ))
    await connection.executemany("""
      INSERT INTO source_occupation_titles (
        taxonomy_id, occupation_code, title, title_type, locale, source_title_type,
        source_id, import_run_id, source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb)
      ON CONFLICT (taxonomy_id, occupation_code, title, title_type, locale) DO UPDATE SET
        source_title_type=EXCLUDED.source_title_type, source_id=EXCLUDED.source_id,
        import_run_id=EXCLUDED.import_run_id, source_record_id=EXCLUDED.source_record_id,
        source_version=EXCLUDED.source_version, row_hash=EXCLUDED.row_hash,
        source_metadata=EXCLUDED.source_metadata, is_current=true
    """, title_values)

    node_values: list[tuple[Any, ...]] = []
    for row in occupation_rows:
        node_values.append((taxonomy_ids["onet2019"], row["O*NET-SOC Code"], None, "occupation", row["Title"], row["Description"], 1,
                            source_ids["onet"], run_id, _ref(source_records, "occupation_data", row), version,
                            _canonical_hash(row), json.dumps({"dataset": "occupation_data"})))
    seen_predecessors: set[str] = set()
    for row in crosswalk_rows:
        if row["O*NET-SOC 2010 Code"] in seen_predecessors:
            continue
        seen_predecessors.add(row["O*NET-SOC 2010 Code"])
        node_values.append((taxonomy_ids["onet2010"], row["O*NET-SOC 2010 Code"], None, "occupation", row["O*NET-SOC 2010 Title"], "", 1,
                            source_ids["crosswalk"], run_id, _ref(source_records, "occupation_succession_2010_2019", row), "2010-to-2019",
                            _canonical_hash(row), json.dumps({"dataset": "occupation_succession_2010_2019"})))
    for row in group_rows:
        node_values.append((taxonomy_ids["soc2018"], row["SOC 2018 Major Group"], None, "major_group", row["Title"], "", 1,
                            source_ids["soc2018"], run_id, _ref(source_records, "soc_2018_major_groups", row), "2018",
                            _canonical_hash(row), json.dumps({"dataset": "soc_2018_major_groups"})))
    await connection.executemany("""
      INSERT INTO source_taxonomy_nodes (
        taxonomy_id, external_code, parent_external_code, node_type, title, description,
        hierarchy_level, source_id, import_run_id, source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb)
      ON CONFLICT (taxonomy_id, external_code) DO UPDATE SET
        parent_external_code=EXCLUDED.parent_external_code, node_type=EXCLUDED.node_type,
        title=EXCLUDED.title, description=EXCLUDED.description, hierarchy_level=EXCLUDED.hierarchy_level,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
    """, node_values)

    await connection.execute(
        "UPDATE source_occupation_taxonomy_memberships SET is_current=false WHERE occupation_code=ANY($1::text[])", codes,
    )
    membership_values: list[tuple[Any, ...]] = []
    for row in occupation_rows:
        onet_node_id = int(await connection.fetchval(
            "SELECT id FROM source_taxonomy_nodes WHERE taxonomy_id=$1 AND external_code=$2",
            taxonomy_ids["onet2019"], row["O*NET-SOC Code"],
        ))
        soc_node_id = int(await connection.fetchval(
            "SELECT id FROM source_taxonomy_nodes WHERE taxonomy_id=$1 AND external_code=$2",
            taxonomy_ids["soc2018"], row["O*NET-SOC Code"][:2],
        ))
        for taxonomy_id, node_id, relation in (
            (taxonomy_ids["onet2019"], onet_node_id, "primary"),
            (taxonomy_ids["soc2018"], soc_node_id, "major_group"),
        ):
            membership_values.append((taxonomy_id, node_id, row["O*NET-SOC Code"], relation,
                                      source_ids["onet"], run_id, _ref(source_records, "occupation_data", row), version,
                                      _canonical_hash(row), json.dumps({"editorial_taxonomy": False})))
    await connection.executemany("""
      INSERT INTO source_occupation_taxonomy_memberships (
        taxonomy_id, node_id, occupation_code, relation_type, source_id, import_run_id,
        source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
      ON CONFLICT (taxonomy_id, node_id, occupation_code, relation_type) DO UPDATE SET
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
    """, membership_values)

    await connection.execute(
        "UPDATE source_occupation_successions SET is_current=false WHERE successor_code=ANY($1::text[])", codes,
    )
    await connection.executemany("""
      INSERT INTO source_occupation_successions (
        predecessor_taxonomy_id, predecessor_code, predecessor_title,
        successor_taxonomy_id, successor_code, successor_title, mapping_type,
        allocation_weight, effective_version, source_id, import_run_id,
        source_record_id, source_version, row_hash, source_metadata
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,NULL,$8,$9,$10,$11,$12,$13,$14::jsonb)
      ON CONFLICT (predecessor_taxonomy_id, predecessor_code, successor_taxonomy_id, successor_code) DO UPDATE SET
        predecessor_title=EXCLUDED.predecessor_title, successor_title=EXCLUDED.successor_title,
        mapping_type=EXCLUDED.mapping_type, allocation_weight=NULL, effective_version=EXCLUDED.effective_version,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, source_metadata=EXCLUDED.source_metadata, is_current=true
    """, [
        (
            taxonomy_ids["onet2010"], row["O*NET-SOC 2010 Code"], row["O*NET-SOC 2010 Title"],
            taxonomy_ids["onet2019"], row["O*NET-SOC 2019 Code"], row["O*NET-SOC 2019 Title"],
            succession_mapping_type(row, predecessor_counts, successor_counts), "2019", source_ids["crosswalk"],
            run_id, _ref(source_records, "occupation_succession_2010_2019", row), "2010-to-2019",
            _canonical_hash(row), json.dumps({"allocation_weight": "not_provided_by_source"}),
        )
        for row in crosswalk_rows
    ])

    await _refresh_domain_coverage(connection, codes, source_ids["onet"], run_id, version)
    await connection.execute("ALTER TABLE onet_task_ratings VALIDATE CONSTRAINT onet_task_ratings_scale_fk")
    await connection.execute("ALTER TABLE onet_element_ratings VALIDATE CONSTRAINT onet_element_ratings_scale_fk")


async def _refresh_domain_coverage(
    connection: asyncpg.Connection, codes: list[str], source_id: int, run_id: int, version: str,
) -> None:
    await connection.execute("DELETE FROM onet_occupation_domain_coverage WHERE occupation_code=ANY($1::text[])", codes)
    await connection.execute("""
      INSERT INTO onet_occupation_domain_coverage (
        occupation_code, domain, entity_count, rating_count, coverage_status,
        issues, source_id, import_run_id, source_version
      )
      SELECT occupation.onet_soc_code, domain.name,
        CASE domain.name
          WHEN 'titles' THEN (SELECT count(*) FROM source_occupation_titles title WHERE title.occupation_code=occupation.onet_soc_code AND title.is_current)
          WHEN 'tasks' THEN (SELECT count(*) FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current)
          WHEN 'task_ratings' THEN (SELECT count(*) FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current)
          WHEN 'skills' THEN (SELECT count(DISTINCT element_id) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='skill' AND rating.is_current)
          WHEN 'abilities' THEN (SELECT count(DISTINCT element_id) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='ability' AND rating.is_current)
          WHEN 'work_activities' THEN (SELECT count(DISTINCT element_id) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_activity' AND rating.is_current)
          WHEN 'work_context' THEN (SELECT count(DISTINCT element_id) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_context' AND rating.is_current)
          WHEN 'related_occupations' THEN (SELECT count(*) FROM onet_related_occupations relation WHERE relation.occupation_code=occupation.onet_soc_code AND relation.is_current)
          WHEN 'source_taxonomy' THEN (SELECT count(*) FROM source_occupation_taxonomy_memberships membership WHERE membership.occupation_code=occupation.onet_soc_code AND membership.is_current)
          WHEN 'soc_succession' THEN (SELECT count(*) FROM source_occupation_successions succession WHERE succession.successor_code=occupation.onet_soc_code AND succession.is_current)
        END::integer,
        CASE domain.name
          WHEN 'task_ratings' THEN (SELECT count(*) FROM onet_task_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.is_current)
          WHEN 'skills' THEN (SELECT count(*) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='skill' AND rating.is_current)
          WHEN 'abilities' THEN (SELECT count(*) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='ability' AND rating.is_current)
          WHEN 'work_activities' THEN (SELECT count(*) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_activity' AND rating.is_current)
          WHEN 'work_context' THEN (SELECT count(*) FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_context' AND rating.is_current)
          ELSE 0
        END::integer,
        CASE
          WHEN domain.name='task_ratings' AND EXISTS (
            SELECT 1 FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current AND NOT task.weighting_eligible
          ) THEN 'partial'
          WHEN domain.name='soc_succession' AND NOT EXISTS (
            SELECT 1 FROM source_occupation_successions succession WHERE succession.successor_code=occupation.onet_soc_code AND succession.is_current
          ) THEN 'not_applicable'
          WHEN domain.name='skills' AND NOT EXISTS (
            SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='skill' AND rating.is_current
          ) THEN 'missing'
          WHEN domain.name IN ('titles','tasks','abilities','work_activities','work_context','source_taxonomy') AND CASE domain.name
            WHEN 'titles' THEN NOT EXISTS (SELECT 1 FROM source_occupation_titles title WHERE title.occupation_code=occupation.onet_soc_code AND title.is_current)
            WHEN 'tasks' THEN NOT EXISTS (SELECT 1 FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current)
            WHEN 'abilities' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='ability' AND rating.is_current)
            WHEN 'work_activities' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_activity' AND rating.is_current)
            WHEN 'work_context' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_context' AND rating.is_current)
            WHEN 'source_taxonomy' THEN NOT EXISTS (SELECT 1 FROM source_occupation_taxonomy_memberships membership WHERE membership.occupation_code=occupation.onet_soc_code AND membership.is_current)
          END THEN 'missing'
          WHEN domain.name IN ('titles','tasks','task_ratings','skills','abilities','work_activities','work_context','source_taxonomy') THEN 'complete'
          ELSE 'present'
        END,
        CASE
          WHEN domain.name='task_ratings' AND EXISTS (
            SELECT 1 FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current AND NOT task.weighting_eligible
          ) THEN jsonb_build_array(jsonb_build_object(
            'code','missing_task_ratings','policy',$4::text,
            'affected_tasks',(SELECT count(*) FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current AND NOT task.weighting_eligible),
            'imputed',false
          ))
          WHEN domain.name IN ('skills','abilities','work_activities','work_context') AND CASE domain.name
            WHEN 'skills' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='skill' AND rating.is_current)
            WHEN 'abilities' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='ability' AND rating.is_current)
            WHEN 'work_activities' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_activity' AND rating.is_current)
            WHEN 'work_context' THEN NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='work_context' AND rating.is_current)
          END THEN '[{"code":"missing_source_domain","imputed":false}]'::jsonb
          ELSE '[]'::jsonb
        END,
        $2, $3, $5
      FROM onet_occupations occupation
      CROSS JOIN (VALUES
        ('titles'),('tasks'),('task_ratings'),('skills'),('abilities'),('work_activities'),
        ('work_context'),('related_occupations'),('source_taxonomy'),('soc_succession')
      ) AS domain(name)
      WHERE occupation.onet_soc_code=ANY($1::text[]) AND occupation.is_current
    """, codes, source_id, run_id, TASK_RATING_POLICY_VERSION, version)


async def _upsert_promotion_policy(
    connection: asyncpg.Connection,
    codes: list[str],
    source_ids: dict[str, int],
    run_id: int,
    version: str,
) -> dict[str, Any]:
    occupations = await connection.fetch("""
      SELECT source.onet_soc_code, source.title, source.jobs_vs_ai_occupation_id,
             source.source_record_id, source.row_hash, editorial.slug editorial_slug,
             editorial.title editorial_title
      FROM onet_occupations source
      LEFT JOIN occupations editorial ON editorial.id=source.jobs_vs_ai_occupation_id
      WHERE source.onet_soc_code=ANY($1::text[]) AND source.is_current
      ORDER BY source.onet_soc_code
    """, codes)
    coverage_rows = await connection.fetch("""
      SELECT occupation.onet_soc_code,
        (SELECT count(*) FROM onet_tasks task
          WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current) task_count,
        (SELECT count(*) FROM onet_tasks task
          WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current AND task.weighting_eligible) eligible_task_count,
        (SELECT count(DISTINCT element_id) FROM onet_element_ratings rating
          WHERE rating.occupation_code=occupation.onet_soc_code AND rating.is_current AND rating.element_type='skill') skill_count
      FROM onet_occupations occupation
      WHERE occupation.onet_soc_code=ANY($1::text[]) AND occupation.is_current
    """, codes)
    coverage = {row["onet_soc_code"]: row for row in coverage_rows}
    successions = await connection.fetch("""
      SELECT succession.*, taxonomy.id source_taxonomy_id
      FROM source_occupation_successions succession
      JOIN source_taxonomies taxonomy ON taxonomy.id=succession.predecessor_taxonomy_id
      WHERE succession.successor_code=ANY($1::text[]) AND succession.is_current
      ORDER BY succession.successor_code, succession.predecessor_code
    """, codes)
    by_successor: dict[str, list[asyncpg.Record]] = {}
    for succession in successions:
        by_successor.setdefault(succession["successor_code"], []).append(succession)
    taxonomy_2019 = int(await connection.fetchval("""
      SELECT id FROM source_taxonomies WHERE taxonomy_code='ONET_SOC' AND taxonomy_version='2019'
    """))

    identity_ids: dict[str, int] = {}
    for occupation in occupations:
        code = occupation["onet_soc_code"]
        identity_key = (
            f"jobsvsai:{occupation['editorial_slug']}" if occupation["editorial_slug"]
            else f"onet-soc-2019:{code}"
        )
        identity_ids[code] = int(await connection.fetchval("""
          INSERT INTO canonical_occupation_identities (
            identity_key, current_source_code, jobs_vs_ai_occupation_id, identity_origin,
            created_by_policy, source_version
          ) VALUES ($1,$2,$3,$4,$5,$6)
          ON CONFLICT (identity_key) DO UPDATE SET
            current_source_code=EXCLUDED.current_source_code,
            jobs_vs_ai_occupation_id=COALESCE(EXCLUDED.jobs_vs_ai_occupation_id, canonical_occupation_identities.jobs_vs_ai_occupation_id),
            source_version=EXCLUDED.source_version, updated_at=now()
          RETURNING id
        """, identity_key, code, occupation["jobs_vs_ai_occupation_id"],
             "existing_editorial" if occupation["jobs_vs_ai_occupation_id"] else "source_import",
             IDENTITY_POLICY_VERSION, version))

    await connection.execute(
        "UPDATE occupation_identity_resolutions SET is_current=false WHERE target_occupation_code=ANY($1::text[])", codes,
    )
    resolution_values: list[tuple[Any, ...]] = []
    complex_codes: set[str] = set()
    for occupation in occupations:
        code = occupation["onet_soc_code"]
        mappings = by_successor.get(code, [])
        if not mappings:
            resolution_values.append((
                None, taxonomy_2019, code, identity_ids[code], code, "new_source_identity", True,
                "auto_resolved", "No predecessor mapping in the official 2010→2019 crosswalk.",
                source_ids["onet"], run_id, occupation["source_record_id"], version, occupation["row_hash"],
            ))
            continue
        for mapping in mappings:
            mapping_type = mapping["mapping_type"]
            resolution_type = {
                "unchanged": "unchanged_continuity",
                "renamed": "renamed_continuity",
                "recoded": "recoded_continuity",
                "merge": "merge_new_identity",
                "split": "split_new_identity",
                "complex": "complex_manual",
            }[mapping_type]
            automatic = mapping_type != "complex"
            if not automatic:
                complex_codes.add(code)
            resolution_values.append((
                mapping["id"], mapping["source_taxonomy_id"], mapping["predecessor_code"],
                identity_ids[code], code, resolution_type, automatic,
                "auto_resolved" if automatic else "pending",
                "Historical scores are never merged, split, or allocated automatically.",
                mapping["source_id"], run_id, mapping["source_record_id"], mapping["source_version"], mapping["row_hash"],
            ))
    await connection.executemany("""
      INSERT INTO occupation_identity_resolutions (
        succession_id, source_taxonomy_id, source_occupation_code, target_identity_id,
        target_occupation_code, resolution_type, automatic_allowed, review_status, notes,
        allocation_weight, policy_version, source_id, import_run_id, source_record_id,
        source_version, row_hash
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NULL,$10,$11,$12,$13,$14,$15)
      ON CONFLICT (succession_id, source_occupation_code, target_occupation_code) DO UPDATE SET
        target_identity_id=EXCLUDED.target_identity_id, resolution_type=EXCLUDED.resolution_type,
        automatic_allowed=EXCLUDED.automatic_allowed, review_status=EXCLUDED.review_status,
        notes=EXCLUDED.notes, allocation_weight=NULL, policy_version=EXCLUDED.policy_version,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_record_id=EXCLUDED.source_record_id, source_version=EXCLUDED.source_version,
        row_hash=EXCLUDED.row_hash, is_current=true
    """, [
        (*value[:9], IDENTITY_POLICY_VERSION, *value[9:]) for value in resolution_values
    ])

    publication_values: list[tuple[Any, ...]] = []
    profile_values: list[tuple[Any, ...]] = []
    for occupation in occupations:
        code = occupation["onet_soc_code"]
        stats = coverage[code]
        task_count = int(stats["task_count"] or 0)
        eligible_count = int(stats["eligible_task_count"] or 0)
        skill_count = int(stats["skill_count"] or 0)
        eligible_ratio = eligible_count / task_count if task_count else 0
        blocking: list[str] = []
        if code in complex_codes:
            blocking.append("identity_review_required")
        if task_count == 0:
            blocking.append("no_task_statements")
        if eligible_count == 0:
            blocking.append("no_complete_task_ratings")
        elif eligible_ratio < 0.5:
            blocking.append("complete_task_rating_coverage_below_50_percent")
        if skill_count == 0:
            blocking.append("no_skill_ratings")
        scoring_eligible = (
            code not in complex_codes and task_count > 0 and eligible_count > 0
            and eligible_ratio >= 0.5 and skill_count > 0
        )
        lifecycle = "normalized" if code in complex_codes else "scoring_ready" if scoring_eligible else "identity_resolved"
        profile_values.append((
            identity_ids[code], code, lifecycle, True, scoring_eligible, False,
            LIFECYCLE_POLICY_VERSION, SCORING_READINESS_POLICY_VERSION,
            json.dumps(blocking), source_ids["onet"], run_id, version,
        ))

        public_title = occupation["editorial_title"] or occupation["title"]
        review_reasons = [] if occupation["editorial_title"] else _title_review_reasons(public_title)
        review_status = "approved" if occupation["editorial_title"] else "pending" if review_reasons else "not_required"
        publication_values.append((
            identity_ids[code], "en", public_title,
            occupation["editorial_slug"] or _public_slug(public_title, code), "US",
            "review_required" if review_reasons else "staged", review_status,
            "jobsvsai_editorial" if occupation["editorial_title"] else "onet_preferred",
            json.dumps(review_reasons), source_ids["onet"], run_id, version,
        ))
    await connection.executemany("""
      INSERT INTO occupation_promotion_profiles (
        identity_id, source_occupation_code, lifecycle_state, ingestion_eligible,
        scoring_eligible, public_activation_eligible, lifecycle_policy_version,
        scoring_policy_version, blocking_reasons, source_id, import_run_id, source_version
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12)
      ON CONFLICT (identity_id) DO UPDATE SET
        source_occupation_code=EXCLUDED.source_occupation_code, lifecycle_state=EXCLUDED.lifecycle_state,
        ingestion_eligible=EXCLUDED.ingestion_eligible, scoring_eligible=EXCLUDED.scoring_eligible,
        public_activation_eligible=false, lifecycle_policy_version=EXCLUDED.lifecycle_policy_version,
        scoring_policy_version=EXCLUDED.scoring_policy_version, blocking_reasons=EXCLUDED.blocking_reasons,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_version=EXCLUDED.source_version, evaluated_at=now()
    """, profile_values)
    await connection.executemany("""
      INSERT INTO occupation_publications (
        identity_id, locale, canonical_public_title, seo_slug, source_geography,
        activation_status, editorial_review_status, title_source, review_reasons,
        source_id, import_run_id, source_version
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12)
      ON CONFLICT (identity_id, locale, source_geography) DO UPDATE SET
        canonical_public_title=EXCLUDED.canonical_public_title, seo_slug=EXCLUDED.seo_slug,
        activation_status=CASE WHEN occupation_publications.activation_status='public' THEN 'public' ELSE EXCLUDED.activation_status END,
        editorial_review_status=EXCLUDED.editorial_review_status, title_source=EXCLUDED.title_source,
        review_reasons=EXCLUDED.review_reasons, source_id=EXCLUDED.source_id,
        import_run_id=EXCLUDED.import_run_id, source_version=EXCLUDED.source_version, updated_at=now()
    """, publication_values)

    await connection.execute(
        "DELETE FROM occupation_search_aliases WHERE identity_id=ANY($1::bigint[])", list(identity_ids.values()),
    )
    title_rows = await connection.fetch("""
      SELECT title.id, title.occupation_code, title.title, title.title_type,
             title.source_id, title.source_version, title.source_metadata
      FROM source_occupation_titles title
      WHERE title.occupation_code=ANY($1::text[]) AND title.is_current
      ORDER BY title.occupation_code, title.title_type, title.title
    """, codes)
    alias_values: list[tuple[Any, ...]] = []
    for title in title_rows:
        code = title["occupation_code"]
        if code not in identity_ids:
            continue
        preferred = title["title_type"] in ("preferred", "short")
        alias_values.append((
            identity_ids[code], title["id"], title["title"], "en", "US", preferred,
            "staged", "not_required" if preferred else "pending",
            title["source_id"], run_id, title["source_version"],
        ))
    historical_rows = await connection.fetch("""
      SELECT title.id, title.title, title.source_id, title.source_version,
             title.source_metadata->>'successor_code' successor_code
      FROM source_occupation_titles title
      WHERE title.title_type='historical' AND title.is_current
        AND title.source_metadata->>'successor_code'=ANY($1::text[])
    """, codes)
    for title in historical_rows:
        code = title["successor_code"]
        alias_values.append((
            identity_ids[code], title["id"], title["title"], "en", "US", False,
            "staged", "pending", title["source_id"], run_id, title["source_version"],
        ))
    await connection.executemany("""
      INSERT INTO occupation_search_aliases (
        identity_id, source_title_id, alias, locale, source_geography, searchable,
        activation_status, editorial_review_status, source_id, import_run_id, source_version
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
      ON CONFLICT (identity_id, alias, locale, source_geography) DO UPDATE SET
        source_title_id=EXCLUDED.source_title_id, searchable=EXCLUDED.searchable,
        activation_status=EXCLUDED.activation_status,
        editorial_review_status=EXCLUDED.editorial_review_status,
        source_id=EXCLUDED.source_id, import_run_id=EXCLUDED.import_run_id,
        source_version=EXCLUDED.source_version
    """, alias_values)

    await connection.execute("""
      INSERT INTO source_attribution_requirements (
        source_id, source_version, license_name, license_url, attribution_text,
        publisher_name, source_url, publication_required, publication_gate, metadata
      ) VALUES ($1,$2,'Creative Commons Attribution 4.0 International',
        'https://creativecommons.org/licenses/by/4.0/',
        'This product uses the O*NET Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA).',
        'U.S. Department of Labor, Employment and Training Administration',
        'https://www.onetcenter.org/database.html',true,'before_public_activation',
        '{"private_ingestion_allowed":true,"public_activation_requires_attribution":true}'::jsonb)
      ON CONFLICT (source_id, source_version) DO UPDATE SET
        license_name=EXCLUDED.license_name, license_url=EXCLUDED.license_url,
        attribution_text=EXCLUDED.attribution_text, publisher_name=EXCLUDED.publisher_name,
        source_url=EXCLUDED.source_url, publication_required=true,
        publication_gate=EXCLUDED.publication_gate, metadata=EXCLUDED.metadata
    """, source_ids["onet"], version)

    matrix = await connection.fetchrow("SELECT * FROM occupation_promotion_matrix")
    invalid = await connection.fetchrow("""
      SELECT
        (SELECT count(*) FROM occupation_identity_resolutions WHERE is_current AND allocation_weight IS NOT NULL) invented_weights,
        (SELECT count(*) FROM occupation_promotion_profiles WHERE public_activation_eligible) public_ready,
        (SELECT count(*) FROM occupation_publications WHERE activation_status='public') public_activated,
        (SELECT count(*) FROM onet_element_ratings WHERE element_type='skill' AND skill_classification IS NULL AND is_current) unclassified_skill_ratings,
        (SELECT count(*) FROM occupation_identity_resolutions WHERE is_current
          AND resolution_type='complex_manual' AND (automatic_allowed OR review_status<>'pending')) invalid_complex
    """)
    policy_checks_pass = all(int(invalid[key] or 0) == 0 for key in invalid.keys())
    return {
        "matrix": dict(matrix),
        "checks": dict(invalid),
        "policy_checks_pass": policy_checks_pass,
        "policy_versions": {
            "identity": IDENTITY_POLICY_VERSION,
            "lifecycle": LIFECYCLE_POLICY_VERSION,
            "scoring_readiness": SCORING_READINESS_POLICY_VERSION,
        },
    }


async def validation_report(connection: asyncpg.Connection, version: str | None = None) -> dict[str, Any]:
    version_filter = "AND source_version=$1" if version else ""
    params: list[Any] = [version] if version else []
    row = await connection.fetchrow(f"""
      SELECT
        (SELECT count(*) FROM onet_occupations WHERE is_current {version_filter}) occupations,
        (SELECT count(*) FROM onet_occupations WHERE is_current AND jobs_vs_ai_occupation_id IS NOT NULL {version_filter}) product_links,
        (SELECT count(*) FROM onet_alternate_titles WHERE is_current {version_filter}) alternate_titles,
        (SELECT count(*) FROM onet_tasks WHERE is_current {version_filter}) tasks,
        (SELECT count(*) FROM onet_task_ratings WHERE is_current {version_filter}) task_ratings,
        (SELECT count(*) FROM onet_elements WHERE is_current {version_filter}) elements,
        (SELECT count(*) FROM onet_element_ratings WHERE is_current {version_filter}) element_ratings,
        (SELECT count(*) FROM onet_related_occupations WHERE is_current {version_filter}) related_occupations,
        (SELECT count(*) FROM onet_scales WHERE is_current {version_filter}) scales,
        (SELECT count(*) FROM source_occupation_titles WHERE is_current) source_titles,
        (SELECT count(*) FROM source_taxonomies WHERE is_current) source_taxonomies,
        (SELECT count(*) FROM source_taxonomy_nodes WHERE is_current) source_taxonomy_nodes,
        (SELECT count(*) FROM source_occupation_taxonomy_memberships WHERE is_current) taxonomy_memberships,
        (SELECT count(*) FROM source_occupation_successions WHERE is_current) succession_mappings,
        (SELECT count(*) FROM source_occupation_successions WHERE is_current AND allocation_weight IS NOT NULL) invented_succession_weights,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND weighting_eligible {version_filter}) weighting_eligible_tasks,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND NOT weighting_eligible {version_filter}) weighting_ineligible_tasks,
        (SELECT count(*) FROM onet_occupation_domain_coverage WHERE coverage_status IN ('partial','missing')) incomplete_domain_rows,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND importance_score IS NULL {version_filter}) tasks_missing_importance,
        (SELECT count(*) FROM onet_tasks WHERE is_current AND frequency_score IS NULL {version_filter}) tasks_missing_frequency,
        (SELECT count(*) FROM onet_occupations occupation WHERE occupation.is_current {version_filter}
          AND NOT EXISTS (SELECT 1 FROM onet_tasks task WHERE task.occupation_code=occupation.onet_soc_code AND task.is_current)) occupations_without_tasks,
        (SELECT count(*) FROM onet_occupations occupation WHERE occupation.is_current {version_filter}
          AND NOT EXISTS (SELECT 1 FROM onet_element_ratings rating WHERE rating.occupation_code=occupation.onet_soc_code AND rating.element_type='skill' AND rating.is_current)) occupations_without_skills,
        (SELECT count(*) FROM onet_task_ratings rating LEFT JOIN onet_tasks task ON task.task_id=rating.task_id
          WHERE rating.is_current AND task.task_id IS NULL {version_filter.replace('source_version', 'rating.source_version')}) orphan_task_ratings,
        (SELECT count(*) FROM onet_element_ratings rating LEFT JOIN onet_elements element
          ON element.element_type=rating.element_type AND element.element_id=rating.element_id
          WHERE rating.is_current AND element.element_id IS NULL {version_filter.replace('source_version', 'rating.source_version')}) orphan_element_ratings,
        (SELECT count(*) FROM onet_task_ratings rating LEFT JOIN onet_scales scale ON scale.scale_id=rating.scale_id
          WHERE rating.is_current AND scale.scale_id IS NULL {version_filter.replace('source_version', 'rating.source_version')}) orphan_task_scales,
        (SELECT count(*) FROM onet_element_ratings rating LEFT JOIN onet_scales scale ON scale.scale_id=rating.scale_id
          WHERE rating.is_current AND scale.scale_id IS NULL {version_filter.replace('source_version', 'rating.source_version')}) orphan_element_scales
    """, *params)
    type_rows = await connection.fetch(f"""
      SELECT element_type, count(*) elements,
        (SELECT count(*) FROM onet_element_ratings rating
         WHERE rating.element_type=element.element_type AND rating.is_current
           {version_filter.replace('source_version', 'rating.source_version')}) ratings
      FROM onet_elements element WHERE is_current {version_filter.replace('source_version', 'element.source_version')}
      GROUP BY element_type ORDER BY element_type
    """, *params)
    report = dict(row)
    report["by_element_type"] = {item["element_type"]: {"elements": item["elements"], "ratings": item["ratings"]} for item in type_rows}
    report["relationship_checks_pass"] = (
        report["orphan_task_ratings"] == 0
        and report["orphan_element_ratings"] == 0
        and report["orphan_task_scales"] == 0
        and report["orphan_element_scales"] == 0
        and report["invented_succession_weights"] == 0
    )
    report["coverage_warnings"] = {
        "occupations_without_skills": report["occupations_without_skills"],
        "tasks_missing_importance": report["tasks_missing_importance"],
        "tasks_missing_frequency": report["tasks_missing_frequency"],
        "incomplete_domain_rows": report["incomplete_domain_rows"],
    }
    return report


async def import_subset(data_dir: Path, subset_file: Path, version: str, full: bool = False) -> dict[str, Any]:
    if full:
        subset_codes = {
            row["O*NET-SOC Code"] for row in _read_csv(data_dir / DATASET_FILES["occupation_data"])
        }
    else:
        subset_codes = {
            line.strip() for line in subset_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        if not 20 <= len(subset_codes) <= 50:
            raise ValueError(f"Representative subset must contain 20–50 occupations; got {len(subset_codes)}")

    rows, raw_records, file_hashes = load_subset(data_dir, version, subset_codes)
    run_key = hashlib.sha256(json.dumps({
        "importer": IMPORTER_VERSION,
        "version": version,
        "codes": sorted(subset_codes),
        "file_hashes": file_hashes,
    }, sort_keys=True).encode("utf-8")).hexdigest()
    subset_name = "full" if full else subset_file.stem
    connection = await asyncpg.connect(_database_url())
    run_id: int | None = None
    try:
        if full:
            gate = await connection.fetchrow("""
              SELECT
                (SELECT count(*) FROM occupation_promotion_profiles
                  WHERE source_occupation_code=ANY($1::text[])) representative_profiles,
                (SELECT count(*) FROM occupation_identity_resolutions
                  WHERE is_current AND allocation_weight IS NOT NULL) invented_weights,
                (SELECT count(*) FROM occupation_publications WHERE activation_status='public') source_publications,
                (SELECT count(*) FROM import_runs
                  WHERE scope LIKE 'subset:%' AND status='complete'
                    AND (metadata->'promotion'->>'policy_checks_pass')::boolean) passing_subset_runs
            """, [
                line.strip() for line in subset_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ])
            if (
                int(gate["representative_profiles"] or 0) != 31
                or int(gate["invented_weights"] or 0) != 0
                or int(gate["source_publications"] or 0) != 0
                or int(gate["passing_subset_runs"] or 0) == 0
            ):
                raise RuntimeError(f"Full import blocked by representative promotion gate: {dict(gate)}")
        source_ids: dict[str, int] = {}
        source_ids["onet"] = int(await connection.fetchval("""
          INSERT INTO data_sources (name, source_url, version, published_at, metadata)
          VALUES ($1, $2, $3, $4::timestamptz, $5::jsonb)
          ON CONFLICT (name) DO UPDATE SET
            source_url=EXCLUDED.source_url, version=EXCLUDED.version,
            published_at=EXCLUDED.published_at, metadata=EXCLUDED.metadata
          RETURNING id
        """, f"O*NET Database {version}", "https://www.onetcenter.org/database.html", version,
             datetime(2026, 5, 1, tzinfo=timezone.utc) if version == "30.3" else None,
             json.dumps({"license": "CC BY 4.0", "format": "CSV", "importer": IMPORTER_VERSION})))
        source_ids["crosswalk"] = int(await connection.fetchval("""
          INSERT INTO data_sources (name, source_url, version, metadata)
          VALUES ('O*NET-SOC 2010 to 2019 Crosswalk', $1, '2010-to-2019', $2::jsonb)
          ON CONFLICT (name) DO UPDATE SET source_url=EXCLUDED.source_url,
            version=EXCLUDED.version, metadata=EXCLUDED.metadata
          RETURNING id
        """, CROSSWALK_URL, json.dumps({"format": "CSV", "importer": IMPORTER_VERSION})))
        source_ids["soc2018"] = int(await connection.fetchval("""
          INSERT INTO data_sources (name, source_url, version, metadata)
          VALUES ('Standard Occupational Classification', $1, '2018', $2::jsonb)
          ON CONFLICT (name) DO UPDATE SET source_url=EXCLUDED.source_url,
            version=EXCLUDED.version, metadata=EXCLUDED.metadata
          RETURNING id
        """, SOC_2018_URL, json.dumps({"publisher": "U.S. Bureau of Labor Statistics", "importer": IMPORTER_VERSION})))
        source_id = source_ids["onet"]
        run_id = int(await connection.fetchval("""
          INSERT INTO import_runs (
            source_id, status, started_at, run_key, scope, source_version, manifest, metadata
          ) VALUES ($1, 'running', now(), $2, $3, $4, $5::jsonb, $6::jsonb)
          RETURNING id
        """, source_id, run_key, "full" if full else f"subset:{subset_name}", version,
             json.dumps({
                 "codes": sorted(subset_codes), "files": file_hashes,
                 "secondary_sources": ["O*NET-SOC 2010 to 2019 Crosswalk", "Standard Occupational Classification 2018"],
             }),
             json.dumps({"score_recalculation": False, "ai_capability_mapping": False})))
        before_scores = await _score_fingerprint(connection)
        await connection.execute("SELECT pg_advisory_lock(hashtext($1))", f"jobsvsai:onet:{version}")
        try:
            async with connection.transaction():
                source_records: dict[tuple[str, str], int] = {}
                records_written = 0
                for source_key in ("onet", "crosswalk", "soc2018"):
                    records = [record for record in raw_records if record.source_key == source_key]
                    source_version = {"onet": version, "crosswalk": "2010-to-2019", "soc2018": "2018"}[source_key]
                    references, writes = await _stage_source_versions(
                        connection, source_ids[source_key], run_id, source_version, records,
                    )
                    source_records.update(references)
                    records_written += writes
                await _upsert_canonical(
                    connection, rows, source_records, source_id, run_id, version, subset_name,
                )
                await _upsert_source_models(
                    connection, rows, source_records, source_ids, run_id, version,
                )
                promotion = await _upsert_promotion_policy(
                    connection, sorted(subset_codes), source_ids, run_id, version,
                )
                if not promotion["policy_checks_pass"]:
                    raise RuntimeError(f"Occupation promotion policy gate failed: {promotion}")
                after_scores = await _score_fingerprint(connection)
                if before_scores != after_scores:
                    raise RuntimeError("Score guard failed: O*NET import changed scoring state")
                validation = await validation_report(connection, version)
                if not validation["relationship_checks_pass"]:
                    raise RuntimeError(f"Relationship validation failed: {validation}")
                dataset_counts = dict(Counter(record.dataset for record in raw_records))
                metadata = {
                    "dataset_counts": dataset_counts,
                    "validation": validation,
                    "source_file_hashes": file_hashes,
                    "score_guard": {"passed": True, "fingerprint": before_scores},
                    "promotion": promotion,
                    "ai_capability_mapping": False,
                    "score_recalculation": False,
                }
                await connection.execute("""
                  UPDATE import_runs SET status='complete', records_read=$2, records_written=$3,
                    completed_at=now(), metadata=$4::jsonb WHERE id=$1
                """, run_id, len(raw_records), records_written, json.dumps(metadata, default=str))
        finally:
            await connection.execute("SELECT pg_advisory_unlock(hashtext($1))", f"jobsvsai:onet:{version}")
        return {
            "run_id": run_id,
            "run_key": run_key,
            "version": version,
            "subset": subset_name,
            "scope": "full" if full else "representative_subset",
            "records_read": len(raw_records),
            "records_written": records_written,
            "validation": validation,
            "promotion": promotion,
            "score_guard": True,
        }
    except Exception as error:
        if run_id is not None:
            await connection.execute(
                "UPDATE import_runs SET status='failed', error=$2, completed_at=now() WHERE id=$1",
                run_id, str(error)[:4000],
            )
        raise
    finally:
        await connection.close()


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Import an isolated, score-neutral O*NET subset")
    parser.add_argument("command", choices=("import", "validate"), nargs="?", default="import")
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--subset-file", type=Path, default=Path("ingestion/subsets/representative_31.txt"))
    parser.add_argument("--full", action="store_true", help="Import the complete private O*NET release after policy preflight")
    args = parser.parse_args()
    data_dir = args.data_dir or Path(f"ingestion/data/onet/{args.version}")
    if args.command == "import":
        result = await import_subset(data_dir, args.subset_file, args.version, full=args.full)
    else:
        connection = await asyncpg.connect(_database_url())
        try:
            result = await validation_report(connection, args.version)
        finally:
            await connection.close()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
