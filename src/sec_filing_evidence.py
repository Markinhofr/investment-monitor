"""Read original SEC inline-XBRL with contexts, units, scale and provenance.

This verifies extraction, not accounting scope or financial approval. Ambiguous
facts and unsupported formats are rejected; missing values remain missing.
"""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from datetime import date, timedelta


class FilingParser(HTMLParser):
    def __init__(self, source, accession, filed):
        super().__init__()
        self.source, self.accession, self.filed = source, accession, filed
        self.contexts, self.units, self.facts = {}, {}, []
        self.context = self.unit = self.field = None
        self.text = []
        self.fact_stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'xbrli:context':
            self.context = {'id': a['id'], 'dimensional': False, 'members': []}
        elif tag == 'xbrli:unit':
            self.unit = {'id': a['id']}
        elif tag == 'xbrli:divide' and self.unit is not None:
            self.unit['unsupported_divide']=True
        elif tag == 'xbrldi:explicitmember' or tag == 'xbrldi:typedmember':
            if self.context is not None:
                self.context['dimensional'] = True
                if tag == 'xbrldi:explicitmember':
                    self.field, self.text = 'member', []
        elif tag in ('xbrli:startdate','xbrli:enddate','xbrli:instant','xbrli:identifier','xbrli:measure'):
            self.field, self.text = tag.split(':')[1], []
        elif tag == 'ix:nonfraction':
            self.fact_stack.append({**a, 'text': []})

    def handle_data(self, data):
        if self.field:
            self.text.append(data)
        for fact in self.fact_stack:
            fact['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'ix:nonfraction' and self.fact_stack:
            self.facts.append(self.fact_stack.pop())
        elif tag == 'xbrli:context' and self.context is not None:
            self.contexts[self.context['id']] = self.context
            self.context = None
        elif tag == 'xbrli:unit' and self.unit is not None:
            self.units[self.unit['id']] = None if self.unit.get('unsupported_divide') else self.unit.get('measure')
            self.unit = None
        elif self.field == 'member' and tag == 'xbrldi:explicitmember':
            self.context['members'].append(''.join(self.text).strip())
            self.field, self.text = None, []
        elif self.field and tag == 'xbrli:' + self.field:
            target = self.unit if self.field == 'measure' else self.context
            if target is not None:
                target[self.field] = ''.join(self.text).strip()
            self.field, self.text = None, []

    def select(self, tag, start, end, unit='USD', members=()):
        rows = []
        for raw in self.facts:
            c = self.contexts.get(raw.get('contextref'), {})
            if raw.get('name') != tag or sorted(c.get('members',[])) != sorted(members) or (c.get('dimensional') and not members) or c.get('identifier','').lstrip('0') != '1652044':
                continue
            if (c.get('startdate'), c.get('enddate') or c.get('instant')) != (start, end):
                continue
            actual_unit = (self.units.get(raw.get('unitref')) or '').split(':')[-1]
            if actual_unit != unit:
                continue
            if raw.get('xsi:nil') == 'true':
                continue
            text = ''.join(raw['text']).strip().replace(',','').replace('\u00a0','')
            fmt = (raw.get('format') or '').lower()
            if not (fmt.endswith('num-dot-decimal') or fmt.endswith('numdotdecimal') or not fmt or fmt.endswith('zerodash') or fmt.endswith('num-dash')):
                continue
            if text in ('—','–','-') and ('dash' in fmt):
                text = '0'
            if not re.fullmatch(r'-?\d+(\.\d+)?', text):
                continue
            try:
                value = Decimal(text) * Decimal(10) ** int(raw.get('scale', '0'))
                if raw.get('sign') == '-':
                    value = -value
            except (ValueError,InvalidOperation):
                continue
            if not value.is_finite():
                continue
            rows.append({'value': int(value) if value == value.to_integral_value() else float(value),
                         'unit':unit, 'start':start, 'end':end, 'as_of':self.filed if start else end, 'filed':self.filed,
                         'accession':self.accession, 'tag':tag, 'context':raw.get('contextref'),
                         'decimals':raw.get('decimals'), 'members':list(members), 'source_url':self.source,
                         'document_sha256':getattr(self,'document_sha256',None),
                         'validated':True, 'validation_scope':'inline-XBRL extraction only; no financial approval'})
        if not rows:
            return None
        if len({x['value'] for x in rows}) != 1:
            raise ValueError('Ambiguous SEC fact: ' + tag)
        return rows[0]


def read_filing(path, source, accession, filed):
    payload = path.read_bytes()
    parser = FilingParser(source,accession,filed)
    parser.feed(payload.decode('utf-8'))
    parser.document_sha256 = sha256(payload).hexdigest()
    return parser


def ttm(annual, current, prior):
    if any(x is None for x in (annual,current,prior)):
        return None
    if len({x['tag'] for x in (annual,current,prior)}) != 1 or len({x['unit'] for x in (annual,current,prior)}) != 1:
        raise ValueError('Incompatible TTM concepts')
    if current['end'][5:] != prior['end'][5:] or current['start'][5:] != '01-01' or prior['start'][5:] != '01-01':
        raise ValueError('Incompatible TTM periods')
    if int(current['start'][:4]) != int(annual['end'][:4])+1 or prior['start'][:4] != annual['end'][:4]:
        raise ValueError('Incompatible TTM years')
    value = annual['value']+current['value']-prior['value']
    return {'value':value,'unit':annual['unit'],'start':(date.fromisoformat(prior['end'])+timedelta(days=1)).isoformat(),
            'end':current['end'],'as_of':current['as_of'],'source_url':current['source_url'],
            'validated':True,'formula':'annual + current YTD - prior YTD',
            'components':{'annual':annual,'current_ytd':current,'prior_ytd':prior}}
