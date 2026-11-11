import copy
import datetime as dt
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.research import analyze as core_analyze, collect, load_policy


def analyze(data, review, now=None):
    return core_analyze(data, review, now, policy={"valuation_enabled": True})
from src.dcf import calculate_dcf
from src.fundamentals_fetcher import calculate_ttm, balance_sheet, candidates, get_sec_data
from src.monitor import assess, quote, notification_message, telegram

NOW = dt.date(2026, 11, 10)

def fixture():
    def record(value, unit='USD', start=None):
        return {'value':value, 'unit':unit, 'start':start, 'end':'2026-09-30',
                'filed':'2026-10-28', 'accession':'test-filing'}
    data = {'balance_sheet':{'cash':record(50), 'current_debt':record(10),
                            'noncurrent_debt':record(20), 'shares':record(10, 'shares')},
            'ttm_operating_cash_flow':{'value':150,'end':'2026-09-30', 'sources':{}},
            'ttm_capex':{'value':50,'end':'2026-09-30', 'sources':{}}}
    for key, value in (('ttm_operating_cash_flow',150),('ttm_capex',50)):
        annual=record(value,start='2025-01-01'); annual['end']='2025-12-31'
        current=record(value,start='2026-01-01')
        prior=record(value,start='2025-01-01'); prior['end']='2025-09-30'
        data[key]['sources']={'annual':annual,'current_ytd':current,'prior_ytd':prior}
    data['capital_structure'] = {'preferred_shares':record(0, 'shares'), 'finance_lease_liability':record(0)}
    review = {'cash_flow_methodology_approved':True, 'methodology_rationale':'Synthetic unit fixture', 'period_end':'2026-09-30','accession':'test-filing','reviewed_by':'fixture',
              'source_url':'https://www.sec.gov/Archives/test', 'reviewed_at':'2026-11-01',
              'all_share_classes_confirmed':True,'debt_scope_confirmed':True,
              'extraordinary_cash_flows_reviewed':True,'assumptions_approved':True,
              'normalized_fcf':80,'normalization_rationale':'fixture: exclude non recurring cash inflow'}
    return data, review

class ResearchTests(unittest.TestCase):
    def test_valid_scenarios_and_net_cash(self):
        report = analyze(*fixture(), now=NOW)
        self.assertTrue(report['valuation_ready'], report['errors'])
        self.assertEqual(report['net_debt'], -20)
        self.assertEqual(report['fcf_ttm']['value'],100)
        self.assertEqual(report['fcf_normalized']['value'],80)
        values = [report['scenarios'][x]['fair_value'] for x in ('pessimistic','base','optimistic')]
        self.assertEqual(values, sorted(values))
    def test_missing_and_invalid_inputs_block_all_scenarios(self):
        for name in ('cash','current_debt','noncurrent_debt','shares'):
            data, review = fixture()
            data['balance_sheet'][name] = None
            report = analyze(data, review, NOW)
            self.assertFalse(report['valuation_ready'])
            self.assertTrue(all(x['fair_value'] is None for x in report['scenarios'].values()))
    def test_review_expires_when_filing_changes(self):
        data, review = fixture()
        review['accession'] = 'old'
        self.assertFalse(analyze(data,review,NOW)['valuation_ready'])
    def test_unreviewed_extraordinary_gains_block(self):
        data,review=fixture()
        review['extraordinary_cash_flows_reviewed']=False
        self.assertFalse(analyze(data,review,NOW)['valuation_ready'])
    def test_normalized_fcf_cannot_exceed_ttm(self):
        data,review=fixture()
        review['normalized_fcf']=200
        self.assertFalse(analyze(data,review,NOW)['valuation_ready'])
    def test_mismatched_period_and_stale_data(self):
        data,review=fixture()
        data['ttm_capex']['sources']['annual']['start']='2024-01-01'
        self.assertFalse(analyze(data,review,NOW)['valuation_ready'])
        self.assertFalse(analyze(*fixture(),now=dt.date(2027,12,1))['valuation_ready'])
    def test_api_failure_has_no_old_valuation(self):
        with patch('src.research.fetch_alphabet',side_effect=urllib.error.HTTPError('SEC',429,'rate',{},None)):
            report=collect({})
        self.assertEqual(report['data_status'],'DATA_UNAVAILABLE')
        self.assertIsNone(report['fcf_ttm']['value'])
    def test_finite_dcf_inputs(self):
        for invalid in (float('nan'),float('inf'),True,None):
            with self.assertRaises(ValueError):
                calculate_dcf(invalid,0,10,.05,.1,.02)
    def test_sec_requires_contact(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(RuntimeError):get_sec_data()
    def test_missing_debt_is_not_zero(self):
        self.assertEqual(balance_sheet({}),{})
    def test_nan_sec_values_ignored(self):
        facts={'Cash':{'units':{'USD':[{'val':float('nan'),'form':'10-Q','end':'2026-09-30','filed':'2026-10-28'}]}}}
        self.assertEqual(candidates(facts,['Cash']),[])
    def test_quote_api_error(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):quote('GOOGL')
    def test_empty_quote_payload(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{"chart":{"result":[]}}'
        with patch('urllib.request.urlopen',return_value=response):
            with self.assertRaises((ValueError,IndexError)):quote('GOOGL')
    def test_new_filing_notification_and_unchanged_suppression(self):
        now=dt.datetime.now(dt.timezone.utc)
        previous={'positions':[], 'alphabet':{'accession':'old','data_status':'VALIDATION_PENDING'}}
        current={'positions':[], 'alphabet':{'accession':'new','period_end':'2026-09-30','data_status':'VALIDATION_PENDING'}}
        self.assertIn('nova demonstração SEC', notification_message(current,previous,'daily',now))
        self.assertIsNone(notification_message(current,current,'daily',now))
    def test_no_telegram_without_secrets(self):
        with patch.dict('os.environ',{},clear=True),patch('urllib.request.urlopen') as call:
            self.assertEqual(telegram('test'),'not_configured')
            call.assert_not_called()
    def test_stale_price_and_currency_mismatch(self):
        today=dt.datetime.now(dt.timezone.utc).isoformat()
        fv={'value':100,'currency':'USD','verified':True,'valuation_ready':True,'as_of':today,'source_url':'https://www.sec.gov/'}
        self.assertIsNone(assess({'price':50,'as_of':'2020-01-01','currency':'USD'},fv)['discount_pct'])
        self.assertIsNone(assess({'price':50,'as_of':today,'currency':'EUR'},fv)['discount_pct'])

class DeliveryTests(unittest.TestCase):
    def run_delivery(self, status, existing=None):
        import src.monitor as monitor
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root=Path(self.directory.name)
        (root/'data').mkdir()
        path=root/'data/notification_state.json'
        if existing:
            path.write_text(json.dumps(existing))
        report={'positions':[], 'alphabet':{'accession':'new','period_end':'2026-09-30','data_status':'VALIDATED'}}
        with patch.object(monitor,'ROOT',root),patch.object(monitor,'build',return_value=report), \
             patch.object(monitor,'telegram',return_value=status) as send, \
             patch.dict('os.environ',{'REPORT_MODE':'daily','OFFLINE_TEST':'0'}):
            if status=='failed':
                with self.assertRaises(RuntimeError):monitor.main()
            else:
                monitor.main()
                if status=='sent':
                    monitor.main()
                    self.assertEqual(send.call_count,1)
        return path
    def test_delivery_failure_does_not_advance_state(self):
        original={'report':{'positions':[], 'alphabet':{'accession':'old','data_status':'VALIDATED'}}}
        path=self.run_delivery('failed',original)
        self.assertEqual(json.loads(path.read_text()),original)
    def test_successful_delivery_deduplicates_next_run(self):
        path=self.run_delivery('sent')
        self.assertEqual(json.loads(path.read_text())['report']['alphabet']['accession'],'new')
    def test_offline_never_sends(self):
        import src.monitor as monitor
        with tempfile.TemporaryDirectory() as directory,patch.object(monitor,'ROOT',Path(directory)), \
             patch.object(monitor,'build',return_value={'positions':[],'alphabet':{}}), \
             patch.object(monitor,'telegram') as send, \
             patch.dict('os.environ',{'REPORT_MODE':'daily','OFFLINE_TEST':'1'}):
            monitor.main()
            send.assert_not_called()


class ProductionSafetyTests(unittest.TestCase):
    def test_missing_policy_blocks_even_reviewed_data(self):
        report = core_analyze(*fixture(), now=NOW)
        self.assertFalse(report['valuation_ready'])
        self.assertIn('VALUATION_DISABLED_BY_POLICY', report['errors'])
    def test_preferred_stock_blocks_even_with_attestation(self):
        data, review = fixture()
        data['capital_structure']['preferred_shares']['value'] = 19_000_000
        report = analyze(data, review, NOW)
        self.assertIn('UNSUPPORTED_PREFERRED_STOCK', report['errors'])
        self.assertTrue(all(s['fair_value'] is None for s in report['scenarios'].values()))
    def test_finance_leases_require_model_decision(self):
        data, review = fixture()
        data['capital_structure']['finance_lease_liability']['value'] = 3_705_000_000
        self.assertIn('LEASE_METHODOLOGY_REQUIRED', analyze(data, review, NOW)['errors'])
    def test_missing_capital_structure_is_not_zero(self):
        data, review = fixture()
        data.pop('capital_structure')
        self.assertIn('CAPITAL_STRUCTURE_NOT_VALIDATED', analyze(data, review, NOW)['errors'])
    def test_methodology_needs_explicit_review(self):
        data, review = fixture()
        review.pop('cash_flow_methodology_approved')
        self.assertFalse(analyze(data, review, NOW)['valuation_ready'])
    def test_repository_policy_remains_locked(self):
        self.assertIs(load_policy().get('valuation_enabled'), False)
