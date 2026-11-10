import unittest
import datetime
import tempfile
from pathlib import Path
from unittest.mock import patch
from src.monitor import schedule, assess, build
from src.research import collect

class Tests(unittest.TestCase):
    def test_winter_daily(self):
        self.assertEqual(schedule(datetime.datetime(2026,11,9,22,30,tzinfo=datetime.timezone.utc)), 'daily')
    def test_summer_daily(self):
        self.assertEqual(schedule(datetime.datetime(2027,7,9,21,30,tzinfo=datetime.timezone.utc)), 'daily')
    def test_weekly(self):
        self.assertEqual(schedule(datetime.datetime(2026,11,8,10,30,tzinfo=datetime.timezone.utc)), 'weekly')
    def test_outside(self):
        self.assertIsNone(schedule(datetime.datetime(2026,11,9,12,30,tzinfo=datetime.timezone.utc)))
    def test_discount(self):
        today = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.assertEqual(assess({'price':80,'currency':'USD','as_of':today},
                         {'value':100,'currency':'USD','source_url':'https://www.sec.gov/',
                          'as_of':today,'verified':True,'valuation_ready':True})['discount_pct'],20)
    def test_unverified_value(self):
        today = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.assertIsNone(assess({'price':80,'currency':'USD','as_of':today},
                          {'value':100,'currency':'USD','as_of':today,'source_url':'https://example.org'})['discount_pct'])
    def test_watchlist(self):
        import src.monitor as monitor
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(monitor.ROOT / 'data', root / 'data')
            with patch.object(monitor, 'ROOT', root):
                report = build('test', True, research=collect({}, True))
            self.assertFalse(next(x for x in report['positions'] if x['symbol']=='GOOGL')['owned'])
            self.assertTrue((root / 'docs/history.json').exists())
