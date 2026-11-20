"""Fixed-trial before/after checks for the focused future-self trump preference.

Uses original public inputs and exact references from the runtime comparison.
No actual hidden hands are read. Full matches are deliberately not repeated.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.storage.analysis_log import analysis_record, append_analysis
from bela.storage.user_storage import loads_user_match


def run(root, reference_root, label):
    folder = root / label
    folder.mkdir(exist_ok=False)
    shutil.copytree(Path(__file__).resolve().parents[1] / 'src' / 'bela', folder/'source',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    cases = {}
    for line in (reference_root/'endgames'/'analyses.jsonl').read_text().splitlines():
        r = json.loads(line)
        cases.setdefault(r['context']['case'], r['input'])
    rows = []
    for case, inp in sorted(cases.items()):
        match = loads_user_match(json.dumps(inp))
        exact = json.loads((reference_root/'endgames'/f'case-{case:02d}.json').read_text())['reference']
        values = {r['card']: Fraction(r['objective_fraction']) for r in exact['moves']}
        for samples in (128, 512):
            for seed in (7, 42, 119):
                result = analyze_moves(match, MonteCarloConfig(samples=samples, seconds=30, seed=seed))
                append_analysis(folder/'analyses.jsonl', analysis_record(match, result,
                    case=case, purpose='focused_trump_discard_check'))
                assert result['status'] == 'complete' and result['completed_samples'] == samples
                selected = result['moves'][0]['card']
                rows.append({'case': case, 'samples': samples, 'seed': seed,
                    'selected': selected, 'optimal': selected in exact['best_cards'],
                    'root_regret': float(max(values.values()) - values[selected]),
                    'guard_selections': result['strategy_model']['self_search'].get(
                        'attempted_losing_trump_selections', 0)})
        print(f'{label}: exact case {case+1}/20', flush=True)
    saved = []
    for r in json.loads((root/'baseline-traces.json').read_text()):
        match = loads_user_match(json.dumps(r['input']))
        result = analyze_moves(match, MonteCarloConfig(**r['config']))
        append_analysis(folder/'saved-analyses.jsonl', analysis_record(match, result,
            **{k:r[k] for k in ('index','deal','ply')}, purpose='saved_disagreement_check'))
        assert result['status'] == 'complete' and result['completed_samples'] == 128
        saved.append({k:r[k] for k in ('index','deal','ply')} | {
            'selected': result['moves'][0]['card'],
            'baseline_selected': r['advice']['moves'][0]['card'],
            'guard_selections': result['strategy_model']['self_search'].get(
                'attempted_losing_trump_selections', 0)})
    summary = {str(n): {'optimal': sum(r['optimal'] for r in rows if r['samples']==n),
        'analyses': sum(r['samples']==n for r in rows),
        'mean_root_regret': sum(r['root_regret'] for r in rows if r['samples']==n)/60,
        'max_root_regret': max(r['root_regret'] for r in rows if r['samples']==n)} for n in (128,512)}
    report = {'summary': summary, 'rows': rows, 'saved_positions': saved,
              'scope': 'Development regression checks, not a fresh full-match strength claim.'}
    if label != 'baseline':
        before = json.loads((root/'baseline'/'results.json').read_text())['rows']
        assert [(r['case'],r['samples'],r['seed']) for r in rows] == [
            (r['case'],r['samples'],r['seed']) for r in before]
        report['improvements'] = [r | {'baseline_regret': b['root_regret']}
            for r,b in zip(rows,before) if r['root_regret'] < b['root_regret']]
        report['regressions'] = [r | {'baseline_regret': b['root_regret']}
            for r,b in zip(rows,before) if r['root_regret'] > b['root_regret']]
    (folder/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    run(a.output, a.reference, a.label)
