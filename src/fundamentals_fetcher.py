
import json
import os
import urllib.request
from datetime import date, datetime, timezone

SEC_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/"
    "CIK0001652044.json"
)

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]

INCOME_TAGS = ["NetIncomeLoss"]

OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities"
]

CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment"
]


def get_sec_data():
    agent = os.environ.get("SEC_USER_AGENT", "")

    if not agent or "@" not in agent:
        raise RuntimeError(
            "Configure SEC_USER_AGENT com um "
            "contacto valido antes da consulta."
        )

    request = urllib.request.Request(
        SEC_URL,
        headers={
            "User-Agent": agent,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(
        request, timeout=30
    ) as response:
        return json.load(response)


def duration_days(item):
    if not item.get("start") or not item.get("end"):
        return None

    return (
        date.fromisoformat(item["end"])
        - date.fromisoformat(item["start"])
    ).days + 1


def candidates(facts, tags, unit="USD"):
    result = []

    for tag in tags:
        entries = (
            facts.get(tag, {})
            .get("units", {})
            .get(unit, [])
        )

        for item in entries:
            if item.get("form") not in ("10-K", "10-Q"):
                continue

            if not item.get("filed") or not item.get("end"):
                continue

            if not isinstance(item.get("val"), (int, float)):
                continue

            result.append({
                **item,
                "_tag": tag,
                "_unit": unit,
            })

    return result


def pack(item):
    if item is None:
        return None

    return {
        "value": item["val"],
        "start": item.get("start"),
        "end": item["end"],
        "filed": item["filed"],
        "accession": item.get("accn"),
        "tag": item["_tag"],
        "unit": item["_unit"],
    }


def latest_annual(facts, tags):
    rows = [
        x for x in candidates(facts, tags)
        if x["form"] == "10-K"
        and 350 <= (duration_days(x) or 0) <= 380
    ]

    if not rows:
        return None

    latest_end = max(x["end"] for x in rows)

    matching = [
        x for x in rows
        if x["end"] == latest_end
    ]

    # Prefer the most recently filed observation
    # for the selected annual period.
    return pack(max(
        matching,
        key=lambda x: (
            x["filed"],
            x.get("accn", ""),
        )
    ))


def latest_instant(facts, tags, unit="USD"):
    rows = [
        x for x in candidates(facts, tags, unit)
        if not x.get("start")
    ]

    if not rows:
        return None

    return pack(max(
        rows,
        key=lambda x: (
            x["end"],
            x["filed"],
        )
    ))


def annual_for_period(facts, tags, start, end):
    rows = [
        x for x in candidates(facts, tags)
        if x["form"] == "10-K"
        and x.get("start") == start
        and x["end"] == end
    ]

    if not rows:
        return None

    return pack(max(
        rows,
        key=lambda x: x["filed"]
    ))


def quarterly_ytd(facts, tags, year, quarter):
    ranges = {
        1: (75, 105),
        2: (165, 200),
        3: (255, 290),
    }

    low, high = ranges[quarter]

    rows = [
        x for x in candidates(facts, tags)
        if x["form"] == "10-Q"
        and x.get("start") == f"{year}-01-01"
        and x["end"].startswith(str(year))
        and low <= (duration_days(x) or 0) <= high
    ]

    if not rows:
        return None

    return pack(max(
        rows,
        key=lambda x: (
            x["end"],
            x["filed"],
        )
    ))


def calculate_ttm(facts, tags, annual):
    if not annual:
        return None

    year = int(annual["end"][:4])

    # Select the latest available current-year
    # YTD period and the matching prior-year YTD.
    for quarter in (3, 2, 1):
        current = quarterly_ytd(
            facts, tags, year + 1, quarter
        )
        previous = quarterly_ytd(
            facts, tags, year, quarter
        )

        if not current or not previous:
            continue

        if current["end"][5:] != previous["end"][5:]:
            continue

        value = (
            annual["value"]
            + current["value"]
            - previous["value"]
        )

        return {
            "value": value,
            "end": current["end"],
            "method": "FY + current YTD - prior YTD",
            "components": {
                "annual": annual["value"],
                "current_ytd": current["value"],
                "prior_ytd": previous["value"],
            },
            "verified": False,
        }

    return None


def fetch_alphabet():
    facts = get_sec_data()["facts"]["us-gaap"]

    revenue = latest_annual(facts, REVENUE_TAGS)

    if revenue is None:
        raise ValueError(
            "Nao foi encontrado um periodo anual "
            "valido para receitas."
        )

    start = revenue["start"]
    end = revenue["end"]

    income = annual_for_period(
        facts, INCOME_TAGS, start, end
    )

    ocf = annual_for_period(
        facts, OCF_TAGS, start, end
    )

    capex = annual_for_period(
        facts, CAPEX_TAGS, start, end
    )

    fcf = None

    if ocf and capex:
        fcf = {
            "value": ocf["value"] - capex["value"],
            "start": start,
            "end": end,
            "method": "Operating cash flow - CapEx",
            "verified": False,
        }

    return {
        "company": "Alphabet",
        "ticker": "GOOGL",
        "currency": "USD",
        "annual_revenue": revenue,
        "annual_net_income": income,
        "ttm_revenue": calculate_ttm(
            facts, REVENUE_TAGS, revenue
        ),
        "ttm_net_income": calculate_ttm(
            facts, INCOME_TAGS, income
        ),
        "annual_operating_cash_flow": ocf,
        "annual_capex": capex,
        "annual_free_cash_flow": fcf,
        "cash": latest_instant(
            facts,
            ["CashAndCashEquivalentsAtCarryingValue"]
        ),
        "shares_outstanding": latest_instant(
            facts,
            ["CommonStockSharesOutstanding"],
            "shares",
        ),
        "source": SEC_URL,
        "retrieved_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "verified": False,
    }


if __name__ == "__main__":
    print(json.dumps(
        fetch_alphabet(), indent=2
    ))



def calculate_net_debt(current_debt, noncurrent_debt, cash):
    """
    Calcula a divida liquida preliminar.
    Os valores devem corresponder a mesma data,
    moeda e base contabilistica.
    """
    values = [current_debt, noncurrent_debt, cash]

    if any(
        not isinstance(x, (int, float))
        or isinstance(x, bool)
        or x < 0
        for x in values
    ):
        raise ValueError("Dados de divida ou caixa invalidos")

    total_debt = current_debt + noncurrent_debt

    return {
        "total_debt": total_debt,
        "cash": cash,
        "net_debt": total_debt - cash,
        "verified": False,
    }

