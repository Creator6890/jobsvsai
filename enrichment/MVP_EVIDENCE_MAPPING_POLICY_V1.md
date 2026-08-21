# JobsVsAI MVP Evidence-Based Mapping Policy v1

## Purpose

`mvp-evidence-policy-v1` replaces mandatory human-gold coverage as the acceptance mechanism for provisional MVP task mappings. The research-grade gold review, adjudication, mapper evaluation, and acceptance-gate infrastructure remains intact, but it does not block provisional MVP scoring eligibility.

The policy is active. No mapping is activated merely because the policy is active. Eligibility is decided independently for each immutable AI-generated mapping and remains separate from public activation and occupation-score calculation.

## Required provenance

Every AI mapping run records:

- capability taxonomy and rubric versions;
- evidence-policy version;
- provider, model name, model version, and optional model snapshot date;
- prompt name, version, SHA-256 hash, and optional system-prompt hash;
- inference configuration;
- allowed-input manifest and prohibited-input attestation;
- run evidence, source, author, and creation provenance.

Every task mapping records the task-statement hash, mapping version, confidence, ambiguity state, initial validation and review states, rationale, evidence, and optional supersession link. Capability requirements and environment constraints retain their own confidence, rationale, evidence, and provenance.

## MVP eligibility gates

A task mapping is provisionally scoring-eligible only when deterministic validation confirms all of the following:

- the policy is active;
- taxonomy, rubric, and policy versions reconcile;
- the stored task hash matches the current O*NET statement;
- one to six capability dimensions are present;
- capability weights normalize to 1 within the rubric tolerance;
- all weights and requirement/constraint levels meet rubric minimums;
- mapping confidence is at least 70;
- every dimension confidence is at least 60;
- 100% of mapped dimensions have task-local evidence and rationale;
- ambiguity state is `none`—ambiguous or insufficient descriptions are ineligible;
- provider/model and prompt/version/hash provenance is complete;
- prohibited score and outcome inputs are attested absent.

Successful validation emits an append-only `ai_validated` status event with `scoring_eligible=true`. Failed validation records every failed gate and never silently falls back. Human review is allowed and preserved but is not mandatory for this provisional state.

## Separation from research validation

`mapper-acceptance-gates-v1`, the 175-task review frame, human review events, adjudication, and aggregate gold metrics remain unchanged for future research-grade validation. They assess mapper quality at dataset level; `mvp-evidence-policy-v1` determines provisional eligibility at individual-task level.

## Structured import

`import_ai_task_mappings.py` accepts versioned JSON payloads, stores structured AI mappings, and runs deterministic validation in the same transaction. It writes only the provisional enrichment tables. It never writes active task mappings, Frontier Index values, task AI scores, or occupation scores.

No AI-generated mapping is seeded by the policy migration.
