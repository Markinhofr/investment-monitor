
from dataclasses import dataclass


@dataclass
class ValuationResult:
    fair_value: float
    margin_of_safety: float
    buy_price_20: float
    buy_price_30: float
    classification: str


def calculate_dcf(
    free_cash_flow: float,
    growth_rate: float,
    discount_rate: float,
    terminal_growth: float,
    years: int,
    shares_outstanding: float,
    net_debt: float = 0.0,
) -> float:
    """
    DCF simplificado, com fluxos de caixa livres
    projetados e valor terminal.

    Os valores monetarios devem usar a mesma
    unidade e moeda.
    """
    if years < 1:
        raise ValueError("Years must be positive")

    if shares_outstanding <= 0:
        raise ValueError("Invalid share count")

    if discount_rate <= terminal_growth:
        raise ValueError(
            "Discount rate must exceed terminal growth"
        )

    if discount_rate <= -1 or growth_rate <= -1:
        raise ValueError("Invalid growth/discount rate")

    if free_cash_flow < 0:
        raise ValueError(
            "This simplified model requires positive FCF"
        )

    present_value = 0.0
    projected_fcf = free_cash_flow

    for year in range(1, years + 1):
        projected_fcf *= (1 + growth_rate)
        present_value += (
            projected_fcf / (1 + discount_rate) ** year
        )

    terminal_value = (
        projected_fcf * (1 + terminal_growth)
        / (discount_rate - terminal_growth)
    )

    present_value += (
        terminal_value / (1 + discount_rate) ** years
    )

    equity_value = present_value - net_debt

    return max(0.0, equity_value / shares_outstanding)


def evaluate_stock(
    current_price: float,
    fair_value: float,
) -> ValuationResult:
    if current_price <= 0 or fair_value <= 0:
        raise ValueError("Prices must be positive")

    margin = (fair_value - current_price) / fair_value

    if margin >= 0.30:
        classification = "INVESTIGAR_COMPRA"
    elif margin >= 0.20:
        classification = "OBSERVAR_OPORTUNIDADE"
    elif margin >= 0:
        classification = "PROXIMO_VALOR_JUSTO"
    else:
        classification = "ACIMA_VALOR_JUSTO"

    return ValuationResult(
        fair_value=round(fair_value, 2),
        margin_of_safety=round(margin * 100, 2),
        buy_price_20=round(fair_value * 0.80, 2),
        buy_price_30=round(fair_value * 0.70, 2),
        classification=classification,
    )
