"""All numeric fixtures below are SYNTHETIC unit-test inputs, never Alphabet estimates."""
import copy
import math
import unittest
from src.fcff_model import (ModelError, normalized_fcff, ocf_fcff_bridge, wacc,
    capital_bridge, project, margin_of_safety, evaluate, FINANCIAL_UNITS, ASSUMPTION_UNITS, SCENARIO_KEYS)


def normal_inputs():
    return {'reported_ebit':100,'reported_sbc':20,'normalized_sbc':25,'operating_da':10,
            'operating_tax_rate':.2,'sustainable_cash_capex':15,'owned_capex_accrual_change':3,
            'capitalized_interest_in_capex':1,'finance_lease_investment':2,'normalized_delta_nwc':4,
            'ebit_adjustments':[],'after_tax_adjustments':[],
            'ocf':105,'cash_interest_in_ocf_including_leases':10,'interest_tax_shield_rate':.2,
            'nonoperating_cash_after_tax':5,'ocf_adjustments':[{'id':'tax-and-nwc-review','value':-1}],
            'reconciliation_tolerance':.01}


def capital_inputs():
    return {'cash':20,'minimum_operating_cash':5,'investments_net_tax':30,'capped_calls_value':2,
            'notes_market_value':40,'finance_lease_pv':10,'preferred_market_value':15,
            'minority_interest_value':4,'other_claims_value':3,
            'class_a':5,'class_b':1,'class_c':4,'reported_common_total':10,'incremental_non_sbc_shares':1,
            'preferred_treatment':'full_hybrid_claim','preferred_conversion_shares':0,
            'future_sbc_dilution_rate':0,'capped_call_share_offset':0}


def projections():
    return {'revenue_growth':[.05]*5,'ebit_margin':[.3]*5,'da_ratio':[.05]*5,
            'owned_capex_ratio':[.08]*5,'lease_capex_ratio':[.01]*5,'nwc_ratio':[.1]*5,
            'terminal_growth':.02,'terminal_roic':.1,'wacc_adjustment':0,
            'common_weight_path':[.7,.7,.7,.8,.8],'debt_weight_path':[.2]*5,
            'preferred_weight_path':[.1,.1,.1,0,0],'beta_path':[1]*5,
            'terminal_beta':1,'terminal_debt_weight':.2}


class FCFFTests(unittest.TestCase):
    def test_fcff_is_not_ocf_minus_capex(self):
        x=normal_inputs();p=normalized_fcff(x)
        self.assertEqual(p['normalized_ebit'],95) # replace SBC, never subtract twice
        self.assertEqual(p['nopat'],76)
        self.assertEqual(p['economic_capex'],19) # 15+3-1+2
        self.assertEqual(p['fcff'],63) # 76+10-19-4
        self.assertNotEqual(p['fcff'],x['ocf']-x['sustainable_cash_capex'])
    def test_independent_cash_flow_bridge(self):
        x=normal_inputs();p=normalized_fcff(x)
        # 105 + 8 - 5 -25 -19 -1 =63
        bridge=ocf_fcff_bridge(x,p)
        self.assertEqual(bridge['fcff'],63)
        self.assertTrue(bridge['reconciled'])
    def test_discrepancy_is_not_used_as_a_plug(self):
        x=normal_inputs();p=normalized_fcff(x)
        x['ocf']+=10
        b=ocf_fcff_bridge(x,p)
        self.assertFalse(b['reconciled']);self.assertEqual(b['difference_from_ebit_route'],10)
    def test_no_automatic_refund_on_losses(self):
        x=normal_inputs();x['reported_ebit']=-100
        self.assertEqual(normalized_fcff(x)['operating_tax'],0)
    def test_missing_lease_investment_not_zero(self):
        x=normal_inputs();x['finance_lease_investment']=None
        with self.assertRaises(ModelError):normalized_fcff(x)
    def test_adjustments_need_unique_ids(self):
        x=normal_inputs();x['ebit_adjustments']=[{'id':'same','value':1}]*2
        with self.assertRaises(ModelError):normalized_fcff(x)
    def test_negative_working_capital_is_valid(self):
        a=project(100,-10,.2,{**projections(),'nwc_ratio':[-.1]*5},.1)
        self.assertLess(a['years'][0]['delta_nwc'],0)
    def test_finite_inputs_and_tax_bounds(self):
        for invalid in (True,None,float('nan'),float('inf')):
            x=normal_inputs();x['operating_tax_rate']=invalid
            with self.assertRaises(ModelError):normalized_fcff(x)
        x=normal_inputs();x['operating_tax_rate']=1.2
        with self.assertRaises(ModelError):normalized_fcff(x)


class WACCTests(unittest.TestCase):
    def inputs(self):
        return {'risk_free':.04,'beta':1.2,'equity_risk_premium':.05,'country_risk_premium':0,
                'notes_yield':.06,'finance_lease_yield':.06,'finance_lease_tax_rate':.25,'notes_market_value':250,'finance_lease_pv':50,'marginal_debt_tax_rate':.25,'preferred_required_return':.08,
                'common_market_value':600,'debt_market_value':300,'preferred_market_value':100}
    def test_market_weighted_hybrid_wacc(self):
        x=wacc(self.inputs())
        self.assertAlmostEqual(x['cost_of_equity'],.10)
        self.assertAlmostEqual(x['wacc'],.6*.1+.3*.06*.75+.1*.08)
        self.assertAlmostEqual(sum(x['weights'].values()),1)
    def test_hybrid_return_not_assumed_coupon(self):
        x=self.inputs();a=wacc(x)['wacc'];x['preferred_required_return']=.1
        self.assertGreater(wacc(x)['wacc'],a)
    def test_invalid_values(self):
        for field,val in [('debt_market_value',-1),('beta',float('nan')),('common_market_value',0)]:
            x=self.inputs();x[field]=val
            with self.assertRaises(ModelError):wacc(x)


class EquityAndProjectionTests(unittest.TestCase):
    def test_enterprise_to_common_bridge(self):
        b=capital_bridge(200,capital_inputs())
        # 200+15+30+2-40-10-4-3-15=175; 5+1+4+1=11 shares.
        self.assertEqual(b['common_equity_residual'],175)
        self.assertAlmostEqual(b['value_per_common_share'],175/11)
        self.assertEqual(b['financial_debt_market_value'],50)
    def test_no_preferred_claim_and_conversion_double_count(self):
        x=capital_inputs();x['preferred_conversion_shares']=5
        with self.assertRaises(ModelError):capital_bridge(200,x)
    def test_no_sbc_cost_and_future_dilution_double_count(self):
        x=capital_inputs();x['future_sbc_dilution_rate']=.02
        with self.assertRaises(ModelError):capital_bridge(200,x)
    def test_capped_call_asset_cannot_also_reduce_shares(self):
        x=capital_inputs();x['capped_call_share_offset']=1
        with self.assertRaises(ModelError):capital_bridge(200,x)
    def test_class_sum_and_operating_cash_checks(self):
        for key,val in [('reported_common_total',9),('minimum_operating_cash',21)]:
            x=capital_inputs();x[key]=val
            with self.assertRaises(ModelError):capital_bridge(200,x)
    def test_limited_liability_preserves_deficit_reconciliation(self):
        b=capital_bridge(-100,capital_inputs())
        self.assertEqual(b['value_per_common_share'],0)
        self.assertGreater(b['equity_deficit'],0)
    def test_terminal_reinvestment_is_not_free_growth(self):
        p=project(100,10,.2,projections(),.1)
        self.assertAlmostEqual(p['terminal_fcff'],p['terminal_nopat']*(1-.02/.1))
        self.assertAlmostEqual(p['enterprise_value'],p['present_value_explicit']+p['present_value_terminal'])
    def test_more_discount_reduces_value(self):
        self.assertGreater(project(100,10,.2,projections(),.09)['enterprise_value'],
                           project(100,10,.2,projections(),.11)['enterprise_value'])
    def test_terminal_and_horizon_validation(self):
        for change in ({'terminal_growth':.1},{'terminal_roic':.01},{'revenue_growth':[.1]*4}):
            with self.assertRaises(ModelError):project(100,10,.2,{**projections(),**change},.1)
    def test_margin_of_safety(self):
        self.assertEqual(margin_of_safety(100,75),25)
        self.assertEqual(margin_of_safety(100,120),-20)
        self.assertIsNone(margin_of_safety(0,75))


def approved_fixture():
    """Deliberately fictional evidence and approvals, for testing only."""
    from datetime import date
    when='2026-11-11'
    def record(value,unit,assumption=False,instant=False):
        r={'value':value,'unit':unit,'as_of':when,'source_url':'https://www.sec.gov/Archives/SYNTHETIC-TEST',
           'validated':True,'approved':True,'approved_by':'UNIT TEST ONLY','approved_at':when,
           'rationale':'SYNTHETIC TEST FIXTURE; not real Alphabet data'}
        if not assumption and not instant:
            r.update(start='2025-10-01',end='2026-09-30')
            r['components']={}
            for key,start,end in [('annual','2025-01-01','2025-12-31'),('current_ytd','2026-01-01','2026-09-30'),('prior_ytd','2025-01-01','2025-09-30')]:
                r['components'][key]={'value':value,'unit':unit,'start':start,'end':end,
                    'validated':True,'accession':'synthetic-'+key,'source_url':r['source_url'],'tag':'TEST'}
        return r
    x={**normal_inputs(),**capital_inputs(),'revenue':200,'class_a_price':20,'class_b_price':20,'class_c_price':20,
       'risk_free':.04,'beta':1,'equity_risk_premium':.05,'country_risk_premium':0,'notes_yield':.05,'finance_lease_yield':.04,'finance_lease_tax_rate':.2,
       'preferred_required_return':.08,'marginal_debt_tax_rate':.2,'base_normalized_nwc':20}
    instant={'cash','class_a','class_b','class_c','reported_common_total','class_a_price',
             'class_b_price','class_c_price','notes_market_value','finance_lease_pv','preferred_market_value'}
    c={'methodology':'FCFF_WACC','currency':'USD','valuation_date':when,
       'methodology_approval':{'approved':True,'scope':'method only'},
       'financial_period':{'start':'2025-10-01','end':'2026-09-30'},
       'financials':{k:record(x[k],u,instant=k in instant) for k,u in FINANCIAL_UNITS.items()},
       'assumptions':{k:record(x[k],u,True) for k,u in ASSUMPTION_UNITS.items()},
       'scenario_assumptions':{s:{k:record(v,'multiple' if k in ('beta_path','terminal_beta') else 'fraction',True) for k,v in projections().items()} for s in ('pessimistic','base','optimistic')},
       'preferred_conversion_date':{'value':'2029-05-15','validated':True,'source_url':'https://www.sec.gov/Archives/SYNTHETIC-TEST'},
       'capital_rollforward_review':{'approved':True,'as_of':when,'approved_by':'UNIT TEST ONLY','rationale':'Synthetic'},
       'policies':{k:{'value':v,'approved':True,'approved_by':'UNIT TEST ONLY','rationale':'Synthetic'} for k,v in {
          'sbc':'cash_equivalent','finance_leases':'capitalized','operating_leases':'operating_expense',
          'preferred':'full_hybrid_claim','capital_weights':'market_value','class_b_proxy':'explicit_reviewed_price'}.items()},
       'adjustment_sets_reviewed':{'ebit_adjustments':True,'after_tax_adjustments':True,'ocf_adjustments':True}}
    for group in c['adjustment_sets_reviewed']:
        c[group]=[{**record(row['value'],'USD',True),'id':row['id']} for row in x[group]]
    return c


class ApprovalBoundaryTests(unittest.TestCase):
    def test_complete_synthetic_model_never_enables_production(self):
        result=evaluate(approved_fixture())
        self.assertEqual(result['blockers'],[])
        self.assertTrue(result['calculation_ready'])
        self.assertFalse(result['valuation_ready'])
        self.assertFalse(result['production_valuation_enabled'])
        self.assertEqual(result['signal'],'NO_SIGNAL')
        self.assertTrue(all(x['fair_value'] is None for x in result['scenarios'].values()))
        self.assertEqual(len(result['review_calculations']['base']['sensitivity']),9)
    def test_single_missing_input_blocks_all_values(self):
        c=approved_fixture();c['assumptions']['risk_free']['value']=None
        r=evaluate(c)
        self.assertTrue(r['blockers']);self.assertNotIn('review_calculations',r)
    def test_method_approval_not_financial_approval(self):
        c=approved_fixture();c['assumptions']['operating_tax_rate']['approved']=False
        self.assertFalse(evaluate(c)['calculation_ready'])
    def test_future_and_stale_quote_rejected(self):
        for when in ('2026-11-12','2020-01-01'):
            c=approved_fixture();c['financials']['class_a_price']['as_of']=when
            self.assertTrue(evaluate(c)['blockers'])
    def test_mismatched_currency_and_ttm_rejected(self):
        for update in ({'unit':'EUR'},{'start':'2024-10-01'},{'value':9999}):
            c=approved_fixture();c['financials']['reported_ebit'].update(update)
            self.assertTrue(evaluate(c)['blockers'])
    def test_unexplained_cash_flow_difference_blocks_model(self):
        c=approved_fixture()
        # Keep the source arithmetic consistent, but the CFO/EBIT cash bridge inconsistent.
        record=c['financials']['ocf'];record['value']=115
        for item in record['components'].values():item['value']=115
        r=evaluate(c)
        self.assertIn('MODEL_INVALID:CFO_TO_EBIT_FCFF_DOES_NOT_RECONCILE',r['blockers'])
    def test_boolean_is_not_a_number(self):
        c=approved_fixture();c['assumptions']['beta']['value']=True
        self.assertTrue(evaluate(c)['blockers'])
    def test_missing_explicit_zero_not_defaulted(self):
        c=approved_fixture();del c['assumptions']['country_risk_premium']
        self.assertTrue(evaluate(c)['blockers'])

class ConversionTermStructureTests(unittest.TestCase):
    def inputs(self):
        c=approved_fixture()
        x={k:v['value'] for k,v in {**c['financials'],**c['assumptions']}.items()}
        x['common_market_value']=200
        x['debt_market_value']=x['notes_market_value']+x['finance_lease_pv']
        return x
    def test_conversion_year_discount_is_split(self):
        from src.fcff_model import wacc_term_structure
        from datetime import date
        r=wacc_term_structure(self.inputs(),projections(),date(2026,11,11),date(2029,5,15))
        self.assertGreater(r['periods'][2]['preferred_fraction_of_year'],0)
        self.assertLess(r['periods'][2]['preferred_fraction_of_year'],1)
        self.assertEqual(r['terminal_preferred_weight'],0)
        self.assertEqual(r['periods'][3]['preferred_fraction_of_year'],0)
        row=r['periods'][2];f=row['preferred_fraction_of_year']
        self.assertAlmostEqual(row['effective_wacc'],(1+row['pre_conversion_wacc'])**f*(1+row['post_conversion_wacc'])**(1-f)-1)
    def test_perpetual_preferred_weight_rejected(self):
        from src.fcff_model import wacc_term_structure
        from datetime import date
        p=projections();p['preferred_weight_path']=[.1]*5;p['common_weight_path']=[.7]*5
        with self.assertRaises(ModelError):wacc_term_structure(self.inputs(),p,date(2026,11,11),date(2029,5,15))
    def test_weights_must_sum_to_one(self):
        from src.fcff_model import wacc_term_structure
        from datetime import date
        p=projections();p['common_weight_path']=[.9]*5
        with self.assertRaises(ModelError):wacc_term_structure(self.inputs(),p,date(2026,11,11),date(2029,5,15))
    def test_nonconstant_wacc_discount_factors_compound(self):
        path=[.08,.09,.10,.11,.12]
        p=project(100,10,.2,projections(),path,.1)
        product=1
        for row,w in zip(p['years'],path):
            product*=1+w
            self.assertAlmostEqual(row['discount_factor'],product)
        self.assertAlmostEqual(p['present_value_terminal'],p['terminal_value']/product)

class ProductionIsolationTests(unittest.TestCase):
    def test_approved_research_fixture_does_not_unlock_live_monitor(self):
        import json, os, shutil, subprocess, tempfile
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temporary=Path(directory)
            for name in ('src','data','docs'):
                shutil.copytree(root/name,temporary/name)
            (temporary/'data/fcff_inputs.json').write_text(json.dumps(approved_fixture()))
            result=subprocess.run(['python','-m','src.monitor'],cwd=temporary,
                env={**os.environ,'REPORT_MODE':'daily','OFFLINE_TEST':'1'},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((temporary/'docs/latest.json').read_text())
            self.assertFalse(report['alphabet']['valuation_ready'])
            self.assertTrue(all(x['fair_value'] is None for x in report['positions']))
            self.assertIs(json.loads((temporary/'data/valuation_policy.json').read_text())['valuation_enabled'],False)
