"""Unit tests for deterministic public occupation content.

The rule under test is the one that matters most: O*NET facts are copied, JobsVsAI
interpretation is generated from persisted numbers, and a missing fact stays missing.
"""

import pytest

from ingestion.public_content_policy import (
    CONTENT_POLICY_VERSION,
    ONET_ATTRIBUTION,
    VERDICT_TEMPLATE_VERSION,
    build_content,
    build_verdict,
    job_family,
    slugify,
)

IDENTITY = {"identityId": 11}
ONET = {
    "onetSocCode": "29-1141.00",
    "title": "Registered Nurses",
    "description": "Assess patient health problems and needs, develop and implement nursing care plans.",
}
SNAPSHOT = {
    "snapshotId": 501,
    "aiExposure": 58.0,
    "replacementRisk": 34.0,
    "structuralConstraints": {
        "physical-presence": 91.0, "human-dependency": 78.0,
        "accountability": 84.0, "regulation": 70.0,
    },
    # The two provisional replacement-risk factors, as a promoted snapshot carries them.
    "provisionalFactors": [
        {"factorKey": "adoptionPressure", "weight": 0.15,
         "proxyModelVersion": "phase4b-occupation-proxy-v1"},
        {"factorKey": "labourMarketResilienceResistance", "weight": 0.10,
         "proxyModelVersion": "phase4b-occupation-proxy-v1"},
    ],
}


def test_slug_is_deterministic_and_ascii() -> None:
    assert slugify("Registered Nurses") == "registered-nurses"
    assert slugify("Émergency Medical Technicians & Paramedics") == "emergency-medical-technicians-paramedics"
    assert slugify("First-Line Supervisors") == slugify("First-Line Supervisors")


def test_job_family_maps_the_soc_major_group_and_keeps_the_source_title() -> None:
    major, source_title, family = job_family("29-1141.00")
    assert major == "29"
    assert source_title == "Healthcare Practitioners and Technical Occupations"
    assert family == "Healthcare"

    with pytest.raises(ValueError, match="Unknown SOC major group"):
        job_family("99-9999.00")


def test_summary_is_the_onet_description_verbatim_and_attributed() -> None:
    content = build_content(IDENTITY, ONET, SNAPSHOT, alternate_titles=[])
    assert content["sourceSummary"] == ONET["description"]
    assert content["sourceSummaryOrigin"] == "onet_occupation_description"
    assert content["sourceAttribution"] == ONET_ATTRIBUTION


def test_missing_description_is_left_missing_not_invented() -> None:
    content = build_content(IDENTITY, {**ONET, "description": "  "}, SNAPSHOT, alternate_titles=[])
    assert content["sourceSummary"] is None
    assert content["sourceSummaryOrigin"] is None
    assert content["missingFields"] == ["source_summary"]
    assert content["contentCompleteness"] == "incomplete"


def test_missing_snapshot_leaves_the_verdict_missing() -> None:
    content = build_content(IDENTITY, ONET, None, alternate_titles=[])
    assert content["jobsvsaiVerdict"] is None
    assert content["verdictSnapshotId"] is None
    assert "jobsvsai_verdict" in content["missingFields"]
    assert content["contentCompleteness"] == "incomplete"


def test_verdict_keeps_exposure_and_replacement_distinct_and_names_the_constraint() -> None:
    sentence, inputs = build_verdict(SNAPSHOT)
    assert "exposure is moderate" in sentence
    assert "replacement risk is low" in sentence
    assert "in person" in sentence, "the dominant constraint should be named"
    assert inputs["dominantConstraint"] == "physical-presence"
    assert inputs["gap"] == 24.0
    assert inputs["templateVersion"] == VERDICT_TEMPLATE_VERSION


def test_verdict_handles_the_inverse_case_without_claiming_a_constraint() -> None:
    sentence, inputs = build_verdict({
        "snapshotId": 1, "aiExposure": 40.0, "replacementRisk": 62.0, "structuralConstraints": {},
    })
    assert "reorganised" in sentence
    assert inputs["dominantConstraint"] is None


def test_verdict_is_reproducible_from_the_same_snapshot() -> None:
    assert build_verdict(SNAPSHOT) == build_verdict(SNAPSHOT)


def test_editorial_title_and_slug_win_over_onet() -> None:
    content = build_content(
        IDENTITY, ONET, SNAPSHOT, alternate_titles=[],
        editorial_override={"title": "Nurses", "slug": "nurses"},
    )
    assert content["canonicalTitle"] == "Nurses"
    assert content["titleSource"] == "jobsvsai_editorial"
    assert content["seoSlug"] == "nurses"
    assert content["slugSource"] == "existing_editorial"


def test_aliases_come_from_source_titles_and_are_deduplicated() -> None:
    content = build_content(
        IDENTITY, ONET, SNAPSHOT,
        alternate_titles=["Staff Nurse", "RN", "Staff Nurse", "  ", "Charge Nurse"],
    )
    assert content["alternateTitleCount"] == 3
    assert content["searchAliases"] == "Charge Nurse RN Staff Nurse"


def test_provisional_factors_are_disclosed_with_their_real_combined_weight() -> None:
    """The disclosure is computed from the snapshot's own weights, never hard-coded."""
    content = build_content(IDENTITY, ONET, SNAPSHOT, alternate_titles=["RN"])
    disclosure = content["verdictInputs"]["provisionalDisclosure"]
    assert disclosure["appliesTo"] == "replacementRisk"
    assert disclosure["combinedWeight"] == 0.25
    assert disclosure["combinedWeightPercent"] == 25.0
    assert disclosure["validated"] is False
    assert [item["factorKey"] for item in disclosure["factors"]] == [
        "adoptionPressure", "labourMarketResilienceResistance"]
    assert all(item["proxyModelVersion"] for item in disclosure["factors"])
    # No probability language, and no claim that a quarter of the score is wrong.
    assert "probability" not in disclosure["detail"].lower()
    assert "25%" in disclosure["detail"]
    assert "provisional" in disclosure["pageNote"].lower()


def test_snapshot_without_loaded_provisional_factors_is_incomplete() -> None:
    """An absent key is a wiring fault, not a snapshot with nothing to disclose."""
    snapshot = {key: value for key, value in SNAPSHOT.items() if key != "provisionalFactors"}
    content = build_content(IDENTITY, ONET, snapshot, alternate_titles=["RN"])
    assert content["contentCompleteness"] == "incomplete"
    assert "provisional_disclosure" in content["missingFields"]


def test_snapshot_with_no_provisional_factors_needs_no_disclosure() -> None:
    content = build_content(
        IDENTITY, ONET, {**SNAPSHOT, "provisionalFactors": []}, alternate_titles=["RN"])
    assert content["contentCompleteness"] == "complete"
    assert "provisionalDisclosure" not in content["verdictInputs"]


def test_complete_content_declares_its_versions() -> None:
    content = build_content(IDENTITY, ONET, SNAPSHOT, alternate_titles=["RN"])
    assert content["contentCompleteness"] == "complete"
    assert content["missingFields"] == []
    assert content["contentPolicyVersion"] == CONTENT_POLICY_VERSION
    assert content["verdictSnapshotId"] == 501
