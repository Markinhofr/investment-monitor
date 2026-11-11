"""Read-only release preflight. Makes no merges, settings changes, dispatches or notifications."""
import json
import subprocess
from pathlib import Path

REPO = 'Markinhofr/investment-monitor'
ROOT = Path(__file__).resolve().parents[1]


def github(path):
    result = subprocess.run(['gh', 'api', 'repos/' + REPO + ('/' + path if path else '')], check=True,
                            capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    if subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() != 'investment-v2':
        raise SystemExit('Run only from investment-v2')
    pr = github('pulls/1')
    repo = github('')
    workflows = github('actions/workflows')['workflows']
    pages = github('pages')
    runs = github('actions/runs?per_page=30')['workflow_runs']
    active = [dict(id=x['id'], event=x['event'], branch=x['head_branch'], status=x['status'])
              for x in runs if x['status'] != 'completed']
    policy = json.loads((ROOT / 'data/valuation_policy.json').read_text())
    review = json.loads((ROOT / 'data/alphabet_review.json').read_text())
    if policy.get('valuation_enabled') is not False or any(review.get(k) is True for k in (
        'all_share_classes_confirmed', 'debt_scope_confirmed', 'extraordinary_cash_flows_reviewed',
        'assumptions_approved', 'cash_flow_methodology_approved')):
        raise SystemExit('Financial lock/review changed: require renewed approval')
    monitor = [x for x in workflows if x['path'] == '.github/workflows/monitor.yml']
    if len(monitor) != 1:
        raise SystemExit('Expected exactly one monitor workflow')
    summary = {
        'repository': REPO, 'default_branch': repo['default_branch'],
        'default_branch_sha': github('branches/' + repo['default_branch'])['commit']['sha'],
        'pr': {k: pr.get(k) for k in ('number','state','mergeable','mergeable_state')},
        'reviewed_head_sha': pr['head']['sha'],
        'pages': {k: pages.get(k) for k in ('build_type','source','html_url')},
        'monitor_workflow': {k:monitor[0][k] for k in ('id','path','state')},
        'active_runs': active, 'financial_values_locked': True,
        'cutover_authorized': False,
        'next': 'Owner approval required. Follow docs/PRODUCTION.md; do not execute merge/settings changes from this preflight.'}
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
