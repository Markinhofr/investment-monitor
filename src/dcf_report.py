
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.fundamentals_fetcher import (
    get_sec_data,
    latest_annual,
    annual_for_period,
    quarterly_ytd,
    OCF_TAGS,
    CAPEX_TAGS,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "dcf_alphabet.json"

SCENARIOS = {
    "pessimistic": (0.05, 0.11, 0.02),
    "base": (0.10, 0.09, 0.025),
    "optimistic": (0.15, 0.08, 0.03),
}


def calculate_ttm_fcf(facts):
    annual_ocf = latest_annual(facts, OCF_TAGS)

    if not annual_ocf:
        raise ValueError("Cash flow anual indisponivel")

    annual_capex = annual_for_period(
        facts,
        CAPEX_TAGS,
        annual_ocf["start"],
        annual_ocf["end"],
    )

    if not annual_capex:
        raise ValueError("CapEx anual indisponivel")

    year = int(annual_ocf["end"][:4])

    for quarter in (3, 2, 1):
        current_ocf = quarterly_ytd(
            facts, OCF_TAGS, year + 1, quarter
        )
        previous_ocf = quarterly_ytd(
            facts, OCF_TAGS, year, quarter
        )
        current_capex = quarterly_ytd(
            facts, CAPEX_TAGS, year + 1, quarter
        )
        previous_capex = quarterly_ytd(
            facts, CAPEX_TAGS, year, quarter
        )

        records = (
            current_ocf,
            previous_ocf,
            current_capex,
            previous_capex,
        )

        if any(record is None for record in records):
            continue

        if current_ocf["end"] != current_capex["end"]:
            continue

        if previous_ocf["end"] != previous_capex["end"]:
            continue

        if current_ocf["end"][5:] != previous_ocf["end"][5:]:
            continue

        annual_fcf = (
            annual_ocf["value"] - annual_capex["value"]
        )

        current_fcf = (
            current_ocf["value"] - current_capex["value"]
        )

        previous_fcf = (
            previous_ocf["value"] - previous_capex["value"]
        )

        ttm_fcf = annual_fcf + current_fcf - previous_fcf

        return {
            "value": ttm_fcf,
            "annual_fcf": annual_fcf,
            "current_ytd_fcf": current_fcf,
            "prior_ytd_fcf": previous_fcf,
            "end": current_ocf["end"],
            "source": (
                "https://data.sec.gov/api/xbrl/"
                "companyfacts/CIK0001652044.json"
            ),
            "verified": False,
        }

    raise ValueError(
        "Nao existem periodos compativeis para calcular FCF TTM"
    )


def generate_report(offline=False):
    from src.research import collect
    review_path = ROOT / 'data/alphabet_review.json'
    review = json.loads(review_path.read_text()) if review_path.exists() else {}
    report = collect(review, offline)
    for path in (OUTPUT, ROOT / 'docs/dcf_alphabet.json'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    return report


if __name__ == "__main__":
    print(json.dumps(
        generate_report(),
        indent=2,
        ensure_ascii=False,
    ))
