"""Deterministic public occupation content derivation.

Pure functions. Given O*NET source facts and a promoted score snapshot, produce the fields a
public occupation page needs. No language model is involved and no factual sentence is
generated: the summary is the O*NET description verbatim, and the verdict is a versioned
template filled from persisted numbers.

Separation of concerns, which is the whole point of this module:

    source_*    O*NET facts. Copied, attributed, never reworded.
    jobsvsai_*  JobsVsAI interpretation. Template + persisted scores, fully reproducible.

If a fact is missing, the field stays NULL and the occupation is marked incomplete. It is
never filled with a plausible sentence.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

CONTENT_POLICY_VERSION = "phase6-public-content-v2"
VERDICT_TEMPLATE_VERSION = "phase6-verdict-template-v2"
# v2 adds the provisional-factor disclosure. The wording is fixed and versioned here so a
# page can never disclose something different from what the score actually contains.
PROVISIONAL_DISCLOSURE_VERSION = "phase6-provisional-disclosure-v1"

ONET_ATTRIBUTION = (
    "Occupation description from O*NET 30.3 by the U.S. Department of Labor, "
    "Employment and Training Administration. Used under CC BY 4.0."
)

# The 2018 SOC major groups. Source fact (the SOC structure), rendered with the label
# JobsVsAI uses on the site. This is a presentation choice over a published taxonomy, not a
# new taxonomy — the source group and title are stored alongside it.
SOC_MAJOR_GROUPS: dict[str, tuple[str, str]] = {
    "11": ("Management Occupations", "Management & Leadership"),
    "13": ("Business and Financial Operations Occupations", "Business & Finance"),
    "15": ("Computer and Mathematical Occupations", "Technology & Data"),
    "17": ("Architecture and Engineering Occupations", "Engineering & Architecture"),
    "19": ("Life, Physical, and Social Science Occupations", "Science & Research"),
    "21": ("Community and Social Service Occupations", "Community & Social Services"),
    "23": ("Legal Occupations", "Legal"),
    "25": ("Educational Instruction and Library Occupations", "Education & Training"),
    "27": ("Arts, Design, Entertainment, Sports, and Media Occupations", "Creative & Media"),
    "29": ("Healthcare Practitioners and Technical Occupations", "Healthcare"),
    "31": ("Healthcare Support Occupations", "Healthcare Support"),
    "33": ("Protective Service Occupations", "Protective Services"),
    "35": ("Food Preparation and Serving Related Occupations", "Food & Hospitality"),
    "37": ("Building and Grounds Cleaning and Maintenance Occupations", "Facilities & Grounds"),
    "39": ("Personal Care and Service Occupations", "Personal Care & Service"),
    "41": ("Sales and Related Occupations", "Sales"),
    "43": ("Office and Administrative Support Occupations", "Office & Administration"),
    "45": ("Farming, Fishing, and Forestry Occupations", "Agriculture & Environment"),
    "47": ("Construction and Extraction Occupations", "Construction & Extraction"),
    "49": ("Installation, Maintenance, and Repair Occupations", "Installation & Repair"),
    "51": ("Production Occupations", "Manufacturing & Production"),
    "53": ("Transportation and Material Moving Occupations", "Transport & Logistics"),
    "55": ("Military Specific Occupations", "Military"),
}

# Public score bands. Deliberately coarse: the underlying index is not precise enough to
# justify finer language, and a band is easier to defend than an adjective per point.
EXPOSURE_BANDS = (
    (75.0, "very high"), (60.0, "high"), (40.0, "moderate"), (0.0, "low"),
)
REPLACEMENT_BANDS = (
    (75.0, "very high"), (60.0, "high"), (40.0, "moderate"), (0.0, "low"),
)


# Disclosure (policy option A). Two of the six replacement-risk factors are provisional
# structural models. The public statement is that they are provisional and versioned — not
# that they are wrong, not that a quarter of the score is uncertain, and never a probability.
PROVISIONAL_FACTOR_LABELS = {
    "adoptionPressure": "AI adoption pressure",
    "labourMarketResilienceResistance": "labour-market resilience",
}
PROVISIONAL_PAGE_NOTE = (
    "Replacement Risk includes provisional estimates for AI adoption pressure and "
    "labour-market resilience. These inputs are versioned and monitored as the "
    "methodology improves."
)


def build_provisional_disclosure(
    provisional_factors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """The disclosure payload for one occupation, derived from its own factor rows.

    The combined share is computed from the persisted weights rather than hard-coded, so the
    sentence a page shows cannot drift from the arithmetic the score actually used.
    """
    if not provisional_factors:
        return None
    factors = sorted(
        (
            {
                "factorKey": item["factorKey"],
                "label": PROVISIONAL_FACTOR_LABELS.get(item["factorKey"], item["factorKey"]),
                "weight": round(float(item["weight"]), 4),
                "proxyModelVersion": item.get("proxyModelVersion"),
            }
            for item in provisional_factors
        ),
        key=lambda item: -item["weight"],
    )
    combined = round(sum(item["weight"] for item in factors), 4)
    named = " and ".join(item["label"] for item in factors)
    weight_clause = ", ".join(
        f"{item['label']} (weight {item['weight']:.2f})" for item in factors
    )
    return {
        "disclosureVersion": PROVISIONAL_DISCLOSURE_VERSION,
        "appliesTo": "replacementRisk",
        "combinedWeight": combined,
        "combinedWeightPercent": round(combined * 100, 2),
        "factors": factors,
        # Short form: the footnote next to Replacement Risk.
        "pageNote": PROVISIONAL_PAGE_NOTE,
        # Long form: the score methodology / details area.
        "detail": (
            f"Replacement Risk is a weighted index of six structural factors. Two of them — "
            f"{weight_clause} — are provisional models: {named} are estimated from structural "
            f"proxies rather than measured directly, and have not been through the same "
            f"validation as the other four factors. Together they carry "
            f"{combined * 100:.0f}% of the current Replacement Risk weighting. They are "
            f"versioned, their contribution to every occupation is published in the score "
            f"breakdown, and they will be revised as the methodology improves."
        ),
        "validated": False,
    }


def slugify(title: str) -> str:
    """Deterministic ASCII slug. Same title always yields the same slug."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower())
    return lowered.strip("-")


def band(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    for threshold, label in bands:
        if value >= threshold:
            return label
    return bands[-1][1]


def job_family(onet_soc_code: str) -> tuple[str, str, str]:
    """(major group, source SOC title, JobsVsAI family label). Raises on an unknown group."""
    major = onet_soc_code[:2]
    if major not in SOC_MAJOR_GROUPS:
        raise ValueError(f"Unknown SOC major group {major!r} for {onet_soc_code!r}")
    source_title, family = SOC_MAJOR_GROUPS[major]
    return major, source_title, family


def build_verdict(snapshot: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The public one-line verdict, and the exact inputs it was built from.

    Every clause is traceable to a persisted number. The sentence deliberately keeps
    exposure and replacement distinct, and names the constraint that separates them when one
    exists, because collapsing them is the single failure mode the product exists to avoid.
    """
    exposure = float(snapshot["aiExposure"])
    replacement = float(snapshot["replacementRisk"])
    exposure_band = band(exposure, EXPOSURE_BANDS)
    replacement_band = band(replacement, REPLACEMENT_BANDS)
    gap = exposure - replacement

    constraints = snapshot.get("structuralConstraints") or {}
    dominant_constraint = None
    if constraints:
        key, level = max(constraints.items(), key=lambda item: float(item[1]))
        if float(level) >= 60.0:
            dominant_constraint = (key, float(level))

    constraint_language = {
        "physical-presence": "the work has to happen in person",
        "environment-variability": "conditions vary too much to script",
        "accountability": "someone has to carry the responsibility",
        "consequence-severity": "mistakes are too costly to delegate",
        "human-dependency": "the work runs on human relationships",
        "regulation": "regulation limits how far automation can go",
    }

    sentence = (
        f"AI exposure is {exposure_band} and replacement risk is {replacement_band}."
    )
    if gap >= 10.0 and dominant_constraint:
        key, _ = dominant_constraint
        clause = constraint_language.get(key, "real-world constraints apply")
        sentence += (
            f" Current AI can take on a meaningful share of the tasks, but {clause}, "
            "so exposure is unlikely to translate fully into replacement."
        )
    elif gap >= 10.0:
        sentence += (
            " Current AI can take on a meaningful share of the tasks, though structural "
            "constraints slow how quickly that becomes displacement."
        )
    elif gap <= -10.0:
        sentence += (
            " Replacement pressure here comes less from raw AI capability than from how "
            "readily this work is reorganised around it."
        )
    else:
        sentence += " Exposure and replacement pressure move closely together for this occupation."

    inputs = {
        "aiExposure": exposure,
        "replacementRisk": replacement,
        "exposureBand": exposure_band,
        "replacementBand": replacement_band,
        "gap": round(gap, 4),
        "dominantConstraint": dominant_constraint[0] if dominant_constraint else None,
        "dominantConstraintLevel": dominant_constraint[1] if dominant_constraint else None,
        "templateVersion": VERDICT_TEMPLATE_VERSION,
    }
    return sentence, inputs


def build_content(
    identity: dict[str, Any],
    onet: dict[str, Any],
    snapshot: dict[str, Any] | None,
    alternate_titles: list[str],
    editorial_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One staged content candidate.

    `editorial_override` carries any existing JobsVsAI editorial title/slug, which always
    wins over the O*NET preferred title — an editorial decision already taken is not
    something a generator gets to revisit.
    """
    missing: list[str] = []

    if editorial_override and editorial_override.get("title"):
        canonical_title = editorial_override["title"]
        title_source = "jobsvsai_editorial"
    else:
        canonical_title = onet["title"]
        title_source = "onet_preferred"

    if editorial_override and editorial_override.get("slug"):
        seo_slug = editorial_override["slug"]
        slug_source = "existing_editorial"
    else:
        seo_slug = slugify(canonical_title)
        slug_source = "derived_from_canonical_title"
    if not seo_slug:
        raise ValueError(f"Could not derive a slug for {canonical_title!r}")

    major, source_group_title, family = job_family(onet["onetSocCode"])

    source_summary = (onet.get("description") or "").strip() or None
    if source_summary is None:
        missing.append("source_summary")

    verdict: str | None = None
    verdict_inputs: dict[str, Any] = {}
    verdict_snapshot_id: int | None = None
    if snapshot is None:
        missing.append("jobsvsai_verdict")
    else:
        verdict, verdict_inputs = build_verdict(snapshot)
        verdict_snapshot_id = snapshot["snapshotId"]
        # Disclosure travels with the verdict it qualifies, derived from this snapshot's own
        # factor rows. A promoted snapshot whose replacement risk contains provisional
        # factors must not produce a page that fails to say so.
        #
        # Absent key and empty list mean different things and are treated differently: an
        # absent key means the caller never loaded the factors, which is a wiring fault and
        # makes the content incomplete. An empty list means this snapshot genuinely has no
        # provisional factor, so there is nothing to disclose.
        if "provisionalFactors" not in snapshot:
            missing.append("provisional_disclosure")
        else:
            disclosure = build_provisional_disclosure(snapshot["provisionalFactors"] or [])
            if disclosure is not None:
                verdict_inputs["provisionalDisclosure"] = disclosure

    # Aliases power search. They are source titles, not invented synonyms.
    aliases = sorted({title.strip() for title in alternate_titles if title and title.strip()})

    return {
        "identityId": identity["identityId"],
        "onetSocCode": onet["onetSocCode"],
        "canonicalTitle": canonical_title,
        "titleSource": title_source,
        "seoSlug": seo_slug,
        "slugSource": slug_source,
        "socMajorGroup": major,
        "sourceSocMajorGroupTitle": source_group_title,
        "jobsvsaiJobFamily": family,
        "sourceSummary": source_summary,
        "sourceSummaryOrigin": "onet_occupation_description" if source_summary else None,
        "sourceAttribution": ONET_ATTRIBUTION,
        "jobsvsaiVerdict": verdict,
        "verdictSnapshotId": verdict_snapshot_id,
        "verdictInputs": verdict_inputs,
        "searchAliases": " ".join(aliases),
        "alternateTitleCount": len(aliases),
        "contentCompleteness": "complete" if not missing else "incomplete",
        "missingFields": missing,
        "contentPolicyVersion": CONTENT_POLICY_VERSION,
        "verdictTemplateVersion": VERDICT_TEMPLATE_VERSION,
    }
