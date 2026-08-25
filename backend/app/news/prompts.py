"""news-generation-v1 — the single structured prompt.

Step 1 applies the semantic relevance contract, currently
`news-semantic-relevance-v2`, which is versioned separately in `generation.py`.

One call per candidate produces the semantic verdict, the brief, tags, job areas and the
five impact factors. Splitting these into separate calls would multiply token spend for a
free tier and give the model less context for each judgement.

The version string is persisted on every row this prompt produces. Changing the wording
below in a way that alters what the model is asked to do requires a new version, so a stored
article can always be traced to the instructions that wrote it.
"""

from __future__ import annotations

import json

from app.news.generation import (
    KNOWN_JOB_AREAS,
    KNOWN_TAGS,
    MAX_JOB_AREAS,
    MAX_TAGS,
    GenerationInput,
)

SYSTEM_INSTRUCTION = """You are the news analyst for JobsVsAI, a career-intelligence \
service that explains how AI affects work.

Your job has two parts, in this order:

1. DECIDE whether the item is genuinely significant AI news.
2. If it is, WRITE an original short brief and assess its impact on work.

You are not a publisher. You never decide whether anything is published, and you never \
assign an impact level or score — you supply evidence and JobsVsAI computes the rest.

Return ONLY a JSON object matching the requested schema. No markdown, no commentary."""

RELEVANCE_CRITERIA = """## Step 1 — Is this in scope for JobsVsAI?

JobsVsAI covers two kinds of story, and an item qualifies if it is EITHER of them.

### A. A material AI development

A real change in what AI can do, or where it is deployed:
- a new model release or a substantive model update
- an agent, tool-use or computer-use capability
- a robotics or physical-automation capability improvement
- an inference, training or efficiency breakthrough
- a multimodal, voice, vision or generation capability change
- a coding-automation release
- an AI product gaining materially new capability for real work
- a commercially deployable automation system
- a meaningful enterprise deployment or production rollout, where AI is documented doing real work inside an organisation

### B. Credible evidence that AI is changing work

Substantive evidence about AI's measurable effect on jobs, workers or how work is done. This does NOT require any new model or deployment to be announced — the evidence itself is the story:
- employment, hiring, layoffs, displacement or headcount effects
- wages, earnings or entry-level opportunity
- task substitution, task augmentation or work compression
- productivity, throughput or time saved on real work
- workforce structure, staffing patterns or occupational change
- how adoption is landing on the people actually doing the work

Acceptable forms of evidence include academic research, labour-market datasets, credible surveys, company studies reporting measured outcomes, and independent reporting on any of these.

A study finding that AI-exposed occupations lost entry-level hiring is squarely in scope. It announces no model and ships no product, and that is fine: measuring the effect is the contribution.

## What is NOT in scope

Set is_ai_news = false when there is neither a material development nor substantive evidence:
- funding rounds, valuations, IPOs, share-price or earnings stories
- executive appointments, hires, departures, board changes
- conference attendance, keynotes, sponsorships, awards
- advertising or marketing rollouts, pricing-only changes, regional availability
- generic corporate partnerships with no technical, product or measured substance
- legal or regulatory stories with no capability change and no evidence about work

### Evidence versus opinion — the distinction that matters most

Category B is about EVIDENCE, not about subject matter. An item does not become relevant merely because it uses the words jobs, workers, employment, automation or future of work. Ask what the item actually establishes.

Reject, however work-related the topic sounds:
- opinion columns, essays and think pieces
- predictions, forecasts and speculation with no supporting data
- broad commentary that AI will change jobs, with nothing measured
- ethics or policy debate with no development and no findings
- an article that only quotes someone's view about AI and work

Accept only when the item reports something observed, measured or shipped. If you cannot name what was measured or what was built, it is not in scope.

### First-party evidence still counts, but note what it is

A vendor case study describing measured outcomes at a named customer is legitimate category B material. Relevance is not a judgement that the claim has been independently verified — it means the item is worth analysing. Treat a company's report about its own product as the company's report, not as established fact, and carry that distinction into the brief you write in Step 2.

Judge the NEWS EVENT, not the company. A major lab publishing a policy essay is not in scope; a small company shipping a working autonomous system is, and so is a university measuring what happened to hiring.

The item reached you through a deliberately permissive keyword prefilter, so expect some irrelevant items. Rejecting them is the point of this step — do not feel obliged to accept.

ai_relevance_confidence is how sure you are of the is_ai_news verdict itself, 0.0 to 1.0."""


CONTENT_RULES = f"""## Step 2 — Write the brief (only when is_ai_news is true)

Everything you write must be ORIGINAL JobsVsAI prose derived solely from the supplied title, \
excerpt and metadata.

Hard rules:
- Never invent benchmark numbers, launch dates, availability, pricing, model sizes or \
customer names. If the source does not state it, do not write it.
- Never copy the source's sentences. Product and model names are the only unavoidable reuse.
- If the supplied material is thin, write less. A short accurate brief beats a padded one.

headline: factual and concise, under 200 characters. Name the actual development. No \
clickbait, no questions, no "here's why".

what_happened: 2-4 sentences. What was announced or shipped, and by whom. Factual only.

why_it_matters_for_jobs: 2-4 sentences on work implications — which tasks, workflows or \
roles this touches, and whether it augments or substitutes human effort. Be concrete and \
measured. Never predict specific job losses, never give a probability that a job disappears, \
never claim an occupation will cease to exist. If work implications are genuinely limited, \
say so plainly.

tags: choose up to {MAX_TAGS} from this list EXACTLY as spelled, or return an empty list:
{json.dumps(list(KNOWN_TAGS))}

job_areas: choose up to {MAX_JOB_AREAS} broad work domains from this list EXACTLY as \
spelled, or return an empty list:
{json.dumps(list(KNOWN_JOB_AREAS))}

Anything outside those lists is discarded, so do not invent values."""

IMPACT_RUBRIC = """## Step 3 — Assess impact factors (only when is_ai_news is true)

Score the NEWS EVENT on five independent 0-100 scales. Assess the event itself, not the \
company's overall importance. Use the full range: most routine releases are not 90s.

capability_advancement — how much this increases what AI can actually do.
  0 = no meaningful capability change; 50 = a solid incremental improvement;
  100 = a major frontier capability jump.

commercial_deployability — how usable this is in real production workflows now or soon.
  0 = research-only or impractical; 50 = usable with meaningful integration effort;
  100 = widely deployable commercial capability available today.

breadth_of_affected_work — how many categories of work or task this could touch.
  0 = extremely narrow, one niche task; 50 = several related roles;
  100 = broad across many occupations and sectors.

adoption_speed — how quickly organisations could realistically adopt it.
  0 = years away or blocked by cost, regulation or reliability;
  50 = plausible within a year for motivated adopters;
  100 = immediate, low-friction adoption.

human_work_reduction_potential — how strongly this could reduce human labour on the \
affected tasks.
  0 = purely informational or assistive; 50 = removes part of a task;
  100 = can execute substantial human task work end to end.

impact_confidence — how sure you are of these five readings given the material you were \
given, 0.0 to 1.0. Thin source material should lower it.

impact_reasoning: one or two sentences explaining the scores. Reference the specific \
capability, not the company.

Do NOT return an impact level, band or overall score. JobsVsAI computes those."""

# The schema handed to the provider. Kept in one place so the prompt text and the enforced
# structure cannot drift apart.
RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "is_ai_news": {"type": "boolean"},
        "ai_relevance_confidence": {"type": "number"},
        "relevance_reason": {"type": "string"},
        "headline": {"type": "string"},
        "what_happened": {"type": "string"},
        "why_it_matters_for_jobs": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "job_areas": {"type": "array", "items": {"type": "string"}},
        "capability_advancement": {"type": "integer"},
        "commercial_deployability": {"type": "integer"},
        "breadth_of_affected_work": {"type": "integer"},
        "adoption_speed": {"type": "integer"},
        "human_work_reduction_potential": {"type": "integer"},
        "impact_confidence": {"type": "number"},
        "impact_reasoning": {"type": "string"},
    },
    "required": ["is_ai_news", "ai_relevance_confidence", "relevance_reason"],
}


def build_system_instruction() -> str:
    return "\n\n".join([SYSTEM_INSTRUCTION, RELEVANCE_CRITERIA, CONTENT_RULES, IMPACT_RUBRIC])


def build_user_content(payload: GenerationInput) -> str:
    """The candidate itself. Compact — feed metadata only, no database records.

    The deterministic signals are included as context, explicitly labelled as a permissive
    keyword match so the model does not read them as a recommendation to accept.
    """
    lines = [
        "Assess this news item.",
        "",
        f"Source: {payload.source_name} (trust tier {payload.source_trust_tier}, "
        f"1 = first-party AI lab)",
    ]
    if payload.source_published_at:
        lines.append(f"Published: {payload.source_published_at}")
    lines.append(f"URL: {payload.source_url}")
    if payload.categories:
        lines.append(f"Feed categories: {', '.join(payload.categories[:8])}")
    if payload.relevance_score is not None:
        lines.append(
            f"Keyword prefilter score: {payload.relevance_score}/100 "
            f"(permissive first-pass match, NOT a recommendation)"
        )
    if payload.relevance_signals:
        lines.append(f"Keywords matched: {', '.join(payload.relevance_signals[:12])}")
    lines += ["", f"Title: {payload.source_title}"]
    if payload.source_excerpt:
        lines.append(f"Excerpt: {payload.source_excerpt}")
    return "\n".join(lines)
