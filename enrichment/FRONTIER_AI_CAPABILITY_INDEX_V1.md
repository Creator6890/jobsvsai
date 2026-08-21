# JobsVsAI Frontier AI Capability Index v1

## Status

`frontier-ai-index-v1` is a draft, versioned evidence layer for estimating AI capability across the 15 JobsVsAI capability dimensions. It is separate from task requirement mappings, O*NET source data, legacy task AI scores, and occupation scores.

The 2026-Q3 commercially deployable track contains 15 provisional JobsVsAI assessment values dated 2026-08-20. The technical-frontier track is defined separately and intentionally contains no values because an approved technical-frontier value set has not been supplied. Neither track is an occupation-scoring input.

## Version and value model

An index version records the capability taxonomy version, methodology version, 0–100 scale, expected capability count, source, provenance, and supersession history. Versioned assessment tracks distinguish:

- `commercially_deployable`: products and APIs that can be deployed under practical availability, reliability, integration and safety constraints;
- `technical_frontier`: best demonstrated technical capability, including research previews and specialist systems.

When values are later approved, each capability entry can store:

- capability score and confidence;
- source type;
- provider, model, and model version;
- observation date;
- benchmark evidence;
- rationale, source, author, and provenance.

Independent evidence records store source tier and type, provider/model where applicable, benchmark name, reported result, source reference, date, structured payload, confidence, rationale, and provenance. The reported benchmark result is retained verbatim as a source signal; it is not numerically converted into the JobsVsAI 0–100 assessment.

A populated track must contain all 15 dimensions from the same taxonomy version, and every value must reconcile to at least one evidence record. Draft tracks may remain empty. The current commercial track is complete but provisional; the technical-frontier track is empty and draft.

## 2026-Q3 commercial assessment

The initial commercially deployable scores are the approved JobsVsAI values supplied for this assessment cycle. Confidence expresses evidence coverage and deployment uncertainty, not model self-confidence. Rationales distinguish broad commercial availability from narrow or preview-stage demonstrations, especially for social and embodied capabilities.

Primary evidence includes OpenAI GPT-5.5 and GPT-5.6 evaluations, Google DeepMind Gemini model cards and robotics results, and the primary PieArena negotiation paper. Each database evidence record retains the benchmark result, publisher/model provenance and direct source reference.
