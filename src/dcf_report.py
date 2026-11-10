
import json
from datetime import datetime, timezone
from pathlib import Path

from src.dcf import calculate_dcf

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "dcf_alphabet.json"

SCENARIOS = {
    "pessimistic": (0.05, 0.11, 0.02),
    "base": (0.10, 0.09, 0.025),
    "optimistic": (0.15, 0.08, 0.03),
}


def generate_report():
    results = {}

    for name, (growth, discount, terminal) in SCENARIOS.items():
        valuation = calculate_dcf(
            fcf=73.266e9,
            net_debt=69.784e9,
            shares=12.324e9,
            growth=growth,
            discount_rate=discount,
            terminal_growth=terminal,
        )

        results[name] = {
            "fair_value": round(
                valuation["fair_value_per_share"], 2
            ),
            "growth": growth,
            "discount_rate": discount,
            "terminal_growth": terminal,
        }

    report = {
        "ticker": "GOOGL",
        "company": "Alphabet",
        "currency": "USD",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "verified": False,
        "valuation_ready": False,
        "signal": "NO_SIGNAL",
        "method": "DCF_5Y",
        "warning": (
            "Demonstracao com pressupostos e dados "
            "ainda nao validados. Nao usar como "
            "recomendacao de investimento."
        ),
        "scenarios": results,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    return report


if __name__ == "__main__":
    report = generate_report()
    print(json.dumps(report, indent=2))

