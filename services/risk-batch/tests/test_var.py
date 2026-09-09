import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from risk_batch.var import batch_var, expected_shortfall, historical_var


class ValueAtRiskTest(unittest.TestCase):
    def test_historical_var_uses_lower_tail(self):
        self.assertAlmostEqual(historical_var([-0.2, -0.1, 0.0, 0.1], 0.75), 0.2)

    def test_expected_shortfall_averages_the_tail(self):
        self.assertAlmostEqual(
            expected_shortfall([-0.3, -0.2, -0.1, 0.0], 0.75),
            0.3,
        )

    def test_batch_var_returns_each_portfolio(self):
        result = batch_var(
            {"growth": [-0.2, -0.1, 0.0, 0.1], "income": [-0.05, 0.0, 0.01, 0.02]},
            0.75,
        )
        self.assertEqual(set(result), {"growth", "income"})
        self.assertAlmostEqual(result["growth"], 0.2)
        self.assertAlmostEqual(result["income"], 0.05)

    def test_empty_returns_are_rejected(self):
        with self.assertRaises(ValueError):
            historical_var([])

    def test_confidence_must_be_between_zero_and_one(self):
        for confidence in (0.0, 1.0, -0.1, 1.1):
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValueError):
                    historical_var([0.0, 0.1], confidence)

    def test_non_finite_returns_are_rejected(self):
        with self.assertRaises(ValueError):
            historical_var([0.0, float("nan")])


if __name__ == "__main__":
    unittest.main()
