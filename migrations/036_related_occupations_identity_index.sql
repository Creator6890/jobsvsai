-- 036 — Index the related-occupations lookup by identity.
--
-- Additive. One index, no data change, no schema change to any existing column.
--
-- ## Why
--
-- Every public occupation read hydrates its related careers through this clause:
--
--     JOIN LATERAL (
--       SELECT max(newer.content_run_id) AS content_run_id
--       FROM public_occupation_related_occupations newer
--       WHERE newer.identity_id = related.identity_id
--     ) latest_run ON latest_run.content_run_id = related.content_run_id
--
-- It filters on `identity_id` and aggregates `content_run_id`. Every existing index on the
-- table leads with `content_run_id` — `public_content_related_idx (content_run_id,
-- identity_id, ...)` and the unique key of the same shape — so none of them can serve it.
-- The planner had to scan.
--
-- That was survivable while content runs covered only the 507-occupation launch cohort and
-- the table held 6,470 rows. Generating content for the whole 1,016-occupation corpus, which
-- the preliminary-estimate layer needs in order to give estimated occupations pages, took it
-- to 31,401 rows. The scan is per hydrated occupation, so the cost is multiplied by the page
-- size: `/api/v1/occupations?limit=500` went from comfortable to **8.3 seconds**, past the
-- frontend's fetch timeout, and `/compare` — which loads every occupation to populate its
-- selector — started returning 500.
--
-- This index makes the LATERAL an index-only scan. Measured on production immediately after
-- creation: `limit=500` fell from 8.3s to 2.6s and `/compare` returned to 200.
--
-- The lesson worth keeping is not "add an index". It is that a data-volume change in one
-- pipeline surfaced as an outage in an unrelated page, because the cost was per-row in an
-- N+1 hydration nobody had reason to look at. The healthcheck passed throughout the release
-- itself and only broke once the content run landed, which is exactly when nothing was
-- watching it.

BEGIN;

CREATE INDEX IF NOT EXISTS public_content_related_identity_run_idx
    ON public_occupation_related_occupations (identity_id, content_run_id);

COMMENT ON INDEX public_content_related_identity_run_idx IS
  'Serves the max(content_run_id) per identity LATERAL in the public occupation read path. '
  'The other indexes on this table lead with content_run_id and cannot answer it.';

COMMIT;
