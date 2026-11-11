"""Validate the exact Pages artifact before upload; never publish unlocked values by accident."""
import json
import os
from pathlib import Path


def check(root):
    root = Path(root)
    policy = json.loads((root / 'data/valuation_policy.json').read_text())
    latest = json.loads((root / 'docs/latest.json').read_text())
    release = json.loads((root / 'docs/release.json').read_text())
    if release.get('version') != '2.0' or release.get('source_commit') != latest.get('source_commit'):
        raise ValueError('Release provenance differs from dashboard')
    expected = os.getenv('EXPECTED_SOURCE_COMMIT')
    if expected and release.get('source_commit') != expected:
        raise ValueError('Artifact does not match tested revision')
    research = json.loads((root / 'docs/dcf_alphabet.json').read_text())
    if policy.get('valuation_enabled') is not True:
        if any(x.get('valuation_ready') or x.get('verified') for x in (research, latest.get('alphabet', {}))):
            raise ValueError('Locked policy conflicts with ready valuation')
        if any(s.get('fair_value') is not None or s.get('margin_of_safety_pct') is not None
               for payload in (research, latest.get('alphabet', {}))
               for s in payload.get('scenarios', {}).values()):
            raise ValueError('Locked policy contains DCF values')
        if any(row.get('fair_value') is not None or row.get('assessment', {}).get('discount_pct') is not None
               or row.get('assessment', {}).get('label') not in (None, 'DADOS INSUFICIENTES', 'SEM FAIR VALUE VERIFICADO')
               for row in latest.get('positions', [])):
            raise ValueError('Locked policy contains fair values or margins')
    if latest.get('alphabet', {}).get('accession') != research.get('accession'):
        raise ValueError('Dashboard and DCF filing differ')
    for name in ('index.html', 'dcf.html', 'history.json'):
        if not (root / 'docs' / name).is_file():
            raise ValueError('Missing Pages artifact: ' + name)
    print('Pages artifact validated; valuation policy:', policy.get('valuation_enabled') is True)


if __name__ == '__main__':
    check(Path(__file__).resolve().parents[1])
