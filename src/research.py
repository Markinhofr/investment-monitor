"""Fail-closed SEC research pipeline. Review attestations expire with each filing."""
import math
from datetime import date, datetime, timezone
from src.dcf import calculate_dcf
from src.dcf_report import SCENARIOS
from src.fundamentals_fetcher import fetch_alphabet, SEC_URL


def number(value, positive=False):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and (value > 0 if positive else True))


def recent(value, now, days):
    try:
        age = (now - date.fromisoformat(value[:10])).days
        return 0 <= age <= days
    except (TypeError, ValueError):
        return False


def analyze(data, review, now=None):
    now = now or date.today()
    errors = []
    balance = data.get('balance_sheet', {})
    ocf, capex = data.get('ttm_operating_cash_flow'), data.get('ttm_capex')
    def valid_record(item, unit):
        return (isinstance(item, dict) and number(item.get('value'))
                and item.get('unit') == unit and item.get('accession')
                and recent(item.get('filed'), now, 500))
    def duration_sources(item):
        if not item:
            return []
        return list(item.get('sources', {}).values()) or [item]
    for name, item in [('ocf', ocf), ('capex', capex)]:
        sources = duration_sources(item)
        if not sources or not all(valid_record(x, 'USD') for x in sources):
            errors.append('INVALID_' + name.upper())
    for item in (ocf, capex):
        sources = duration_sources(item)
        try:
            if len(sources) == 3:
                annual, current, prior = sources
                expected = annual['value'] + current['value'] - prior['value']
                if (current['start'][5:] != '01-01' or prior['start'][5:] != '01-01'
                        or current['end'][5:] != prior['end'][5:]
                        or int(current['start'][:4]) != int(annual['end'][:4]) + 1
                        or int(prior['start'][:4]) != int(annual['end'][:4])
                        or item['end'] != current['end']):
                    raise ValueError('Incompatible YTD periods')
            elif len(sources) == 1:
                annual = sources[0]
                expected = annual['value']
                if item['end'] != annual['end']:
                    raise ValueError('Annual end mismatch')
            else:
                raise ValueError('Missing components')
            duration = (date.fromisoformat(annual['end']) - date.fromisoformat(annual['start'])).days + 1
            if not 350 <= duration <= 380 or not number(item['value']) or abs(expected - item['value']) > 1:
                raise ValueError('Cash flow reconciliation failed')
        except (TypeError, ValueError, KeyError):
            errors.append('CASH_FLOW_RECONCILIATION_FAILED')
    end = (ocf or {}).get('end')
    if not recent(end, now, 150) or end != (capex or {}).get('end'):
        errors.append('STALE_OR_MISMATCHED_CASH_FLOW')
    osources, csources = duration_sources(ocf), duration_sources(capex)
    if len(osources) != len(csources) or any(
        (o.get('start'), o.get('end'), o.get('accession')) !=
        (c.get('start'), c.get('end'), c.get('accession'))
        for o, c in zip(osources, csources)
    ):
        errors.append('INCOMPATIBLE_CASH_FLOW_COMPONENTS')
    fcf = None
    if not errors and number(ocf.get('value')) and number(capex.get('value')) and capex['value'] >= 0:
        fcf = ocf['value'] - capex['value']
    else:
        errors.append('FCF_NOT_VALIDATED')
    for name in ('cash', 'current_debt', 'noncurrent_debt', 'shares'):
        item = balance.get(name)
        if (not valid_record(item, 'shares' if name == 'shares' else 'USD')
                or item['end'] != end or item['value'] < 0
                or (name == 'shares' and item['value'] == 0)):
            errors.append('INVALID_' + name.upper())
    accessions = {x.get('accession') for x in balance.values() if isinstance(x, dict)}
    if len(accessions) != 1:
        errors.append('BALANCE_FILINGS_DIFFER')
    structural = not errors
    filing = balance.get('cash') or {}
    # SEC companyfacts omits class dimensions: consolidated shares require filing review.
    if not (review.get('period_end') == end and review.get('accession') == filing.get('accession')
            and review.get('reviewed_by') and (review.get('source_url') or '').startswith('https://www.sec.gov/Archives/')
            and recent(review.get('reviewed_at'), now, 120)
            and review.get('all_share_classes_confirmed') is True
            and review.get('debt_scope_confirmed') is True
            and review.get('extraordinary_cash_flows_reviewed') is True
            and review.get('assumptions_approved') is True):
        errors.append('FILING_REVIEW_REQUIRED')
    normalized = review.get('normalized_fcf')
    if not number(normalized, True) or not number(fcf, True) or normalized > fcf or not review.get('normalization_rationale'):
        errors.append('NORMALIZED_FCF_NOT_VALIDATED')
    net_debt = None
    if structural:
        net_debt = balance['current_debt']['value'] + balance['noncurrent_debt']['value'] - balance['cash']['value']
    ready = not errors
    metrics = {}
    for name in ('annual_revenue', 'annual_net_income'):
        item = data.get(name)
        if valid_record(item, 'USD') and recent(item.get('end'), now, 500):
            metrics[name] = item
    scenarios = {}
    for name, (growth, discount, terminal) in SCENARIOS.items():
        result = calculate_dcf(normalized, net_debt, balance['shares']['value'], growth, discount, terminal) if ready else None
        scenarios[name] = {'fair_value': result['fair_value_per_share'] if result else None,
                           'growth': growth, 'discount_rate': discount, 'terminal_growth': terminal,
                           'years': 5, 'calculation': result}
    return {'ticker': 'GOOGL', 'currency': 'USD', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'verified': ready, 'valuation_ready': ready, 'signal': 'NO_SIGNAL',
            'data_status': 'VALIDATED' if ready else 'VALIDATION_PENDING', 'errors': sorted(set(errors)),
            'source': SEC_URL, 'period_end': end, 'accession': filing.get('accession'),
            'fcf_ttm': {'value': fcf, 'end': end, 'verified': structural},
            'fcf_normalized': {'value': normalized if ready else None, 'rationale': review.get('normalization_rationale'), 'verified': ready},
            'net_debt': net_debt if ready else None,
            'metrics': metrics,
            'shares_outstanding': balance['shares']['value'] if ready else None,
            'scenarios': scenarios, 'review': review, 'fundamentals': data,
            'warning': 'DCF sensível aos pressupostos. OCF menos CapEx é um proxy simplificado; não é FCFF puro. Ganhos contabilísticos extraordinários não são extrapolados.'}


def collect(review, offline=False):
    try:
        if offline:
            raise RuntimeError('OFFLINE')
        return analyze(fetch_alphabet(), review)
    except Exception as error:
        report = analyze({}, {})
        report.update(data_status='DATA_UNAVAILABLE', data_error=type(error).__name__)
        return report
