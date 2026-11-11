import copy
import json
import tempfile
import unittest
from pathlib import Path
from scripts.check_dashboard import check


class ArtifactSafetyTests(unittest.TestCase):
    def artifact(self):
        root = Path(self.directory.name)
        (root / 'data').mkdir()
        (root / 'docs').mkdir()
        files = {
            'data/valuation_policy.json': {'valuation_enabled': False},
            'docs/latest.json': {'alphabet': {'accession':'a'}, 'positions':[
                {'fair_value':None,'assessment':{'discount_pct':None}}]},
            'docs/dcf_alphabet.json': {'accession':'a','verified':False,'valuation_ready':False,
                                     'scenarios':{'base':{'fair_value':None,'margin_of_safety_pct':None}}},
            'docs/release.json': {'version':'2.0','source_commit':None},
            'docs/history.json': []}
        for name, value in files.items():
            (root / name).write_text(json.dumps(value))
        for name in ('index.html','dcf.html'):
            (root / 'docs' / name).write_text('<html></html>')
        return root
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
    def test_locked_dashboard_is_publishable(self):
        check(self.artifact())
    def test_old_fair_value_is_rejected_before_publication(self):
        root=self.artifact()
        path=root/'docs/dcf_alphabet.json'
        data=json.loads(path.read_text())
        data['scenarios']['base']['fair_value']=100
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):check(root)
    def test_old_signal_is_rejected_before_publication(self):
        root=self.artifact()
        path=root/'docs/latest.json'
        data=json.loads(path.read_text())
        data['positions'][0]['assessment']['discount_pct']=30
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):check(root)
    def test_mismatched_filing_is_rejected(self):
        root=self.artifact()
        path=root/'docs/latest.json'
        path.write_text(json.dumps({'alphabet':{'accession':'other'},'positions':[]}))
        with self.assertRaises(ValueError):check(root)

    def test_opportunity_label_without_margin_is_rejected(self):
        root=self.artifact()
        path=root/'docs/latest.json'
        data=json.loads(path.read_text())
        data['positions'][0]['assessment']['label']='INVESTIGAR COMPRA'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):check(root)

    def test_wrong_tested_revision_is_rejected(self):
        from unittest.mock import patch
        root=self.artifact()
        with patch.dict('os.environ', {'EXPECTED_SOURCE_COMMIT':'tested-sha'}):
            with self.assertRaises(ValueError):check(root)
