"""Unit tests for the launch-quality triage policy.

The policy is pure, so it is tested against synthetic candidate rows in the persisted
`phase5_occupation_scores` shape. This verifies the classification logic without needing the
real corpus — which matters, because the corpus lives on the operator's machine and the
policy must be trustworthy before it is pointed at 744 real occupations.
"""

from scoring.phase6_launch_triage import (
    GATES,
    SEVERITY_POLICY,
    TRIAGE_POLICY_VERSION,
    soc_family_discontinuities,
    triage_corpus,
    triage_occupation,
)


def candidate(**overrides) -> dict:
    """A clean, launch-eligible candidate. Tests degrade one thing at a time."""
    row = {
        "candidateOccupationId": 1,
        "occupationCode": "13-2011.00",
        "title": "Accountants and Auditors",
        "candidateStatus": "review_ready",
        "coverageGateStatus": "passed",
        "confidenceGateStatus": "passed",
        "aiExposure": 62.0,
        "replacementRisk": 55.0,
        "confidence": 80.0,
        "weightedTaskCoverage": 88.0,
        "reconciliation": {"passed": True},
        "provisionalSensitivity": {
            "maximumAbsoluteScoreImpact": 1.2,
            "provisionalVersions": {"adoptionPressure": "phase4b-occupation-proxy-v1"},
        },
        "factorContributions": [
            {"factor": "taskAutomationExposure", "value": 60.0, "weight": 0.35, "weightedContribution": 21.0},
            {"factor": "aiCapabilityProximity", "value": 70.0, "weight": 0.10, "weightedContribution": 7.0},
            {"factor": "humanDependencyResistance", "value": 40.0, "weight": 0.15, "weightedContribution": 6.0},
            {"factor": "physicalDependencyResistance", "value": 60.0, "weight": 0.15, "weightedContribution": 9.0},
            {"factor": "adoptionPressure", "value": 50.0, "weight": 0.15, "weightedContribution": 7.5},
            {"factor": "labourMarketResilienceResistance", "value": 45.0, "weight": 0.10, "weightedContribution": 4.5},
        ],
        "taskContributions": [
            {"onetTaskId": index, "statement": f"Task {index}", "aiExposureContribution": 62.0 / 8}
            for index in range(1, 9)
        ],
        "structuralProxyInputs": {
            "values": {
                "physical-presence": 25.0, "environment-variability": 30.0,
                "accountability": 55.0, "consequence-severity": 40.0,
                "human-dependency": 45.0, "regulation": 50.0,
                "adoption-pressure": 55.0, "labour-market-resilience": 50.0,
            },
            "missingDataPolicy": {"missingFamilies": []},
        },
    }
    row.update(overrides)
    return row


def codes(findings) -> set[str]:
    return {item["code"] for item in findings}


def test_every_policy_code_declares_a_severity_and_justification() -> None:
    for code, (severity, justification) in SEVERITY_POLICY.items():
        assert severity in {"critical", "high", "medium", "low"}, code
        assert justification.strip(), code


def test_clean_candidate_is_launch_eligible_and_only_carries_the_universal_disclosure() -> None:
    findings = triage_occupation(candidate())
    assert codes(findings) == {"provisional_models_in_use"}
    assert findings[0]["severity"] == "low"


def test_coverage_and_confidence_minimums_are_enforced_not_preferred() -> None:
    """The Phase 5 thresholds existed but only sorted. Here they exclude."""
    low_coverage = triage_occupation(candidate(weightedTaskCoverage=74.0))
    low_confidence = triage_occupation(candidate(confidence=70.0))

    assert "weighted_coverage_below_launch_minimum" in codes(low_coverage)
    assert "confidence_below_launch_minimum" in codes(low_confidence)
    for findings in (low_coverage, low_confidence):
        assert any(item["severity"] == "high" for item in findings)


def test_provisional_sensitivity_excludes_only_when_the_score_actually_moves() -> None:
    insensitive = triage_occupation(candidate(
        provisionalSensitivity={"maximumAbsoluteScoreImpact": 2.9}))
    sensitive = triage_occupation(candidate(
        provisionalSensitivity={"maximumAbsoluteScoreImpact": 3.0}))

    assert "provisional_input_sensitivity" not in codes(insensitive)
    assert "provisional_input_sensitivity" in codes(sensitive)
    # The universal disclosure is never an exclusion on its own.
    assert SEVERITY_POLICY["provisional_models_in_use"][0] == "low"


def test_high_replacement_despite_severe_constraints_is_critical() -> None:
    """The surgeon case: capable AI, but physical presence and duty of care dominate."""
    row = candidate(
        replacementRisk=78.0,
        structuralProxyInputs={"values": {
            "physical-presence": 92.0, "environment-variability": 70.0,
            "accountability": 88.0, "consequence-severity": 95.0,
            "human-dependency": 80.0, "regulation": 85.0}},
    )
    findings = triage_occupation(row)
    finding = next(item for item in findings if item["code"] == "high_replacement_despite_severe_constraints")
    assert finding["severity"] == "critical"
    assert set(finding["observed"]["severeConstraints"]) >= {"physical-presence", "consequence-severity"}


def test_low_replacement_for_digital_routine_work_is_critical() -> None:
    row = candidate(
        replacementRisk=32.0,
        factorContributions=[
            {"factor": "taskAutomationExposure", "value": 85.0, "weight": 0.35, "weightedContribution": 29.75},
            {"factor": "adoptionPressure", "value": 20.0, "weight": 0.15, "weightedContribution": 3.0},
        ],
        structuralProxyInputs={"values": {"physical-presence": 10.0, "human-dependency": 20.0}},
    )
    findings = triage_occupation(row)
    finding = next(item for item in findings
                   if item["code"] == "low_replacement_despite_digital_routine_composition")
    assert finding["severity"] == "critical"


def test_single_factor_dominance_is_detected_against_the_actual_score() -> None:
    row = candidate(
        replacementRisk=40.0,
        factorContributions=[
            {"factor": "taskAutomationExposure", "value": 90.0, "weight": 0.35, "weightedContribution": 31.5},
            {"factor": "adoptionPressure", "value": 56.0, "weight": 0.15, "weightedContribution": 8.5},
        ],
    )
    finding = next(item for item in triage_occupation(row) if item["code"] == "single_factor_dependence")
    assert finding["severity"] == "high"
    assert finding["observed"]["factor"] == "taskAutomationExposure"
    assert finding["observed"]["share"] > GATES["maximumSingleFactorShare"]


def test_single_task_dominance_is_medium_not_blocking() -> None:
    row = candidate(taskContributions=[
        {"onetTaskId": 1, "statement": "Dominant task", "aiExposureContribution": 40.0},
        {"onetTaskId": 2, "statement": "Minor task", "aiExposureContribution": 22.0},
    ])
    findings = triage_occupation(row)
    finding = next(item for item in findings if item["code"] == "single_task_dependence")
    assert finding["severity"] == "medium"

    result = triage_corpus([row])["results"][0]
    assert result["launchEligible"], "a medium finding must not exclude"
    assert result["highestSeverity"] == "medium"


def test_exposure_replacement_gap_blocks() -> None:
    findings = triage_occupation(candidate(aiExposure=85.0, replacementRisk=55.0))
    finding = next(item for item in findings if item["code"] == "exposure_replacement_gap")
    assert finding["severity"] == "high"
    assert finding["observed"]["gap"] == 30.0


def test_blocked_candidates_are_critical_and_do_not_crash_on_missing_scores() -> None:
    findings = triage_occupation({
        "candidateOccupationId": 9, "occupationCode": "00-0000.00", "title": "Blocked",
        "candidateStatus": "blocked", "coverageGateStatus": "below_threshold",
        "confidenceGateStatus": "passed", "aiExposure": None, "replacementRisk": None,
        "confidence": 40.0, "weightedTaskCoverage": 55.0,
    })
    assert codes(findings) == {"not_review_ready"}
    assert findings[0]["severity"] == "critical"


def test_soc_family_discontinuity_flags_every_member_of_a_spread_family() -> None:
    rows = [
        candidate(candidateOccupationId=1, occupationCode="29-1141.01", aiExposure=30.0, replacementRisk=30.0),
        candidate(candidateOccupationId=2, occupationCode="29-1141.02", aiExposure=75.0, replacementRisk=40.0),
        candidate(candidateOccupationId=3, occupationCode="15-1252.00", aiExposure=60.0, replacementRisk=55.0),
    ]
    flagged = soc_family_discontinuities(rows)
    assert set(flagged) == {1, 2}, "only the spread family is flagged, and both members are"
    assert flagged[1]["severity"] == "medium"


def test_cohort_is_everything_that_passes_with_no_target_size() -> None:
    rows = [
        candidate(candidateOccupationId=1, occupationCode="13-2011.00"),
        candidate(candidateOccupationId=2, occupationCode="13-2012.00"),
        candidate(candidateOccupationId=3, occupationCode="13-2013.00", confidence=60.0),   # high
        candidate(candidateOccupationId=4, occupationCode="13-2014.00", replacementRisk=78.0,
                  structuralProxyInputs={"values": {"physical-presence": 95.0}}),           # critical
    ]
    report = triage_corpus(rows)

    assert report["policyVersion"] == TRIAGE_POLICY_VERSION
    assert report["candidatesAssessed"] == 4
    assert report["launchCohortSize"] == 2
    assert report["excludedCount"] == 2
    assert report["cohortSelection"] == "all candidates with no critical and no high findings"
    assert "targetCount" not in report and "launchTargetCount" not in report
    assert report["exclusionReasons"]["confidence_below_launch_minimum"] == 1
    assert report["exclusionReasons"]["high_replacement_despite_severe_constraints"] == 1
    assert report["severityTotals"]["critical"] == 1
    assert report["severityTotals"]["low"] == 4, "the universal disclosure is recorded for every candidate"


def test_triage_is_deterministic() -> None:
    rows = [candidate(candidateOccupationId=index, occupationCode=f"13-20{index:02d}.00")
            for index in range(1, 25)]
    first = triage_corpus(rows)
    second = triage_corpus(rows)
    assert first == second
