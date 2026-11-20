"""Serial three-way equal-wall-time match comparison with original journals.

Time-limit results with completed paired evaluations are expected. Zero-result
analyses, overshoots and other failures stop the experiment before a move.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
from random import Random
import shutil
import statistics
import subprocess
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from compare_search import keep_awake, write_issue

MODELS = {'direct': 'direct_competent_mix_v1', 'learned': 'learn_then_evaluate_v2',
          'current': 'information_set_tree_v1'}


def source_hash():
    root = Path(__file__).resolve().parents[1] / 'src' / 'bela'
    digest = hashlib.sha256()
    for p in sorted(root.rglob('*.py')):
        digest.update(p.relative_to(root).as_posix().encode())
        digest.update(p.read_bytes())
    return digest.hexdigest()


def endgame_sanity(root, seconds):
    from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
    from bela.storage.analysis_log import analysis_record, append_analysis
    from endgame_accuracy import reference_cases
    root.mkdir(exist_ok=False)
    rows = []
    orders = tuple(itertools.permutations(MODELS))
    for metadata, match, exact, _ in reference_cases(root, 2026102504, 16, 4):
        case = metadata['case']
        values = {r['card']: Fraction(r['objective_fraction']) for r in exact['moves']}
        (root/f'case-{case:02d}.json').write_text(json.dumps({'metadata': metadata,
            'reference': exact}, indent=2)+'\n')
        for seed in (7, 42, 119):
            for model in orders[(case+seed) % len(orders)]:
                result = analyze_moves(match, MonteCarloConfig(samples=10000, seconds=seconds,
                    seed=seed, self_policy=MODELS[model]))
                append_analysis(root/'analyses.jsonl', analysis_record(match, result,
                    case=case, purpose='runtime_architecture_endgame_sanity'))
                assert result['status'] in ('complete', 'time_limit') and result['completed_samples'] > 0
                selected = min(result['moves'], key=lambda r:r['rank'])['card']
                rows.append({'case': case, 'seed': seed, 'model': model, 'selected': selected,
                    'optimal': selected in exact['best_cards'],
                    'root_regret_points': float(max(values.values())-values[selected]),
                    'evaluation_trials': result['completed_samples'],
                    'learning_trials': result['completed_learning_samples']})
        print(f'Exact runtime sanity {case+1}/20 complete', flush=True)
    summary = {model: {'analyses': sum(r['model']==model for r in rows),
        'optimal': sum(r['model']==model and r['optimal'] for r in rows),
        'mean_root_regret': statistics.mean(r['root_regret_points'] for r in rows if r['model']==model),
        'max_root_regret': max(r['root_regret_points'] for r in rows if r['model']==model)} for model in MODELS}
    (root/'summary.json').write_text(json.dumps({'seconds': seconds, 'models': summary,
        'rows': rows, 'scope': 'Known-card development sanity, not fresh strength evidence'}, indent=2)+'\n')


def worker(root, model, index):
    from bela.interfaces import batch_cli
    config = json.loads((root / 'config.json').read_text())
    original = batch_cli.run_match
    def checked(cfg, case, *, cancelled=None, on_analysis=None):
        def journal(entry):
            on_analysis(entry)
            advice = entry['advice']
            if advice['status'] == 'forced_move':
                return
            problem = None
            if advice['status'] not in ('complete', 'time_limit'):
                problem = 'unexpected_analysis_status'
            elif advice['completed_samples'] < 1:
                problem = 'no_evaluation_estimate'
            elif advice['elapsed_seconds'] > config['seconds'] + config['overshoot_grace']:
                problem = 'runtime_overshoot'
            elif model == 'learned' and advice['completed_learning_samples'] < 1:
                problem = 'no_completed_learning'
            if problem:
                write_issue(root, {'problem': problem, 'model': model, 'index': index,
                    'context': entry['context'], 'status': advice['status'],
                    'evaluations': advice['completed_samples'], 'seconds': advice['elapsed_seconds']})
        return original(cfg, case, cancelled=lambda: (root/'STOP.json').exists() or
                        (cancelled and cancelled()), on_analysis=journal)
    batch_cli.run_match = checked
    try:
        code = batch_cli.main(['--mode', 'monte-carlo', '--matches', '1',
            '--seed', str(config['seed']), '--start-index', str(index),
            '--samples', str(config['sample_cap']), '--seconds', str(config['seconds']),
            '--self-policy', config['models'][model], '--save-games',
            '--output', str(root/model/f'match-{index}')])
        if code:
            write_issue(root, {'problem': 'worker_exit', 'model': model, 'index': index, 'code': code})
        return code
    except BaseException as error:
        write_issue(root, {'problem': 'worker_exception', 'model': model, 'index': index, 'error': repr(error)})
        raise


def run(root, count, seconds, seed):
    root.mkdir(parents=True, exist_ok=False)
    config = {'models': MODELS, 'sets': count, 'seed': seed, 'seconds': seconds,
              'sample_cap': 10000, 'workers': 1, 'overshoot_grace': .2,
              'order': 'cyclic_six_permutations', 'source_sha256': source_hash(),
              'primary_metric': 'net_recorded_points_per_three_way_shared_deal',
              'noninferiority_margin_points': 5,
              'bootstrap_resamples': 12000, 'bootstrap_seed': 2026102509,
              'comparison_family': 3, 'family_error': .05,
              'default_rule': 'Prefer direct only if adjusted lower bounds vs both alternatives exceed -5 and exact sanity max regret is at most 5. Prefer learned only on clear paired gains over current. Otherwise retain current.',
              'scope': 'half_second_budget; no assertion about larger runtime budgets'}
    (root/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    shutil.copytree(Path(__file__).resolve().parents[1]/'src'/'bela', root/'source'/'bela',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(Path(__file__), root/'benchmark.py')
    orders = tuple(itertools.permutations(MODELS))
    started = perf_counter()
    completed = 0
    try:
        endgame_sanity(root/'endgames', seconds)
        for index in range(count):
            order = orders[index % len(orders)]
            for model in order:
                if source_hash() != config['source_sha256']:
                    raise RuntimeError('Engine source changed during the comparison')
                print(f'Starting set {index+1}/{count}: {model}', flush=True)
                with (root/f'{model}-{index}.log').open('x') as log:
                    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                        '--output', str(root), '--worker', model, str(index)],
                        stdout=log, stderr=subprocess.STDOUT)
                    try:
                        code = child.wait()
                    finally:
                        if child.poll() is None:
                            child.terminate()
                        child.wait()
                if code or (root/'STOP.json').exists():
                    raise RuntimeError('Timed comparison stopped; inspect preserved logs and STOP.json')
                row = json.loads((root/model/f'match-{index}'/'matches.jsonl').read_text())
                assert row['status'] == 'complete'
                completed += 1
                print(f'Finished {model} {index}: score={row["score"]}, win={row["our_win"]}, '
                      f'{row["elapsed_seconds"]:.1f}s', flush=True)
        assert source_hash() == config['source_sha256']
    finally:
        (root/'run-summary.json').write_text(json.dumps({'completed_games': completed,
            'requested_games': count*3, 'status': 'complete' if completed == count*3 else 'stopped',
            'elapsed_seconds': perf_counter()-started}, indent=2)+'\n')


def audit(root):
    from bela.gameplay.batch import trick_point_history
    from bela.gameplay.session import initial_hands
    from bela.storage.persistence import load_match
    from bela.storage.user_storage import loads_user_match
    config = json.loads((root/'config.json').read_text())
    assert json.loads((root/'run-summary.json').read_text())['status'] == 'complete'
    details, clusters = [], []
    journal_count = 0
    for index in range(config['sets']):
        rows, sessions = {}, {}
        for model, policy in config['models'].items():
            folder = root/model/f'match-{index}'
            row = json.loads((folder/'matches.jsonl').read_text())
            archive = folder/'games'/f'match-{index:06d}.sim.json'
            session = load_match(archive)
            raw = json.loads(archive.read_text())['match']['deals']
            journal = [json.loads(x) for x in (folder/'analyses.jsonl').read_text().splitlines()]
            assert row['status'] == 'complete' and list(session.score) == row['score']
            assert session.winner == row['winner']
            assert journal == row['decision_estimates'] and len(journal) == row['decisions']
            elapsed, evaluations, learning = [], [], []
            statuses = Counter()
            for e in journal:
                a, ctx = e['advice'], e['context']
                match = loads_user_match(json.dumps(e['input']))
                assert e['provenance'] == 'original_analysis'
                assert a['config']['self_policy'] == policy
                assert a['config']['seconds'] == config['seconds']
                assert a['config']['samples'] == config['sample_cap']
                assert a['revision'] == match.revision
                assert set(r['card'] for r in a['moves']) == set(map(str, match.state.legal_actions))
                actions = [p for p in raw[ctx['deal_index']]['actions'] if p['type'] == 'play_card']
                played = actions[ctx['ply']]
                assert played['player'] == row['player']
                chosen = min(a['moves'], key=lambda r: r['rank'])
                assert ctx['selected_move'] == {'card': played['card'], 'bela': played['bela']}
                assert ctx['selected_move'] == {'card': chosen['card'], 'bela': chosen['bela']}
                statuses[a['status']] += 1
                if a['status'] == 'forced_move':
                    assert a['completed_samples'] == a['completed_learning_samples'] == 0
                    assert all(r['success_probability'] is None for r in a['moves'])
                    continue
                assert a['status'] in ('complete', 'time_limit') and a['completed_samples'] > 0
                assert a['elapsed_seconds'] <= config['seconds']+config['overshoot_grace']
                assert all(r['samples'] == a['completed_samples'] and 0 <= r['success_probability'] <= 1 for r in a['moves'])
                assert a['total_completed_trials'] == a['completed_samples']+a['completed_learning_samples']
                if model == 'direct':
                    assert a['completed_learning_samples'] == 0 and a['strategy_model']['self_search'] is None
                elif model == 'learned':
                    assert a['completed_learning_samples'] > 0
                    assert a['strategy_model']['self_search']['evaluation']['values_frozen']
                elapsed.append(a['elapsed_seconds'])
                evaluations.append(a['completed_samples'])
                learning.append(a['completed_learning_samples'])
            assert sum(evaluations) == row['completed_trials']
            assert sum(learning) == row['completed_learning_trials']
            for state, deal in zip(session.deals, row['deals']):
                assert state.finished and deal['tricks'] == trick_point_history(state)
                if not deal['belot']:
                    assert len(state.completed_tricks) == 8
                    assert sum(deal['tricks'][-1]['cumulative_card_points']) == 152
            details.append({'index': index, 'model': model, 'win': row['our_win'],
                'score': row['score'], 'deals': len(row['deals']), 'nonforced_analyses': len(elapsed),
                'analysis_seconds': sum(elapsed), 'max_analysis_seconds': max(elapsed, default=0),
                'evaluation_trials': sum(evaluations), 'learning_trials': sum(learning),
                'statuses': dict(statuses)})
            journal_count += len(journal)
            rows[model], sessions[model] = row, session
        baseline = rows['current']
        for row in rows.values():
            for key in ('match_seed', 'match_id', 'player', 'team', 'initial_dealer', 'profiles', 'calling_policy'):
                assert row[key] == baseline[key]
        shared = min(len(row['deals']) for row in rows.values())
        nets = {model: [] for model in MODELS}
        contracts = {model: [0, 0] for model in MODELS}
        for di in range(shared):
            before = sessions['current'].deals[di]
            for model, row in rows.items():
                state, deal = sessions[model].deals[di], row['deals'][di]
                assert initial_hands(state) == initial_hands(before)
                for field in ('dealer', 'caller', 'trump', 'calling'):
                    assert deal[field] == baseline['deals'][di][field]
                team = row['team']
                nets[model].append(deal['recorded'][team]-deal['recorded'][1-team])
                if deal['caller'] % 2 == team:
                    contracts[model][0] += int(deal['caller_passed'])
                    contracts[model][1] += 1
        clusters.append({'index': index, 'shared_deals': shared, 'nets': nets, 'own_contracts': contracts})
        print(f'Audited set {index+1}: {shared} three-way shared deals', flush=True)
    models = list(MODELS)
    pairs = list(itertools.combinations(models, 2))
    rng = Random(config['bootstrap_seed'])
    samples = {pair: [] for pair in pairs}
    for _ in range(config['bootstrap_resamples']):
        draw = rng.choices(clusters, k=len(clusters))
        count = sum(c['shared_deals'] for c in draw)
        for a,b in pairs:
            samples[a,b].append(sum(sum(c['nets'][a])-sum(c['nets'][b]) for c in draw)/count)
    n = sum(c['shared_deals'] for c in clusters)
    alpha = config['family_error']/config['comparison_family']
    comparisons = []
    for a,b in pairs:
        ordered = sorted(samples[a,b]);length = len(ordered)
        comparisons.append({'first': a, 'second': b,
            'mean_net_points_per_shared_deal': sum(sum(c['nets'][a])-sum(c['nets'][b]) for c in clusters)/n,
            'exploratory_family_adjusted_interval': [ordered[int(length*alpha/2)], ordered[min(length-1,int(length*(1-alpha/2)))]]})
    summary = {}
    for model in MODELS:
        rr = [d for d in details if d['model'] == model]
        count = sum(d['nonforced_analyses'] for d in rr)
        summary[model] = {'wins': sum(d['win'] for d in rr), 'matches': len(rr),
            'net_points_per_shared_deal': sum(sum(c['nets'][model]) for c in clusters)/n,
            'own_contracts_passed': sum(c['own_contracts'][model][0] for c in clusters),
            'own_contracts_called': sum(c['own_contracts'][model][1] for c in clusters),
            'mean_analysis_seconds': sum(d['analysis_seconds'] for d in rr)/count,
            'max_analysis_seconds': max(d['max_analysis_seconds'] for d in rr),
            'mean_evaluation_trials': sum(d['evaluation_trials'] for d in rr)/count,
            'mean_learning_trials': sum(d['learning_trials'] for d in rr)/count}
    report = {'models': summary, 'comparisons': comparisons, 'sets': len(clusters),
        'three_way_shared_deals': n, 'journal_records_audited': journal_count,
        'details': details, 'clusters': clusters, 'all_games_and_trick_histories_verified': True,
        'limits': ['Single-worker fixed wall-time budget; hardware load can still vary.',
                   'Time-limited estimates need not reproduce bit-for-bit; original estimates are retained.',
                   'Shared deals are truncated to the common match prefix, not an uncensored population sample.',
                   'Exploratory bootstrap intervals are not exact finite-sample guarantees.',
                   'Conclusions apply to the tested runtime and simulated opponent model, not arbitrary humans.']}
    sanity = json.loads((root/'endgames'/'summary.json').read_text())['models']
    lower = {(p['first'],p['second']):p['exploratory_family_adjusted_interval'][0] for p in comparisons}
    direct_ok = all(lower['direct',other] >= -config['noninferiority_margin_points']
                    for other in ('learned','current')) and sanity['direct']['max_root_regret'] <= 5
    learned_ok = lower['learned','current'] > 0 and sanity['learned']['max_root_regret'] <= 5
    report['recommended_at_tested_budget'] = 'direct' if direct_ok else 'learned' if learned_ok else 'current'
    report['direct_noninferiority_screen_passed'] = direct_ok
    report['exact_sanity'] = sanity
    (root/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('details','clusters')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sets', type=int, default=16)
    parser.add_argument('--seconds', type=float, default=.5)
    parser.add_argument('--seed', type=int, default=2026102508)
    parser.add_argument('--worker', nargs=2)
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker(args.output, args.worker[0], int(args.worker[1])))
    if args.audit:
        audit(args.output)
    else:
        if not 4 <= args.sets <= 100 or not .25 <= args.seconds <= 15:
            parser.error('Use 4–100 sets and 0.25–15 seconds per decision')
        with keep_awake():
            run(args.output, args.sets, args.seconds, args.seed)
