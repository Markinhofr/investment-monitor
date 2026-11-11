
import unittest

from src.fundamental_validator import validate_fundamentals


def sample_data():
    period = {
        "start": "2025-01-01",
        "end": "2025-12-31"
    }

    def item(value):
        return {"value": value, **period}

    return {
        "annual_revenue": item(400),
        "annual_net_income": item(100),
        "annual_operating_cash_flow": item(150),
        "annual_capex": item(50),
        "annual_free_cash_flow": item(100),
        "ttm_revenue": {
            "value": 450,
            "end": "2026-09-30"
        },
        "ttm_net_income": {
            "value": 110,
            "end": "2026-09-30"
        },
        "shares_outstanding": {
            "value": 12_000_000_000,
            "end": "2026-09-30"
        },
        "verified": False
    }


class TestFundamentalValidator(unittest.TestCase):

    def test_valid_periods(self):
        result = validate_fundamentals(sample_data())
        self.assertTrue(result["valid"])
        self.assertFalse(result["valuation_ready"])

    def test_rejects_different_years(self):
        data = sample_data()
        data["annual_net_income"]["end"] = "2024-12-31"
        result = validate_fundamentals(data)
        self.assertFalse(result["valid"])

    def test_rejects_wrong_fcf(self):
        data = sample_data()
        data["annual_free_cash_flow"]["value"] = 999
        result = validate_fundamentals(data)
        self.assertFalse(result["valid"])

    def test_rejects_different_ttm_dates(self):
        data = sample_data()
        data["ttm_net_income"]["end"] = "2026-06-30"
        result = validate_fundamentals(data)
        self.assertFalse(result["valid"])

    def test_rejects_missing_shares(self):
        data = sample_data()
        data["shares_outstanding"] = None
        result = validate_fundamentals(data)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()

