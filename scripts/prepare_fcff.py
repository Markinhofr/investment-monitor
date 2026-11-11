"""Reproducible, read-only-source preparation. Outputs unapproved review files only.

python -m scripts.prepare_fcff --annual-html work/annual.html --quarter-html work/quarter.html
Original reports are downloaded separately, with SEC-compatible identification.
This command never contacts Telegram, modifies live policy, or publishes a site.
"""
import argparse
import json
from datetime import date
from pathlib import Path
from src.fcff_model import FINANCIAL_UNITS, ASSUMPTION_UNITS, SCENARIO_KEYS, evaluate
from src.sec_filing_evidence import read_filing, ttm

Q_URL='https://www.sec.gov/Archives/edgar/data/1652044/000165204426000084/goog-20260930.htm'
A_URL='https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm'


def pending(unit, source=None):
    return {'value':None,'unit':unit,'as_of':None,'source_url':source,
            'approved':False,'approved_by':None,'approved_at':None,'rationale':None}


def prepare(annual_path,quarter_path,valuation_date,fetch_quotes=False):
    annual=read_filing(annual_path,A_URL,'0001652044-26-000018','2026-02-05')
    quarter=read_filing(quarter_path,Q_URL,'0001652044-26-000084','2026-10-29')
    # Checksums identify exact original documents; no approval is implied by extraction.
    financials={k:{**pending(unit),'validated':False} for k,unit in FINANCIAL_UNITS.items()}
    tags={'reported_ebit':'OperatingIncomeLoss','reported_sbc':'ShareBasedCompensation',
          'ocf':'NetCashProvidedByUsedInOperatingActivities','revenue':'Revenues',
          'depreciation_ppe':'Depreciation','intangible_amortization':'AmortizationOfIntangibleAssets',
          'interest_expense_recognized':'InterestExpenseNonoperating',
          'cash_interest_finance_leases':'FinanceLeaseInterestPaymentOnLiability',
          'interest_capitalized':'InterestCostsCapitalized',
          'finance_lease_new_rou':'RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability',
          'cash_capex':'PaymentsToAcquirePropertyPlantAndEquipment'}
    evidence={}
    for key,tag in tags.items():
        values={'annual':annual.select('us-gaap:'+tag,'2025-01-01','2025-12-31'),
                'current_ytd':quarter.select('us-gaap:'+tag,'2026-01-01','2026-09-30'),
                'prior_ytd':quarter.select('us-gaap:'+tag,'2025-01-01','2025-09-30')}
        result=ttm(values['annual'],values['current_ytd'],values['prior_ytd'])
        evidence[key]={'periods':values,'ttm':result}
        if key in financials and result:
            financials[key]=result
    instant_tags={'cash':'CashAndCashEquivalentsAtCarryingValue',
                  'notes_market_value':'LongTermDebtFairValue','finance_lease_pv':'FinanceLeaseLiability',
                  'reported_common_total':'CommonStockSharesOutstanding'}
    for key,tag in instant_tags.items():
        value=quarter.select('us-gaap:'+tag,None,'2026-09-30',FINANCIAL_UNITS[key])
        if value:financials[key]=value
    for cls in ('a','b','c'):
        value=quarter.select('us-gaap:CommonStockSharesOutstanding',None,'2026-09-30','shares',
                             members=('us-gaap:CommonClass'+cls.upper()+'Member',))
        if value:financials['class_'+cls]=value
    if fetch_quotes:
        from src.monitor import quote
        for cls,ticker in (('a','GOOGL'),('c','GOOG')):
            try:
                q=quote(ticker)
                if q['currency'] != 'USD':raise ValueError('Quote currency')
                financials['class_'+cls+'_price']={'value':q['price'],'unit':'USD','as_of':q['as_of'][:10],
                    'source_url':q['source'],'validated':True,'type':q['type'],'ticker':ticker}
            except Exception as error:
                financials['class_'+cls+'_price']['error']=type(error).__name__
    assumptions={k:pending(unit) for k,unit in ASSUMPTION_UNITS.items()}
    assumptions['risk_free']['source_url']='https://home.treasury.gov/resource-center-data-chart-center/interest-rates'
    policies={k:{'value':v,'approved':False,'approved_by':None,'rationale':None} for k,v in {
        'sbc':'cash_equivalent','finance_leases':'capitalized','operating_leases':'operating_expense',
        'preferred':'full_hybrid_claim','capital_weights':'market_value','class_b_proxy':'explicit_reviewed_price'}.items()}
    config={'methodology':'FCFF_WACC','methodology_approval':{'approved':True,'scope':'method only','source':'explicit user instruction 2026-11-11'},
            'valuation_date':valuation_date,'financial_period':{'start':'2025-10-01','end':'2026-09-30'},
            'currency':'USD','financials':financials,'assumptions':assumptions,'policies':policies,
            'capital_rollforward_review':{'approved':False,'approved_by':None,'as_of':None,'rationale':None},
            'ebit_adjustments':[],'after_tax_adjustments':[],'ocf_adjustments':[],
            'adjustment_sets_reviewed':{'ebit_adjustments':False,'after_tax_adjustments':False,'ocf_adjustments':False},
            'preferred_conversion_date':{'value':'2029-05-15','source_url':Q_URL,'validated':True,'note':'Note 11: on or about; early/special conversion is a separate scenario risk'},
            'scenario_assumptions':{scenario:{k:pending('multiple' if k in ('beta_path','terminal_beta') else 'fraction') for k in SCENARIO_KEYS}
                                    for scenario in ('pessimistic','base','optimistic')}}
    manifest={'sources':[{'url':A_URL,'sha256':annual.document_sha256,'accession':annual.accession},
                         {'url':Q_URL,'sha256':quarter.document_sha256,'accession':quarter.accession}],
              'extraction_is_not_financial_approval':True,'duration_evidence':evidence}
    return config,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annual-html',type=Path,required=True)
    parser.add_argument('--quarter-html',type=Path,required=True)
    parser.add_argument('--valuation-date',default=date.today().isoformat())
    parser.add_argument('--fetch-quotes',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=Path('work/fcff'))
    args=parser.parse_args()
    # Keep preparatory results out of Pages/active financial configuration.
    out=args.output_dir.resolve()
    root=Path(__file__).resolve().parents[1]
    if out==root or out.is_relative_to(root/'docs') or out.is_relative_to(root/'src') or out==root/'data':
        raise SystemExit('Use a separate work directory for review outputs')
    config,manifest=prepare(args.annual_html,args.quarter_html,args.valuation_date,args.fetch_quotes)
    out.mkdir(parents=True,exist_ok=True)
    for name,value in (('inputs.json',config),('sec_evidence.json',manifest),('review_report.json',evaluate(config))):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('Prepared evidence and unapproved model inputs:',out)


if __name__=='__main__':main()
