# O*NET 30.3 representative schema-expansion audit

## Result

- Scope: 31 occupations across 19 SOC major groups.
- Expanded run: 27,783 source rows read; 60 new versions (41 crosswalk rows and 19 SOC major groups).
- Exact replay: 27,783 rows read, **0** new source versions.
- Production score and JobsVsAI editorial-taxonomy fingerprints: unchanged.
- Public occupations activated: 0.
- AI capability mappings and scoring jobs created: 0.
- Structural relationship checks: pass.

## Expanded canonical coverage

| Entity/relationship | Current rows |
|---|---:|
| O*NET occupations | 31 |
| Normalized source titles | 2,502 |
| Preferred / alternate / short titles | 31 / 2,186 / 285 |
| Rating scales | 32 |
| Tasks | 720 |
| Task ratings | 6,129 |
| Weighting-eligible / excluded tasks | 681 / 39 |
| Skill elements / ratings | 35 / 2,100 |
| Ability elements / ratings | 52 / 3,120 |
| Work-activity elements / ratings | 41 / 2,460 |
| Work-context elements / ratings | 57 / 9,859 |
| O*NET related-occupation links | 620 |
| Source taxonomies / nodes / memberships | 3 / 91 / 62 |
| O*NET-SOC 2010→2019 succession mappings | 41 |

Succession classifications are 22 unchanged, 1 renamed, 2 recoded, 12 merge, and 4 complex. Every allocation weight is `NULL`; the importer does not invent how a predecessor should be distributed across successors.

## Integrity and policy validation

- Orphan task ratings, element ratings, task scales, and element scales: 0.
- Succession rows with invented weights: 0.
- Related rows outside the `onet_relatedness` namespace: 0.
- Tasks with missing source ratings marked weighting-eligible: 0.
- Tasks missing both importance and frequency: 39, retained as `NULL` and explicitly excluded by `onet-task-rating-v1`.
- Admin incomplete-domain rows: 8.
- Exact replay new source versions: 0.

## Promotion matrix

| State/gate | Occupations |
|---|---:|
| Source imported / normalized | 31 / 31 |
| Identity resolved | 29 |
| Scoring ready | 29 |
| Insufficient for scoring | 2 |
| Identity review required | 2 |
| Partial source data | 4 |
| Public ready / public | 0 / 0 |

The representative policy gate passed. Complex mappings remain pending; source gaps are retained without imputation. This result authorized the separate complete private import.

## Representative promotion holds

1. `15-1255.00 Web and Digital Interface Designers` has 30 task statements but no task-rating rows and no skill, ability, work-activity, or work-context rows in the selected O*NET 30.3 files. Its current JobsVsAI UX Researcher bridge requires manual semantic review.
2. `13-2011.00`, `27-2012.00`, and `49-3023.00` have partial task-rating coverage. The exclusion policy is safe, but product promotion needs a reviewed completeness threshold.
3. Complex SOC succession requires manual review; merge and split rules create new/distinct identities without historical score allocation.
4. Source titles are normalized and staged, but no source occupation is public-ready until editorial promotion.
5. Essential versus Transferable Skills remain immutable source semantics; product relevance remains a future derived layer.
6. O*NET relatedness remains intentionally separate from future JobsVsAI skill similarity and career-transition relationships; those derived models do not yet exist.
7. O*NET attribution metadata is stored, but its public presentation remains a public-activation gate.

The complete private import subsequently ran. Public activation, AI capability mapping, and score recalculation were not started.
