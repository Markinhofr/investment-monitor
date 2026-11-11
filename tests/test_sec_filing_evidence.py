import unittest
from src.sec_filing_evidence import FilingParser,ttm


def filing(value='1,234',unit='iso4217:USD',member='',extra=''):
    dimensional=f'<xbrli:scenario><xbrldi:explicitMember dimension="us-gaap:ClassOfStockAxis">{member}</xbrldi:explicitMember></xbrli:scenario>' if member else ''
    return f'''<xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001652044</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period>{dimensional}</xbrli:context>
    <xbrli:unit id="u"><xbrli:measure>{unit}</xbrli:measure></xbrli:unit>
    <ix:nonFraction name="us-gaap:Test" contextRef="c" unitRef="u" scale="6" decimals="-6" format="ixt:num-dot-decimal">{value}</ix:nonFraction>{extra}'''


class FilingEvidenceTests(unittest.TestCase):
    def parser(self,text):
        p=FilingParser('https://www.sec.gov/Archives/TEST','accession','2026-10-29')
        p.feed(text)
        return p
    def test_scale_context_units_and_provenance(self):
        p=self.parser(filing())
        r=p.select('us-gaap:Test',None,'2026-09-30')
        self.assertEqual(r['value'],1234000000)
        self.assertEqual(r['as_of'],'2026-09-30')
        self.assertEqual(r['filed'],'2026-10-29')
        self.assertEqual(r['accession'],'accession')
        self.assertEqual(r['context'],'c')
    def test_wrong_unit_or_period_missing_not_zero(self):
        p=self.parser(filing())
        self.assertIsNone(p.select('us-gaap:Test',None,'2026-06-30'))
        self.assertIsNone(p.select('us-gaap:Test',None,'2026-09-30','shares'))
    def test_dimensions_not_mixed_with_consolidated_fact(self):
        p=self.parser(filing(unit='xbrli:shares',member='us-gaap:CommonClassAMember'))
        self.assertIsNone(p.select('us-gaap:Test',None,'2026-09-30','shares'))
        r=p.select('us-gaap:Test',None,'2026-09-30','shares',members=('us-gaap:CommonClassAMember',))
        self.assertEqual(r['value'],1234000000)
    def test_ambiguous_values_rejected(self):
        extra='<ix:nonFraction name="us-gaap:Test" contextRef="c" unitRef="u" scale="6">999</ix:nonFraction>'
        p=self.parser(filing(extra=extra))
        with self.assertRaises(ValueError):p.select('us-gaap:Test',None,'2026-09-30')
    def test_unknown_entity_rejected(self):
        p=self.parser(filing().replace('0001652044','0000000001'))
        self.assertIsNone(p.select('us-gaap:Test',None,'2026-09-30'))
    def test_nil_nonfinite_and_unrecognised_formats_rejected(self):
        for value in ('NaN','inf','not-a-number'):
            p=self.parser(filing(value=value))
            self.assertIsNone(p.select('us-gaap:Test',None,'2026-09-30'))
        p=self.parser(filing().replace('format="ixt:num-dot-decimal"','format="unsupported"'))
        self.assertIsNone(p.select('us-gaap:Test',None,'2026-09-30'))
    def test_nested_numeric_facts_share_text_without_duplication(self):
        text=filing(value='<ix:nonFraction name="us-gaap:Alias" contextRef="c" unitRef="u" scale="6">1,234</ix:nonFraction>')
        p=self.parser(text)
        self.assertEqual(p.select('us-gaap:Test',None,'2026-09-30')['value'],1234000000)
        self.assertEqual(p.select('us-gaap:Alias',None,'2026-09-30')['value'],1234000000)
    def test_ttm_period_and_missing_component(self):
        def r(value,start,end,tag='Test'):
            return {'value':value,'start':start,'end':end,'tag':tag,'unit':'USD',
                    'as_of':'2026-10-29','source_url':'https://www.sec.gov/Archives/TEST'}
        a=r(100,'2025-01-01','2025-12-31')
        c=r(90,'2026-01-01','2026-09-30')
        p=r(75,'2025-01-01','2025-09-30')
        result=ttm(a,c,p)
        self.assertEqual(result['value'],115)
        self.assertEqual(result['start'],'2025-10-01')
        self.assertIsNone(ttm(a,c,None))
        with self.assertRaises(ValueError):ttm(a,{**c,'tag':'Other'},p)
        with self.assertRaises(ValueError):ttm(a,c,{**p,'end':'2025-06-30'})
