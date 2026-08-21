# O*NET ingestion design

## Boundary and release

The ingestion boundary targets the official O*NET 30.3 CSV release (May 2026) under CC BY 4.0. It is intentionally isolated from JobsVsAI production scoring. Importing O*NET data does **not** write `ai_capabilities`, `task_ai_scores`, `occupation_scores`, `score_derivations`, or `scoring_jobs`.

The representative validation scope is defined in `subsets/representative_31.txt`. Imported occupations remain in the `onet_*` canonical layer until an explicit promotion design is approved.

## Dataset mapping

| O*NET dataset | Canonical import target | JobsVsAI production bridge | Promotion status |
|---|---|---|---|
| Occupation Data | `onet_occupations` | Optional `jobs_vs_ai_occupation_id` → `occupations.id`; nine Phase 1 occupations are linked without overwriting them | Staged only |
| Job Titles | Compatibility copy in `onet_alternate_titles`; normalized preferred/alternate/short rows in `source_occupation_titles` | Future production search integration; `occupations.search_aliases` is not mutated | Staged only |
| Task Statements | `onet_tasks` | Future merge into `tasks` and `occupation_tasks` | Deferred |
| Task Ratings | `onet_task_ratings`; normalized IM and expected FT summaries plus explicit completeness state on `onet_tasks` | Incomplete tasks are excluded from future weighting under `onet-task-rating-v1`; production promotion remains deferred | Staged only |
| Essential Skills | `onet_elements` (`element_type='skill'`) and `onet_element_ratings` | Future merge into `skills` and `occupation_skills` | Deferred |
| Transferable Skills | Same skill tables, distinguished in `source_metadata.element_group` | Same production bridge | Deferred |
| Abilities | `onet_elements` (`ability`) and `onet_element_ratings` | No Phase 1 production table exists | New canonical layer |
| Work Activities | `onet_elements` (`work_activity`) and `onet_element_ratings` | No Phase 1 production table exists | New canonical layer |
| Work Context | `onet_elements` (`work_context`), `onet_element_ratings`, and `onet_work_context_categories` | No Phase 1 production table exists | New canonical layer |
| Related Occupations | `onet_related_occupations` with fixed `relation_namespace='onet_relatedness'` | Must not be copied directly to future skill-similarity or career-transition models | Staged only |
| Content Model Reference | Definitions in `onet_elements` | Supplies stable element identifiers and descriptions | Imported |
| Scales Reference | `onet_scales`; all task/element ratings retain raw value, normalized value, scale, N, standard error, CI, suppression, relevance, date, and domain metadata | No production score use | Staged only |
| O*NET-SOC crosswalk | `source_occupation_successions` between versioned 2010 and 2019 taxonomy nodes | No automatic reassignment; split/merge/complex mappings have no invented allocation weights | Staged only |
| SOC 2018 major groups | `source_taxonomies`, `source_taxonomy_nodes`, and `source_occupation_taxonomy_memberships` | Kept separate from JobsVsAI `occupation_categories` | Staged only |

## Provenance and versioning

Every input row is copied to append-only `source_record_versions` with:

- owning source release, dataset-specific version, and dataset name;
- dataset-specific natural key;
- exact source URI;
- canonical SHA-256 row hash;
- unmodified JSON payload;
- first/last seen import runs and timestamps;
- current/superseded state.

Every canonical source row points back to the exact source-record version, source release, and import run that produced it. A changed row creates a new raw version; unchanged replays only update `last_seen_*` and write no new version.

## Taxonomy ownership

`occupation_categories` remains the JobsVsAI editorial taxonomy and is included in the importer's immutable production fingerprint. O*NET-SOC 2010, O*NET-SOC 2019, and SOC 2018 are source taxonomies with their own versioned nodes and memberships. The importer never derives an editorial category from a SOC group.

## Missing task-rating policy

Policy `onet-task-rating-v1` is deliberately conservative:

- importance and frequency remain `NULL` when the source does not provide usable ratings;
- no mean, zero, midpoint, cross-occupation, or model-based value is substituted;
- `weighting_eligible` is true only when both summaries exist;
- `rating_status` and `missing_rating_fields` explain the exclusion;
- occupation/domain coverage is marked `partial` and exposed in admin.

`import_runs.manifest` stores the selected O*NET-SOC codes and SHA-256 hashes of all downloaded source files. The run key is derived from the importer version, release, subset codes, and file hashes.

## Idempotency and update safety

- PostgreSQL advisory locking prevents two imports of the same release from running concurrently.
- Canonical writes use natural-key upserts.
- Collection rows are marked inactive within the imported scope before current rows are reasserted, so source deletions do not leave stale active data.
- Raw history is append-only and supports source-row reversion.
- The importer runs canonical changes in one transaction and marks failed runs without retaining partial entities.
- Replaying either the representative subset or the complete 30.3 release produces zero new source versions.
- A fingerprint before and after the transaction guards production scores, occupations, editorial categories, and career relationships.

## Promotion and identity policy

Private ingestion, scoring readiness, and public activation are independent fields in `occupation_promotion_profiles`. The lifecycle is:

`source_imported → normalized → identity_resolved → scoring_ready → scored → editorially_approved → public`

- unchanged, renamed, and one-to-one recoded mappings preserve continuity;
- merge successors receive a new private canonical identity and do not inherit historical scores;
- split successors receive distinct identities and no mathematical historical allocation;
- complex mappings remain `normalized` with a pending manual identity review;
- all allocation weights remain `NULL` unless an official future source provides one.

Source titles remain complete and immutable. `occupation_publications` supplies one staged English/US public title, while `occupation_search_aliases` controls which aliases may eventually be indexed. `occupation_localizations` reserves country/locale-specific public metadata without creating India localizations during this phase.

O*NET Essential and Transferable classifications are retained on each skill rating as immutable source semantics. No JobsVsAI transition-enabling/core/missing-skill interpretation is created by this importer.

O*NET CC BY 4.0 attribution requirements are stored in `source_attribution_requirements`. Attribution is required before public activation, not before private ingestion.

## Full ingestion status

The complete private O*NET 30.3 release was imported after the representative policy gate passed. Every source occupation remains non-public. AI capability mapping and production score recalculation are separate future phases and were not started.

AI capability mappings and production score recalculation are separate future gates and are explicitly out of scope for this importer.
