import json
import math
import os
import urllib.request
from datetime import date, datetime, timezone

SEC_URL = 'https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json'
REVENUE_TAGS = ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet']
INCOME_TAGS = ['NetIncomeLoss']
OCF_TAGS = ['NetCashProvidedByUsedInOperatingActivities']
CAPEX_TAGS = ['PaymentsToAcquirePropertyPlantAndEquipment']


def get_sec_data():
    agent = os.environ.get('SEC_USER_AGENT', '')
    if not agent or '@' not in agent:
        raise RuntimeError('Configure SEC_USER_AGENT com um contacto valido antes da consulta.')
    request = urllib.request.Request(SEC_URL, headers={'User-Agent': agent, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def duration_days(item):
    if not item.get('start') or not item.get('end'):
        return None
    return (date.fromisoformat(item['end']) - date.fromisoformat(item['start'])).days + 1


def candidates(facts, tags, unit='USD'):
    result = []
    for tag in tags:
        for item in facts.get(tag, {}).get('units', {}).get(unit, []):
            if item.get('form') not in ('10-K', '10-Q') or not item.get('filed') or not item.get('end'):
                continue
            if not isinstance(item.get('val'), (int, float)) or isinstance(item['val'], bool) or not math.isfinite(item['val']):
                continue
            result.append({**item, '_tag': tag, '_unit': unit})
    return result


def pack(item):
    if item is None:
        return None
    return {'value': item['val'], 'start': item.get('start'), 'end': item['end'],
            'filed': item['filed'], 'accession': item.get('accn'),
            'tag': item['_tag'], 'unit': item['_unit']}


def choose(rows, tags):
    if not rows:
        return None
    priority = {tag: len(tags) - i for i, tag in enumerate(tags)}
    # Prefer latest filed comparative/restatement for the selected tag and period.
    return pack(max(rows, key=lambda x: (priority.get(x['_tag'], 0), x['filed'], x.get('accn', ''))))


def latest_annual(facts, tags):
    rows = [x for x in candidates(facts, tags) if x['form'] == '10-K'
            and 350 <= (duration_days(x) or 0) <= 380]
    if not rows:
        return None
    end = max(x['end'] for x in rows)
    return choose([x for x in rows if x['end'] == end], tags)


def latest_instant(facts, tags, unit='USD'):
    rows = [x for x in candidates(facts, tags, unit) if not x.get('start')]
    if not rows:
        return None
    end = max(x['end'] for x in rows)
    return choose([x for x in rows if x['end'] == end], tags)


def annual_for_period(facts, tags, start, end):
    rows = [x for x in candidates(facts, tags) if x['form'] == '10-K'
            and x.get('start') == start and x['end'] == end]
    return choose(rows, tags)


def quarterly_ytd(facts, tags, year, quarter):
    ranges = {1: (75, 105), 2: (165, 200), 3: (255, 290)}
    low, high = ranges[quarter]
    rows = [x for x in candidates(facts, tags) if x['form'] == '10-Q'
            and x.get('start') == f'{year}-01-01'
            and x['end'].startswith(f'{year}-')
            and low <= (duration_days(x) or 0) <= high]
    if not rows:
        return None
    end = max(x['end'] for x in rows)
    return choose([x for x in rows if x['end'] == end], tags)


def calculate_ttm(facts, tags, annual):
    if not annual:
        return None
    year = int(annual['end'][:4])
    for quarter in (3, 2, 1):
        current = quarterly_ytd(facts, tags, year + 1, quarter)
        previous = quarterly_ytd(facts, tags, year, quarter)
        if not current or not previous or current['end'][5:] != previous['end'][5:]:
            continue
        if current['tag'] != previous['tag'] or annual['tag'] != current['tag']:
            continue
        value = annual['value'] + current['value'] - previous['value']
        return {'value': value, 'end': current['end'], 'method': 'FY + current YTD - prior YTD',
                'components': {'annual': annual['value'], 'current_ytd': current['value'],
                               'prior_ytd': previous['value']},
                'sources': {'annual': annual, 'current_ytd': current, 'prior_ytd': previous},
                'verified': False}
    return None


def calculate_net_debt(current_debt, noncurrent_debt, cash):
    values = [current_debt, noncurrent_debt, cash]
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or x < 0 for x in values):
        raise ValueError('Dados de divida ou caixa invalidos')
    total_debt = current_debt + noncurrent_debt
    return {'total_debt': total_debt, 'cash': cash, 'net_debt': total_debt - cash, 'verified': False}


def fetch_alphabet():
    payload = get_sec_data()
    if str(payload.get('cik')).lstrip('0') != '1652044':
        raise ValueError('CIK inesperado')
    facts = payload['facts']['us-gaap']
    revenue = latest_annual(facts, REVENUE_TAGS)
    if revenue is None:
        raise ValueError('Nao foi encontrado um periodo anual valido para receitas.')
    start, end = revenue['start'], revenue['end']
    income = annual_for_period(facts, INCOME_TAGS, start, end)
    ocf = annual_for_period(facts, OCF_TAGS, start, end)
    capex = annual_for_period(facts, CAPEX_TAGS, start, end)
    fcf = None
    if ocf and capex and ocf['unit'] == capex['unit']:
        fcf = {'value': ocf['value'] - capex['value'], 'start': start, 'end': end,
               'method': 'Operating cash flow - CapEx', 'verified': False}
    return {'company': 'Alphabet', 'ticker': 'GOOGL', 'currency': 'USD',
            'annual_revenue': revenue, 'annual_net_income': income,
            'ttm_revenue': calculate_ttm(facts, REVENUE_TAGS, revenue),
            'ttm_net_income': calculate_ttm(facts, INCOME_TAGS, income),
            'annual_operating_cash_flow': ocf, 'annual_capex': capex,
            'annual_free_cash_flow': fcf,
            'cash': latest_instant(facts, ['CashAndCashEquivalentsAtCarryingValue']),
            'shares_outstanding': latest_instant(facts, ['CommonStockSharesOutstanding'], 'shares'),
            'source': SEC_URL, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'verified': False,
            'balance_sheet': balance_sheet(facts),
            'ttm_operating_cash_flow': calculate_ttm(facts, OCF_TAGS, ocf) or ocf,
            'ttm_capex': calculate_ttm(facts, CAPEX_TAGS, capex) or capex}




def balance_sheet(facts):
    tags = {
        'cash': ['CashAndCashEquivalentsAtCarryingValue'],
        'current_debt': ['LongTermDebtCurrent', 'LongTermDebtAndCapitalLeaseObligationsCurrent'],
        'noncurrent_debt': ['LongTermDebtNoncurrent', 'LongTermDebtAndCapitalLeaseObligations'],
        'shares': ['CommonStockSharesOutstanding'],
    }
    cash = latest_instant(facts, tags['cash'])
    if not cash:
        return {}
    end = cash['end']
    result = {}
    for name, alternatives in tags.items():
        rows = [x for x in candidates(facts, alternatives, 'shares' if name == 'shares' else 'USD')
                if not x.get('start') and x['end'] == end]
        result[name] = choose(rows, alternatives)
    return result

if __name__ == '__main__':
    print(json.dumps(fetch_alphabet(), indent=2))
