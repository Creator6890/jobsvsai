# O*NET 30.3 complete private ingestion report

## Import result

| Measure | Result |
|---|---:|
| O*NET occupations | 1,016 |
| Source records processed | 785,599 |
| New source versions on initial full run | 757,816 |
| New source versions on exact full replay | 0 |
| Tasks / task ratings | 18,796 / 161,559 |
| Generalized element ratings | 526,540 |
| Source titles | 62,801 |
| Related-occupation links | 18,460 |
| Succession mappings | 1,164 |
| Invented allocation weights | 0 |
| Public-ready / public source occupations | 0 / 0 |

Production scores, production occupations, editorial categories, and existing career relationships retained the same fingerprints. No scoring job, AI capability mapping, or public source activation was created.

## Promotion matrix

| State/gate | Occupations |
|---|---:|
| Source imported | 1,016 |
| Normalized | 1,016 |
| Identity resolved | 988 |
| Scoring ready | 878 |
| Insufficient for scoring | 138 |
| Identity review required | 28 |
| Partial source data | 179 |
| Public ready | 0 |
| Public | 0 |

Lifecycle states currently contain 878 `scoring_ready`, 110 `identity_resolved`, and 28 `normalized` occupations. The normalized occupations are held for complex identity review.

## Coverage matrix

| Incomplete domain | Status | Occupations |
|---|---|---:|
| Tasks | Missing | 93 |
| Task ratings | Partial | 86 |
| Skills | Missing | 122 |
| Abilities | Missing | 122 |
| Work activities | Missing | 122 |
| Work context | Missing | 122 |

These counts overlap by occupation. There are 179 distinct occupations with at least one incomplete domain and 667 occupation/domain gap rows. Missing values remain absent and are never fabricated.

## Identity, titles, and source semantics

- Identity resolutions: 723 unchanged, 49 renamed, 85 recoded, 209 merge-new-identity, 58 split-new-identity, 40 complex-manual mappings, and 4 new-source identities.
- Complex mappings remain pending and cannot resolve automatically.
- Titles: 1,016 preferred, 57,543 alternate, 3,987 short, and 255 historical.
- Publication staging: 865 source titles accepted as the default staged title, 142 require editorial title review, and nine retain an existing JobsVsAI editorial title. None are activated.
- Skill ratings preserve 17,880 Essential and 44,700 Transferable classifications. No JobsVsAI transition semantics were inferred.
- O*NET attribution/license metadata is stored as a mandatory pre-publication gate.

## Remaining promotion work

1. Manually resolve the 28 complex successor identities before they can advance.
2. Review the 142 public-title candidates flagged as taxonomic, US-specific, or unclear.
3. Decide whether the source-coverage scoring threshold needs domain-specific refinements before AI capability mapping.
4. Build and validate the separate JobsVsAI AI Capability Taxonomy before any task exposure mapping or score recalculation.

The O*NET ingestion phase is complete. Work should now stop on source ingestion until the AI capability taxonomy phase is explicitly started.
