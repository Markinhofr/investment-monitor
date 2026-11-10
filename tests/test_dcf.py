
import unittest
from src.dcf import calculate_dcf


class TestDCF(unittest.TestCase):

    def test_base_scenario(self):
        result = calculate_dcf(
            fcf=73.266e9,
            net_debt=69.784e9,
            shares=12.324e9,
            growth=0.10,
            discount_rate=0.09,
            terminal_growth=0.025
        )
        self.assertAlmostEqual(
            result["fair_value_per_share"],
            123.02,
            places=1
        )

    def test_zero_shares(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                100, 20, 0, 0.05, 0.10, 0.02
            )

    def test_invalid_discount_rate(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                100, 20, 10, 0.05, 0.02, 0.03
            )

    def test_negative_fcf(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                -100, 20, 10, 0.05, 0.10, 0.02
            )

    def test_more_debt_reduces_value(self):
        a = calculate_dcf(
            100, 20, 10, 0.05, 0.10, 0.02
        )
        b = calculate_dcf(
            100, 40, 10, 0.05, 0.10, 0.02
        )
        self.assertLess(
            b["fair_value_per_share"],
            a["fair_value_per_share"]
        )


if __name__ == "__main__":
    unittest.main()

