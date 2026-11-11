"""Review-only FCFF/WACC engine. No production imports, signals, network or publication.

All money is nominal USD. Rates are fractions. Numerical functions accept synthetic
or reviewed inputs; evaluate() is the evidence/approval boundary for real data.
"""
import math
from datetime import date


class ModelError(ValueError):
    pass


def finite(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ModelError(name + ': finite number required')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ModelError(name + ': out of range')
    return value


def rate(value, name, maximum=1):
    return finite(value, name, 0, maximum)


def sum_adjustments(adjustments):
    """Signed, separately evidenced adjustments; callers may not create a balancing plug."""
    seen = set()
    for row in adjustments:
        if not row.get('id') or row['id'] in seen:
            raise ModelError('Adjustment IDs must be unique')
        seen.add(row['id'])
        finite(row['value'], row['id'])
    return sum(row['value'] for row in adjustments)


def normalized_fcff(x):
    """EBIT route; SBC remains an economic operating expense, finance leases capitalized.

    Reported EBIT already expenses SBC. Replace it with the reviewed sustainable
    cost rather than subtracting it twice. D&A excludes the SBC cash-flow addback.
    Tax losses do not generate immediate refunds in this explicit implementation.
    """
    positive = ('reported_sbc', 'normalized_sbc', 'operating_da', 'sustainable_cash_capex',
                'finance_lease_investment', 'capitalized_interest_in_capex')
    for name in positive:
        finite(x[name], name, 0)
    for name in ('reported_ebit', 'owned_capex_accrual_change', 'normalized_delta_nwc'):
        finite(x[name], name)
    tax = rate(x['operating_tax_rate'], 'operating_tax_rate')
    adjustments = sum_adjustments(x['ebit_adjustments'])
    ebit = x['reported_ebit'] + x['reported_sbc'] - x['normalized_sbc'] + adjustments
    operating_tax = max(ebit, 0) * tax
    owned_capex = (x['sustainable_cash_capex'] + x['owned_capex_accrual_change']
                   - x['capitalized_interest_in_capex'])
    if owned_capex < 0:
        raise ModelError('Negative owned economic CapEx')
    economic_capex = owned_capex + x['finance_lease_investment']
    after_tax_adjustments = sum_adjustments(x['after_tax_adjustments'])
    result = (ebit - operating_tax + x['operating_da'] - economic_capex
              - x['normalized_delta_nwc'] + after_tax_adjustments)
    finite(result, 'normalized FCFF')
    return {'normalized_ebit': ebit, 'operating_tax': operating_tax,
            'nopat': ebit - operating_tax, 'operating_da': x['operating_da'],
            'owned_economic_capex': owned_capex, 'finance_lease_investment': x['finance_lease_investment'],
            'economic_capex': economic_capex, 'delta_nwc': x['normalized_delta_nwc'],
            'after_tax_adjustments': after_tax_adjustments, 'fcff': result,
            'formula': 'EBIT_normalized - cash_operating_tax + D&A - economic_CapEx - delta_operating_NWC + reviewed_after_tax_adjustments'}


def ocf_fcff_bridge(x, primary):
    """Independent CFO route; use cash interest INCLUDING lease interest, net of shield.

    Cash financing flows (lease principal, new borrowings, equity issuance) are not
    operating FCFF. New leased investment is included in economic CapEx instead.
    Reconciliation adjustments must explain actual tax, NWC, noncash/nonoperating
    differences. No automatic subtraction of the reconciliation difference.
    """
    finite(x['ocf'], 'ocf')
    finite(x['cash_interest_in_ocf_including_leases'], 'cash interest', 0)
    rate(x['interest_tax_shield_rate'], 'interest tax shield')
    finite(x['nonoperating_cash_after_tax'], 'nonoperating cash')
    finite(x['normalized_sbc'], 'normalized SBC', 0)
    finite(x['reconciliation_tolerance'], 'reconciliation tolerance', 0)
    if x['reconciliation_tolerance'] > max(1,abs(primary['fcff'])*.001):
        raise ModelError('Reconciliation tolerance exceeds 0.1% of FCFF (USD 1 minimum)')
    addback = x['cash_interest_in_ocf_including_leases'] * (1 - x['interest_tax_shield_rate'])
    adjustments = sum_adjustments(x['ocf_adjustments'])
    fcff = (x['ocf'] + addback - x['nonoperating_cash_after_tax'] - x['normalized_sbc']
            - primary['economic_capex'] + adjustments)
    finite(fcff,'CFO bridge FCFF')
    delta = fcff - primary['fcff']
    return {'ocf': x['ocf'], 'after_tax_cash_interest_addback': addback,
            'nonoperating_cash_after_tax_removed': x['nonoperating_cash_after_tax'],
            'sbc_economic_cost_removed': x['normalized_sbc'], 'adjustments': adjustments,
            'economic_capex': primary['economic_capex'], 'fcff': fcff,
            'difference_from_ebit_route': delta, 'tolerance':x['reconciliation_tolerance'], 'reconciled': abs(delta) <= x['reconciliation_tolerance']}


def wacc(x):
    """Market-value E/D/P weights. Hybrid preferred return includes conversion value.

    Operating leases are expensed in operations and excluded from D. Finance lease
    PV is in D; unlevered cash flows remove their financing cost consistently.
    """
    for name in ('risk_free', 'equity_risk_premium', 'country_risk_premium',
                 'notes_yield','finance_lease_yield', 'preferred_required_return'):
        rate(x[name], name)
    finite(x['beta'], 'beta', 0, 5)
    rate(x['marginal_debt_tax_rate'], 'marginal debt tax rate')
    rate(x['finance_lease_tax_rate'], 'finance lease tax rate')
    for name in ('notes_market_value','finance_lease_pv'): finite(x[name],name,0)
    if abs(x['debt_market_value']-x['notes_market_value']-x['finance_lease_pv'])>1e-6:
        raise ModelError('Debt market value must equal notes plus finance leases')
    for name in ('common_market_value', 'debt_market_value', 'preferred_market_value'):
        finite(x[name], name, 0)
    if x['common_market_value'] <= 0:
        raise ModelError('Common market capitalization must be positive')
    total = sum(x[k] for k in ('common_market_value', 'debt_market_value', 'preferred_market_value'))
    finite(total,'total market capital',0.000001)
    ke = x['risk_free'] + x['beta'] * x['equity_risk_premium'] + x['country_risk_premium']
    we, wd, wp = (x[k] / total for k in ('common_market_value', 'debt_market_value', 'preferred_market_value'))
    debt=x['debt_market_value']
    kd = (x['notes_market_value']*x['notes_yield']+x['finance_lease_pv']*x['finance_lease_yield'])/debt if debt else 0
    kd_net = (x['notes_market_value']*x['notes_yield']*(1-x['marginal_debt_tax_rate']) + x['finance_lease_pv']*x['finance_lease_yield']*(1-x['finance_lease_tax_rate']))/debt if debt else 0
    value = we * ke + wd * kd_net + wp * x['preferred_required_return']
    if value <= 0:
        raise ModelError('Positive WACC required')
    return {'cost_of_equity': ke, 'pre_tax_cost_of_debt': kd,
            'after_tax_cost_of_debt': kd_net, 'cost_of_preferred': x['preferred_required_return'],
            'weights': {'common': we, 'debt': wd, 'preferred': wp}, 'wacc': value,
            'debt_components': {'notes':{'market_value':x['notes_market_value'],'yield':x['notes_yield'],'tax_shield_rate':x['marginal_debt_tax_rate']},
                                'finance_leases':{'present_value':x['finance_lease_pv'],'yield':x['finance_lease_yield'],'tax_shield_rate':x['finance_lease_tax_rate']}},
            'formula': 'E/V*Ke + Notes/V*Kn*(1-Tn) + Lease/V*Kl*(1-Tl) + P/V*Kp'}


def capital_bridge(enterprise_value, x):
    """Deduct full hybrid fair value once; do NOT also add preferred conversion shares.

    Capped calls enter as a separately reviewed asset, never a second share offset.
    Existing non-SBC incremental dilution must exclude awards already charged in
    the cash-equivalent SBC model. No hypothetical future buybacks are assumed.
    """
    finite(enterprise_value, 'enterprise value')
    names = ('cash', 'minimum_operating_cash', 'investments_net_tax', 'capped_calls_value',
             'notes_market_value', 'finance_lease_pv', 'preferred_market_value',
             'minority_interest_value', 'other_claims_value', 'class_a', 'class_b', 'class_c',
             'incremental_non_sbc_shares')
    for name in names:
        finite(x[name], name, 0)
    if x['minimum_operating_cash'] > x['cash']:
        raise ModelError('Operating cash exceeds total cash')
    if x['preferred_treatment'] != 'full_hybrid_claim' or x['preferred_conversion_shares'] != 0:
        raise ModelError('Do not deduct preferred claim and add its conversion dilution')
    if x['future_sbc_dilution_rate'] != 0 or x['capped_call_share_offset'] != 0:
        raise ModelError('Cash-equivalent SBC / capped-call asset cannot also offset shares')
    common = x['class_a'] + x['class_b'] + x['class_c']
    if common <= 0 or abs(common - finite(x['reported_common_total'], 'reported common total', 0)) > 1e-6:
        raise ModelError('Class A+B+C must reconcile to common shares outstanding')
    diluted = common + x['incremental_non_sbc_shares']
    excess_cash = x['cash'] - x['minimum_operating_cash']
    assets = excess_cash + x['investments_net_tax'] + x['capped_calls_value']
    debt = x['notes_market_value'] + x['finance_lease_pv']
    all_equity = enterprise_value + assets - debt - x['minority_interest_value'] - x['other_claims_value']
    residual = all_equity - x['preferred_market_value']
    for name,value in (('assets',assets),('debt',debt),('equity',all_equity),('residual',residual),('shares',diluted)):
        finite(value,name)
    allocated_common = max(0, residual)
    return {'enterprise_value': enterprise_value, 'excess_cash': excess_cash,
            'nonoperating_assets_total': assets, 'financial_debt_market_value': debt,
            'minority_interest': x['minority_interest_value'], 'other_claims': x['other_claims_value'],
            'equity_before_preferred': all_equity, 'preferred_hybrid_claim': x['preferred_market_value'],
            'common_equity_residual': residual, 'common_equity_limited_liability': allocated_common,
            'common_shares': common, 'incremental_non_sbc_shares': x['incremental_non_sbc_shares'],
            'diluted_common_shares': diluted, 'value_per_common_share': allocated_common / diluted,
            'equity_deficit': max(0, -residual)}


def wacc_term_structure(x, assumptions, valuation_date, conversion_date):
    """Time-varying capital mix; split discounting in the legal conversion year.

    Preferred is priced as a full hybrid claim in today's equity bridge. Its WACC
    weight cannot remain forever after mandatory conversion. Reviewed paths are
    pre-event weights in the conversion year and actual target weights thereafter.
    Beta is an explicitly reviewed annual levered-risk path (not auto-relevered).
    """
    import calendar
    path_keys=('common_weight_path','debt_weight_path','preferred_weight_path','beta_path')
    if any(len(assumptions[k])!=5 for k in path_keys):
        raise ModelError('Five annual capital weights and betas required')
    shift=finite(assumptions['wacc_adjustment'],'WACC adjustment',-.1,.1)
    kd=wacc(x)['after_tax_cost_of_debt']
    rows=[]
    start=valuation_date
    for i in range(5):
        year=valuation_date.year+i+1
        end=date(year,valuation_date.month,min(valuation_date.day,calendar.monthrange(year,valuation_date.month)[1]))
        e,d,p=(rate(assumptions[k][i],k) for k in path_keys[:3])
        if abs(e+d+p-1)>1e-8: raise ModelError('Capital weights must sum to one')
        if start>=conversion_date and p!=0: raise ModelError('Preferred weight after mandatory conversion')
        if start<conversion_date and x['preferred_market_value']>0 and p<=0:
            raise ModelError('Missing preferred weight before conversion')
        beta=finite(assumptions['beta_path'][i],'annual beta',0,5)
        ke=x['risk_free']+beta*x['equity_risk_premium']+x['country_risk_premium']
        before=e*ke+d*kd+p*x['preferred_required_return']+shift
        after=(e+p)*ke+d*kd+shift
        fraction=max(0,min(1,(conversion_date-start).days/(end-start).days))
        if before<=0 or after<=0: raise ModelError('Non-positive annual WACC')
        effective=(1+before)**fraction*(1+after)**(1-fraction)-1
        rows.append({'year':i+1,'start':start.isoformat(),'end':end.isoformat(),
                     'pre_event_weights':{'common':e,'debt':d,'preferred':p},'beta':beta,
                     'preferred_fraction_of_year':fraction,'pre_conversion_wacc':before,
                     'post_conversion_wacc':after,'effective_wacc':effective})
        start=end
    if conversion_date>start:
        raise ModelError('Preferred extends beyond horizon: terminal model not supported')
    debt=rate(assumptions['terminal_debt_weight'],'terminal debt weight')
    beta=finite(assumptions['terminal_beta'],'terminal beta',0,5)
    ke=x['risk_free']+beta*x['equity_risk_premium']+x['country_risk_premium']
    terminal=(1-debt)*ke+debt*kd+shift
    if terminal<=0: raise ModelError('Non-positive terminal WACC')
    return {'annual_wacc':[r['effective_wacc'] for r in rows], 'periods':rows,
            'terminal_wacc':terminal,'terminal_preferred_weight':0,
            'conversion_date':conversion_date.isoformat()}


def project(revenue, base_nwc, tax, assumptions, discount, terminal_discount=None):
    finite(revenue, 'base revenue', 0)
    finite(base_nwc, 'base normalized operating NWC')
    rate(tax, 'operating tax')
    path = discount if isinstance(discount,list) else [discount]*5
    if len(path)!=5: raise ModelError('Five discount periods required')
    for value in path: finite(value,'discount',0)
    terminal_discount=path[-1] if terminal_discount is None else finite(terminal_discount,'terminal WACC',0)
    g = rate(assumptions['terminal_growth'], 'terminal growth')
    roic = finite(assumptions['terminal_roic'], 'terminal ROIC', 0.000001, 1)
    if terminal_discount <= g or roic <= g:
        raise ModelError('WACC and terminal ROIC must exceed terminal growth')
    keys = ('revenue_growth', 'ebit_margin', 'da_ratio', 'owned_capex_ratio', 'lease_capex_ratio', 'nwc_ratio')
    if any(len(assumptions[k]) != 5 for k in keys):
        raise ModelError('Exactly five explicit forecast years required')
    rows, pv, factor = [], 0, 1
    for year in range(5):
        growth = finite(assumptions['revenue_growth'][year], 'revenue growth', -0.99, 1)
        revenue *= 1 + growth
        margin = finite(assumptions['ebit_margin'][year], 'EBIT margin', -1, 1)
        ratios = {k: (finite(assumptions[k][year],k,-1,1) if k=='nwc_ratio' else rate(assumptions[k][year], k)) for k in keys[2:]}
        ebit = revenue * margin
        nopat = ebit - max(0, ebit) * tax
        da = revenue * ratios['da_ratio']
        capex = revenue * (ratios['owned_capex_ratio'] + ratios['lease_capex_ratio'])
        nwc = revenue * ratios['nwc_ratio']
        fcff = nopat + da - capex - (nwc - base_nwc)
        factor *= 1 + path[year]
        value = fcff / factor
        rows.append({'year': year + 1, 'wacc':path[year], 'discount_factor':factor, 'revenue': revenue, 'ebit': ebit, 'nopat': nopat,
                     'da': da, 'economic_capex': capex, 'operating_nwc': nwc,
                     'delta_nwc': nwc - base_nwc, 'fcff': fcff, 'present_value': value})
        base_nwc, pv = nwc, pv + value
    terminal_nopat = max(0, rows[-1]['ebit']) * (1 + g) * (1 - tax)
    if terminal_nopat <= 0:
        raise ModelError('A perpetual going-concern terminal requires positive mature NOPAT')
    terminal_reinvestment = terminal_nopat * g / roic
    terminal_fcff = terminal_nopat - terminal_reinvestment
    tv = terminal_fcff / (terminal_discount - g)
    pv_terminal = tv / factor
    ev = pv + pv_terminal
    finite(ev, 'enterprise value')
    return {'years': rows, 'present_value_explicit': pv, 'terminal_nopat': terminal_nopat,
            'terminal_reinvestment': terminal_reinvestment, 'terminal_fcff': terminal_fcff,
            'terminal_value': tv, 'terminal_wacc':terminal_discount, 'present_value_terminal': pv_terminal, 'enterprise_value': ev,
            'terminal_value_fraction': pv_terminal / ev if ev else None,
            'terminal_fcff_change_from_year5': terminal_fcff - rows[-1]['fcff'],
            'terminal_formula': 'NOPAT6*(1-g/ROIC)/(WACC-g)'}


def margin_of_safety(value, price):
    finite(value, 'value', 0)
    finite(price, 'quote', 0.000001)
    return (value - price) / value * 100 if value > 0 else None


# Every required input has a unit. Absence and explicit zero are different.
FINANCIAL_UNITS = {k: 'USD' for k in (
    'reported_ebit', 'reported_sbc', 'operating_da', 'ocf', 'cash_interest_in_ocf_including_leases',
    'revenue', 'cash', 'class_a_price', 'class_c_price', 'class_b_price',
    'notes_market_value', 'finance_lease_pv', 'preferred_market_value')}
FINANCIAL_UNITS.update({k: 'shares' for k in ('class_a','class_b','class_c','reported_common_total')})
ASSUMPTION_UNITS = {k:'USD' for k in (
    'normalized_sbc', 'sustainable_cash_capex', 'owned_capex_accrual_change',
    'capitalized_interest_in_capex', 'finance_lease_investment', 'normalized_delta_nwc',
    'nonoperating_cash_after_tax', 'reconciliation_tolerance', 'base_normalized_nwc',
    'minimum_operating_cash', 'investments_net_tax', 'capped_calls_value',
    'minority_interest_value', 'other_claims_value')}
ASSUMPTION_UNITS.update({k:'fraction' for k in (
    'operating_tax_rate', 'interest_tax_shield_rate', 'risk_free','equity_risk_premium',
    'country_risk_premium','notes_yield','finance_lease_yield','preferred_required_return','marginal_debt_tax_rate','finance_lease_tax_rate')})
ASSUMPTION_UNITS.update(beta='multiple', incremental_non_sbc_shares='shares')
SCENARIO_KEYS = ('revenue_growth','ebit_margin','da_ratio','owned_capex_ratio',
                 'lease_capex_ratio','nwc_ratio','terminal_growth','terminal_roic','wacc_adjustment',
                 'common_weight_path','debt_weight_path','preferred_weight_path','beta_path','terminal_beta','terminal_debt_weight')


def record_errors(record, name, unit, when, assumption=False, vector=False, instant=False):
    errors = []
    if not isinstance(record, dict):
        return [name + ':MISSING']
    values = record.get('value') if vector else [record.get('value')]
    if not isinstance(values, list) or (vector and len(values) != 5):
        return [name + ':INVALID_VECTOR']
    if any(isinstance(v, bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
        errors.append(name + ':MISSING_OR_NONFINITE_VALUE')
    if record.get('unit') != unit:
        errors.append(name + ':UNIT_MISMATCH')
    if not (record.get('source_url') or '').startswith('https://'):
        errors.append(name + ':SOURCE_REQUIRED')
    try:
        asof = date.fromisoformat(record['as_of'])
        age_limit = (5 if name.endswith('_price') or name=='risk_free' else 30 if name in ('notes_yield','finance_lease_yield','preferred_required_return','beta') else 150 if instant else 120 if assumption else 500)
        if not 0 <= (when - asof).days <= age_limit:
            errors.append(name + ':STALE_OR_FUTURE_SOURCE')
    except (TypeError, ValueError, KeyError):
        errors.append(name + ':DATE_REQUIRED')
    if assumption:
        if record.get('approved') is not True or not record.get('approved_by') or not record.get('rationale'):
            errors.append(name + ':FINANCIAL_APPROVAL_REQUIRED')
        try:
            age=(when-date.fromisoformat(record['approved_at'])).days
            if not 0 <= age <= 120: errors.append(name + ':APPROVAL_STALE_OR_FUTURE')
        except (KeyError,TypeError,ValueError): errors.append(name + ':APPROVAL_DATE_REQUIRED')
    elif record.get('validated') is not True:
        errors.append(name + ':SOURCE_VALIDATION_REQUIRED')
    if not assumption and not instant:
        if record.get('start') != '2025-10-01' or record.get('end') != '2026-09-30':
            errors.append(name + ':TTM_PERIOD_MISMATCH')
        if not record.get('components'):
            errors.append(name + ':TTM_COMPONENTS_REQUIRED')
    if not assumption and not instant and record.get('components'):
        try:
            components=record['components']
            annual,current,prior=(components[k] for k in ('annual','current_ytd','prior_ytd'))
            if len({item['unit'] for item in (annual,current,prior)}) != 1 or annual['unit'] != unit:
                raise ValueError('units')
            if len({item['tag'] for item in (annual,current,prior)}) != 1:
                raise ValueError('concepts')
            if (annual['start'],annual['end'],current['start'],current['end'],prior['start'],prior['end']) != (
                '2025-01-01','2025-12-31','2026-01-01','2026-09-30','2025-01-01','2025-09-30'):
                raise ValueError('periods')
            for item in (annual,current,prior):
                finite(item['value'],'component')
                if item.get('validated') is not True or not item.get('accession') or not (item.get('source_url') or '').startswith('https://www.sec.gov/Archives/'):
                    raise ValueError('provenance')
            if abs(record['value']-(annual['value']+current['value']-prior['value'])) > 1:
                raise ValueError('arithmetic')
        except (KeyError,ValueError,TypeError):
            errors.append(name+':TTM_COMPONENT_RECONCILIATION_FAILED')
    return errors


def evaluate(config):
    """Real-data boundary. Always research-only; approval never changes live policy.

    Report results only with every evidence/approval gate passed. Incomplete real
    configuration yields null scenarios and a complete actionable blocker list.
    """
    report = {'method':'FCFF_WACC', 'methodology_approved':config.get('methodology_approval',{}).get('approved') is True,
              'valuation_ready':False, 'production_valuation_enabled':False,
              'signal':'NO_SIGNAL', 'valuation_date':config.get('valuation_date'),
              'scenarios':{k:{'fair_value':None,'margin_of_safety_pct':None} for k in ('pessimistic','base','optimistic')},
              'blockers':[], 'calculation_ready':False, 'evidence':config}
    errors = report['blockers']
    try:
        when = date.fromisoformat(config['valuation_date'])
    except (KeyError,TypeError,ValueError):
        errors.append('VALUATION_DATE_REQUIRED')
        return report
    if not report['methodology_approved']: errors.append('METHODOLOGY_APPROVAL_REQUIRED')
    if config.get('currency') != 'USD' or config.get('methodology') != 'FCFF_WACC':
        errors.append('METHOD_OR_CURRENCY_MISMATCH')
    if config.get('financial_period') != {'start':'2025-10-01','end':'2026-09-30'}:
        errors.append('UNSUPPORTED_FINANCIAL_PERIOD_REFRESH_SOURCE_MAPPING')
    f, a = config.get('financials',{}), config.get('assumptions',{})
    instants = {'cash','class_a','class_b','class_c','reported_common_total','class_a_price',
                'class_b_price','class_c_price','notes_market_value','finance_lease_pv','preferred_market_value'}
    for name, unit in FINANCIAL_UNITS.items():
        errors.extend(record_errors(f.get(name),name,unit,when,instant=name in instants))
    for name, unit in ASSUMPTION_UNITS.items():
        errors.extend(record_errors(a.get(name),name,unit,when,assumption=True))
    # Policies are judgments, not inferred from SEC tags or global switches.
    expected = {'sbc':'cash_equivalent','finance_leases':'capitalized',
                'operating_leases':'operating_expense','preferred':'full_hybrid_claim',
                'capital_weights':'market_value','class_b_proxy':'explicit_reviewed_price'}
    for name, value in expected.items():
        policy = config.get('policies',{}).get(name,{})
        if policy.get('value') != value or policy.get('approved') is not True or not policy.get('rationale') or not policy.get('approved_by'):
            errors.append('POLICY_REVIEW_REQUIRED:' + name)
    for group in ('ebit_adjustments','after_tax_adjustments','ocf_adjustments'):
        rows = config.get(group)
        if not isinstance(rows,list) or config.get('adjustment_sets_reviewed',{}).get(group) is not True:
            errors.append('ADJUSTMENTS_REVIEW_REQUIRED:' + group)
        else:
            for row in rows:
                errors.extend(record_errors(row,group+':'+str(row.get('id')), 'USD',when,assumption=True))
    for scenario in report['scenarios']:
        inputs = config.get('scenario_assumptions',{}).get(scenario,{})
        for name in SCENARIO_KEYS:
            errors.extend(record_errors(inputs.get(name),scenario+':'+name,'multiple' if name in ('beta_path','terminal_beta') else 'fraction',when,
                                        assumption=True,vector=name in SCENARIO_KEYS[:6] or name.endswith('_path')))
    # Market value bridge explicitly requires claims valued as of the valuation date,
    # rather than silently relabelling an old SEC carrying amount as a current quote.
    capital_review = config.get('capital_rollforward_review',{})
    if capital_review.get('approved') is not True or capital_review.get('as_of') != config['valuation_date'] or not capital_review.get('rationale') or not capital_review.get('approved_by'):
        errors.append('CAPITAL_MARKET_VALUES_AND_DILUTION_ROLLFORWARD_REQUIRED')
    conversion=config.get('preferred_conversion_date',{})
    try:
        conversion_date=date.fromisoformat(conversion['value'])
        if not conversion.get('validated') or not (conversion.get('source_url') or '').startswith('https://www.sec.gov/Archives/'):
            raise ValueError('Unverified conversion date')
    except (KeyError,TypeError,ValueError):
        errors.append('PREFERRED_CONVERSION_DATE_REQUIRED')
    if errors:
        return report
    try:
        x = {k:v['value'] for k,v in {**f,**a}.items()}
        x.update({k:config[k] for k in ('ebit_adjustments','after_tax_adjustments','ocf_adjustments')})
        for cls in ('a','b','c'): finite(x['class_'+cls+'_price'],'class price',0.000001)
        if len({f['class_'+cls+'_price']['as_of'] for cls in ('a','b','c')})!=1:
            raise ModelError('Class prices must refer to the same date')
        primary = normalized_fcff(x)
        bridge = ocf_fcff_bridge(x,primary)
        if not bridge['reconciled']:
            raise ModelError('CFO_TO_EBIT_FCFF_DOES_NOT_RECONCILE')
        x.update(common_market_value=sum(x['class_'+c] * x['class_'+c+'_price'] for c in ('a','b','c')),
                 debt_market_value=x['notes_market_value']+x['finance_lease_pv'],
                 preferred_treatment='full_hybrid_claim',preferred_conversion_shares=0,
                 future_sbc_dilution_rate=0,capped_call_share_offset=0)
        cost = wacc(x)
        report['normalization'] = primary
        report['ocf_reconciliation'] = bridge
        report['wacc'] = cost
        candidate_results = {}
        for scenario in report['scenarios']:
            assumptions={k:config['scenario_assumptions'][scenario][k]['value'] for k in SCENARIO_KEYS}
            terms=wacc_term_structure(x,assumptions,when,conversion_date)
            discount=terms['annual_wacc']
            forecast=project(x['revenue'],x['base_normalized_nwc'],x['operating_tax_rate'],assumptions,discount,terms['terminal_wacc'])
            equity=capital_bridge(forecast['enterprise_value'],x)
            sensitivity=[]
            # Explicitly approved scenario rates; sensitivities are stresses, not new forecasts.
            for d in (-.01,0,.01):
                for g in (-.005,0,.005):
                    stress={**assumptions,'terminal_growth':assumptions['terminal_growth']+g}
                    try:
                        ev=project(x['revenue'],x['base_normalized_nwc'],x['operating_tax_rate'],stress,[w+d for w in discount],terms['terminal_wacc']+d)['enterprise_value']
                        value=capital_bridge(ev,x)['value_per_common_share']
                        sensitivity.append({'wacc_shift':d,'terminal_wacc':terms['terminal_wacc']+d,'g':stress['terminal_growth'],'value_per_share':value})
                    except ModelError as error:
                        sensitivity.append({'wacc_shift':d,'terminal_wacc':terms['terminal_wacc']+d,'g':stress['terminal_growth'],'value_per_share':None,'error':str(error)})
            candidate_results[scenario]={'forecast':forecast,'equity_bridge':equity,'wacc_term_structure':terms,
                'model_value_per_share':equity['value_per_common_share'],
                'model_margin_of_safety_pct':margin_of_safety(equity['value_per_common_share'],x['class_a_price']),
                'sensitivity':sensitivity}
        values=[candidate_results[k]['model_value_per_share'] for k in ('pessimistic','base','optimistic')]
        if values!=sorted(values): raise ModelError('SCENARIOS_NOT_ORDERED_REVIEW_ASSUMPTIONS')
        # This private review result is never mapped to production fair_value or signals.
        report['review_calculations']=candidate_results
        report['calculation_ready']=True
    except (ModelError,KeyError,TypeError,OverflowError) as error:
        errors.append('MODEL_INVALID:' + str(error))
        report.pop('review_calculations',None)
        report['calculation_ready']=False
    return report
