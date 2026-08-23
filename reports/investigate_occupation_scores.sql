-- JobsVsAI — production occupation_scores investigation
-- Read-only, and now enforced rather than merely promised: the SET below makes the whole
-- session read-only, so an accidental edit to this file fails instead of writing.
--
--   ./scripts/psql-readonly.sh -f reports/investigate_occupation_scores.sql
--   (or paste section by section into ./scripts/psql-readonly.sh)
--
SET default_transaction_read_only = on;
--
-- Answers, in order:
--   1. which occupations own the rows
--   2. model version for every row
--   3. calculated timestamps
--   4. which occupations have multiple historical rows
--   5. which process created each row
--   6. whether readers can disagree about "latest"
--   7. which rows are safely archivable

\echo '== 0. headline counts =========================================================='
SELECT
  (SELECT count(*) FROM occupations)                                   AS occupations,
  (SELECT count(*) FROM occupations WHERE is_active)                   AS active_occupations,
  (SELECT count(*) FROM occupation_scores)                             AS occupation_score_rows,
  (SELECT count(DISTINCT occupation_id) FROM occupation_scores)        AS occupations_with_scores,
  (SELECT count(*) FROM score_derivations)                             AS score_derivation_rows,
  (SELECT count(*) FROM score_history)                                 AS score_history_rows,
  (SELECT count(*) FROM task_ai_scores)                                AS task_ai_score_rows,
  (SELECT count(*) FROM scoring_jobs)                                  AS scoring_job_rows;

\echo '== 1-5. every row, with origin attribution ====================================='
-- Origin rule (exact, not heuristic):
--   worker/jobs.py stamps input_versions with a 'reason' key via
--     CAST(:input_versions AS jsonb) || jsonb_build_object('reason', ...)
--   migration 002 seeds input_versions without any 'reason' key.
--   Only three writers of this table exist in the repository: migration 002 (INSERT),
--   migration 004 (UPDATE only, no INSERT), and worker/jobs.py (INSERT).
SELECT
  occupation.slug,
  score.id                                            AS score_id,
  model.version                                       AS model_version,
  score.calculated_at,
  score.ai_exposure,
  score.replacement_risk,
  score.input_versions ->> 'reason'                   AS worker_reason,
  CASE
    WHEN score.input_versions ? 'reason' THEN 'worker: recalculate_occupation'
    WHEN score.input_versions ->> 'occupation' = 'demo-2026-08' THEN 'migration 002 demo seed'
    ELSE 'unknown — investigate'
  END                                                 AS origin,
  (history.id IS NOT NULL)                            AS in_score_history,
  (derivation.id IS NOT NULL)                         AS has_derivation,
  row_number() OVER (
    PARTITION BY score.occupation_id
    ORDER BY score.calculated_at DESC, score.id DESC
  )                                                   AS recency_rank
FROM occupation_scores score
JOIN occupations occupation      ON occupation.id = score.occupation_id
JOIN scoring_model_versions model ON model.id     = score.model_version_id
LEFT JOIN score_history history   ON history.source_score_id = score.id
LEFT JOIN score_derivations derivation ON derivation.score_id = score.id
ORDER BY occupation.slug, score.calculated_at DESC, score.id DESC;

\echo '== 4. occupations carrying more than one row =================================='
SELECT occupation.slug,
       count(*)                     AS rows,
       min(score.calculated_at)     AS first_calculated,
       max(score.calculated_at)     AS last_calculated,
       count(*) FILTER (WHERE score.input_versions ? 'reason')     AS worker_rows,
       count(*) FILTER (WHERE NOT (score.input_versions ? 'reason')) AS seeded_rows
FROM occupation_scores score
JOIN occupations occupation ON occupation.id = score.occupation_id
GROUP BY occupation.slug
HAVING count(*) > 1
ORDER BY count(*) DESC, occupation.slug;

\echo '== 5b. scoring_jobs trail (why the worker ran, if it was enqueued) ============='
SELECT job.id, occupation.slug, job.reason, job.dependency_type, job.dependency_id,
       job.status, job.queued_at, job.completed_at
FROM scoring_jobs job
LEFT JOIN occupations occupation ON occupation.id = job.occupation_id
ORDER BY job.id;

\echo '== 6. can readers disagree about "latest"? ===================================='
-- Public list/detail/rankings/related-careers order by calculated_at DESC only.
-- careers.py and the admin derivation additionally tiebreak on id DESC.
-- Any occupation below has a calculated_at tie and can therefore be resolved
-- differently by different endpoints. Empty result = no ambiguity today.
SELECT occupation.slug, score.calculated_at, count(*) AS tied_rows,
       array_agg(score.id ORDER BY score.id) AS score_ids
FROM occupation_scores score
JOIN occupations occupation ON occupation.id = score.occupation_id
GROUP BY occupation.slug, score.calculated_at
HAVING count(*) > 1
ORDER BY occupation.slug;

\echo '== 7. archivability: rows never served (superseded) ============================'
WITH ranked AS (
  SELECT score.id, occupation.slug, model.version AS model_version, score.calculated_at,
         score.input_versions ? 'reason' AS worker_written,
         row_number() OVER (
           PARTITION BY score.occupation_id
           ORDER BY score.calculated_at DESC, score.id DESC
         ) AS recency_rank
  FROM occupation_scores score
  JOIN occupations occupation ON occupation.id = score.occupation_id
  JOIN scoring_model_versions model ON model.id = score.model_version_id
)
SELECT CASE WHEN recency_rank = 1 THEN 'CURRENT (served)' ELSE 'SUPERSEDED (archivable)' END AS disposition,
       count(*) AS rows,
       array_agg(slug || '#' || id ORDER BY slug) AS members
FROM ranked
GROUP BY 1
ORDER BY 1;

\echo '== 7b. FK dependents that must be handled before any archival =================='
SELECT 'score_derivations' AS dependent_table, count(*) AS rows_referencing_superseded
FROM score_derivations d
WHERE d.score_id IN (
  SELECT id FROM (
    SELECT id, row_number() OVER (PARTITION BY occupation_id
      ORDER BY calculated_at DESC, id DESC) AS rank FROM occupation_scores
  ) r WHERE r.rank > 1)
UNION ALL
SELECT 'score_history', count(*)
FROM score_history h
WHERE h.source_score_id IN (
  SELECT id FROM (
    SELECT id, row_number() OVER (PARTITION BY occupation_id
      ORDER BY calculated_at DESC, id DESC) AS rank FROM occupation_scores
  ) r WHERE r.rank > 1);

\echo '== 8. what the public would serve right now (post publication gate) ============'
SELECT count(*) AS publicly_visible_occupations
FROM occupations o
WHERE o.is_active
  AND EXISTS (
    SELECT 1 FROM canonical_occupation_identities i
    JOIN occupation_publications p ON p.identity_id = i.id
    WHERE i.jobs_vs_ai_occupation_id = o.id AND p.activation_status = 'public'
  );
