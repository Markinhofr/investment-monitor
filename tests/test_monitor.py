import unittest,datetime,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from monitor import schedule,assess,build
class Tests(unittest.TestCase):
 def test_winter_daily(self): self.assertEqual(schedule(datetime.datetime(2026,11,9,22,30,tzinfo=datetime.timezone.utc)),'daily')
 def test_summer_daily(self): self.assertEqual(schedule(datetime.datetime(2027,7,9,21,30,tzinfo=datetime.timezone.utc)),'daily')
 def test_weekly(self): self.assertEqual(schedule(datetime.datetime(2026,11,8,10,30,tzinfo=datetime.timezone.utc)),'weekly')
 def test_outside(self): self.assertIsNone(schedule(datetime.datetime(2026,11,9,12,30,tzinfo=datetime.timezone.utc)))
 def test_discount(self): self.assertEqual(assess({'price':80,'currency':'USD'},{'value':100,'currency':'USD','source_url':'https://example.org','as_of':'2026-11-09'})['discount_pct'],20)
 def test_currency_mismatch(self): self.assertIsNone(assess({'price':80,'currency':'EUR'},{'value':100,'currency':'USD','source_url':'https://example.org','as_of':'2026-11-09'})['discount_pct'])
 def test_missing_source(self): self.assertIsNone(assess({'price':80,'currency':'USD'},{'value':100,'currency':'USD'})['discount_pct'])
 def test_watchlist(self):
  r=build('test',True)
  self.assertFalse(next(x for x in r['positions'] if x['symbol']=='GOOGL')['owned'])
if __name__=='__main__':unittest.main()
