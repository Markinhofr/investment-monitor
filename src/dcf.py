import math


def calculate_dcf(
    fcf,
    net_debt,
    shares,
    growth,
    discount_rate,
    terminal_growth,
    years=5
):
    numbers = (fcf, net_debt, shares, growth, discount_rate, terminal_growth, years)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in numbers):
        raise ValueError("DCF requer numeros finitos")
    if not isinstance(years, int) or not 1 <= years <= 100 or discount_rate <= -1:
        raise ValueError("Horizonte ou desconto invalido")
    if fcf <= 0 or shares <= 0:
        raise ValueError("FCF e acoes devem ser positivos")

    if not (
        discount_rate > terminal_growth
        and terminal_growth > -1
        and growth > -1
        and years >= 1
    ):
        raise ValueError("Parametros DCF invalidos")

    projected_fcf = []
    present_value = 0

    for year in range(1, years + 1):
        future_fcf = fcf * (1 + growth) ** year
        discounted = future_fcf / (1 + discount_rate) ** year

        projected_fcf.append({
            "year": year,
            "fcf": future_fcf,
            "present_value": discounted
        })

        present_value += discounted

    terminal_fcf = projected_fcf[-1]["fcf"] * (
        1 + terminal_growth
    )

    terminal_value = terminal_fcf / (
        discount_rate - terminal_growth
    )

    discounted_terminal = terminal_value / (
        1 + discount_rate
    ) ** years

    enterprise_value = present_value + discounted_terminal
    equity_value = enterprise_value - net_debt

    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": equity_value / shares,
        "projected_fcf": projected_fcf,
        "assumptions": {
            "growth": growth,
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "years": years
        }
    }

