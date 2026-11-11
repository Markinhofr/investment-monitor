
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
    from src.dcf import calculate_dcf as core_dcf
    return max(0.0, core_dcf(free_cash_flow, net_debt, shares_outstanding,
                           growth_rate, discount_rate, terminal_growth, years)["fair_value_per_share"])


def evaluate_stock(
    current_price: float,
    fair_value: float,
) -> ValuationResult:
    import math
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in (current_price, fair_value)) or current_price <= 0 or fair_value <= 0:
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
