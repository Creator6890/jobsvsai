import unittest

from scoring.exposure import TaskScore, calculate_exposure
from scoring.replacement import ReplacementInputs, calculate_replacement_derivation, calculate_replacement_risk


class ScoringTests(unittest.TestCase):
    def test_exposure_is_importance_weighted(self) -> None:
        result = calculate_exposure([TaskScore(exposure=90, importance=80), TaskScore(exposure=20, importance=20)])
        self.assertEqual(result, 76)

    def test_replacement_risk_reduces_for_human_and_physical_dependency(self) -> None:
        exposed = calculate_replacement_risk(ReplacementInputs(80, 80, 20, 10, 85, 40))
        resilient = calculate_replacement_risk(ReplacementInputs(80, 80, 90, 90, 85, 90))
        self.assertLess(resilient, exposed)

    def test_replacement_rejects_out_of_range_inputs(self) -> None:
        with self.assertRaises(ValueError):
            calculate_replacement_risk(ReplacementInputs(101, 50, 50, 50, 50, 50))

    def test_derivation_contributions_reconcile(self) -> None:
        derivation = calculate_replacement_derivation(ReplacementInputs(70.45, 88, 48, 8, 89, 58))
        self.assertAlmostEqual(sum(factor.contribution for factor in derivation.factors), derivation.total, places=2)
        human = next(factor for factor in derivation.factors if factor.key == "human_dependency")
        self.assertEqual(human.transformed_value, 52)


if __name__ == "__main__":
    unittest.main()
