
import unittest

from src.valuation import calculate_dcf, evaluate_stock


class TestValuation(unittest.TestCase):

    def test_dcf_known_value(self):
        # DCF de um unico ano:
        # FCF1 = 110
        # Valor terminal = 110 * 1.02 / (0.10 - 0.02)
        # Valor presente total = 1375
        result = calculate_dcf(
            free_cash_flow=100,
            growth_rate=0.10,
            discount_rate=0.10,
            terminal_growth=0.02,
            years=1,
            shares_outstanding=10,
            net_debt=0,
        )
        self.assertAlmostEqual(result, 137.5, places=5)

    def test_margin_of_safety(self):
        result = evaluate_stock(
            current_price=75,
            fair_value=100,
        )
        self.assertEqual(result.margin_of_safety, 25.0)
        self.assertEqual(result.buy_price_20, 80.0)
        self.assertEqual(result.buy_price_30, 70.0)
        self.assertEqual(
            result.classification,
            "OBSERVAR_OPORTUNIDADE",
        )

    def test_buy_threshold(self):
        result = evaluate_stock(65, 100)
        self.assertEqual(
            result.classification,
            "INVESTIGAR_COMPRA",
        )

    def test_overvalued(self):
        result = evaluate_stock(120, 100)
        self.assertEqual(
            result.classification,
            "ACIMA_VALOR_JUSTO",
        )
        self.assertEqual(result.margin_of_safety, -20.0)

    def test_invalid_dcf(self):
        with self.assertRaises(ValueError):
            calculate_dcf(
                free_cash_flow=100,
                growth_rate=0.05,
                discount_rate=0.02,
                terminal_growth=0.03,
                years=5,
                shares_outstanding=10,
            )

    def test_invalid_prices(self):
        with self.assertRaises(ValueError):
            evaluate_stock(0, 100)


if __name__ == "__main__":
    unittest.main()
