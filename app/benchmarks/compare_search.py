"""Compare future-search variants on frozen positions and paired local matches.

Run with app/src on PYTHONPATH. All outputs are fresh files under --output;
original diagnostic records are read only. At most four match workers run.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

MODELS = {'old': 'information_set_tree_v1', 'new': 'shared_information_set_tree_v2'}
MODEL_SAMPLES = {'old': 128, 'new': 128}


@contextmanager
def keep_awake():
    """Prevent idle system sleep during a Windows batch; reset on exit.

    This leaves the display free to sleep and changes no power-plan settings.
    Windows also releases the request automatically when the process exits.
    """
    if sys.platform != 'win32':
        yield
        return
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    request = kernel.SetThreadExecutionState
    request.argtypes = [ctypes.c_ulong]
    request.restype = ctypes.c_ulong
    if not request(0x80000001):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        request(0x80000000)


def write_issue(root, details):
    try:
        with (root / 'STOP.json').open('x') as stream:
            json.dump(details, stream)
    except FileExistsError:
        pass  # Keep the first cause rather than a later cancellation exit.


def diagnostic(root, inputs, budgets):
    from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
    from bela.storage.analysis_log import analysis_record, append_analysis
    from bela.storage.user_storage import loads_user_match
    rows = []
    for case in range(1, 7):
        original = json.loads((inputs / f'case-{case}-original.json').read_text())
        match = loads_user_match(json.dumps(original['input']))
        for count in budgets:
            for model, policy in MODELS.items():
                config = MonteCarloConfig(**(original['advice']['config'] |
                    {'samples': count, 'seconds': 60, 'self_policy': policy}))
                advice = analyze_moves(match, config)
                record = analysis_record(match, advice, diagnostic_case=case,
                                         original_record_id=original['record_id'])
                record['provenance'] = 'reanalysis_of_frozen_position'
                append_analysis(root / 'diagnostics.jsonl', record)
                if advice['status'] != 'complete' or advice['completed_samples'] != count:
                    raise RuntimeError('Incomplete diagnostic; stop the experiment')
                if model == 'old' and count == 128 and policy == 'information_set_tree_v1':
                    for field in ('moves', 'comparisons'):
                        assert json.loads(json.dumps(advice[field])) == original['advice'][field]
                stats = advice['strategy_model']['self_search']
                stats = stats.get('evaluation') or stats
                decisions = stats['selections'] - stats['attempted_forced_selections']
                learned = stats['attempted_value_selections']
                shared = stats.get('attempted_shared_value_selections', 0)
                ranked = sorted(advice['moves'], key=lambda r: r['rank'])
                row = {'case': case, 'budget': count, 'model': model,
                       'seconds': advice['elapsed_seconds'], 'card': ranked[0]['card'],
                       'gap': ranked[0]['objective_mean'] - ranked[1]['objective_mean'],
                       'decisions': decisions, 'exact_value_selections': learned,
                       'shared_value_selections': shared,
                       'value_fraction': (learned + shared) / decisions if decisions else 0,
                       'search': stats}
                rows.append(row)
                (root / 'diagnostic-summary.json').write_text(json.dumps(rows, indent=2) + '\n')
                print(json.dumps({k: v for k, v in row.items() if k != 'search'}), flush=True)
    summarize_diagnostics(root, rows, budgets)


def summarize_diagnostics(root, rows, budgets):
    summary = {}
    for count in budgets:
        summary[count] = {}
        for model in MODELS:
            selected = [r for r in rows if r['budget'] == count and r['model'] == model]
            decisions = sum(r['decisions'] for r in selected)
            summary[count][model] = {
                'seconds': sum(r['seconds'] for r in selected),
                'value_fraction': sum(r['exact_value_selections'] + r['shared_value_selections']
                                      for r in selected) / decisions}
    first, last = min(budgets), max(budgets)
    changes = {model: sum(next(r['card'] for r in rows if r['case'] == case and
                              r['model'] == model and r['budget'] == first) !=
                         next(r['card'] for r in rows if r['case'] == case and
                              r['model'] == model and r['budget'] == last)
                         for case in range(1, 7)) for model in MODELS}
    low = summary[first]
    report = {'models': MODELS, 'budgets': summary, 'low_to_high_choice_changes': changes,
              'all_requested_trials_completed': True,
              'original_128_results_reproduced': True if 128 in budgets and MODELS['old'] == 'information_set_tree_v1' else None,
              'diagnostic_screen_passed': (
                  low['new']['value_fraction'] >= 2 * low['old']['value_fraction'] and
                  low['new']['seconds'] <= 1.5 * low['old']['seconds'])
                  if MODELS['old'] == 'information_set_tree_v1' else None}
    (root / 'study-summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


def match_worker(root, model, index, seed):
    from bela.interfaces import batch_cli
    original = batch_cli.run_match
    def checked(config, match_index, *, cancelled=None, on_analysis=None):
        def journal(entry):
            on_analysis(entry)
            advice = entry['advice']
            if advice['status'] != 'forced_move' and (
                    advice['status'] != 'complete' or advice['completed_samples'] != MODEL_SAMPLES[model] or
                    (MODELS[model] in ('learn_then_evaluate_v1', 'learn_then_evaluate_v2') and
                     advice.get('completed_learning_samples') != MODEL_SAMPLES[model])):
                write_issue(root, {'model': model, 'index': index,
                    'status': advice['status'], 'samples': advice['completed_samples']})
        return original(config, match_index,
            cancelled=lambda: (root / 'STOP.json').exists() or (cancelled and cancelled()),
            on_analysis=journal)
    batch_cli.run_match = checked
    code = batch_cli.main(['--mode', 'monte-carlo', '--matches', '1', '--seed', str(seed),
        '--start-index', str(index), '--samples', str(MODEL_SAMPLES[model]), '--seconds', '60',
        '--self-policy', MODELS[model], '--save-games',
        '--output', str(root / model / f'match-{index}')])
    if code:
        write_issue(root, {'model': model, 'index': index, 'exit': code})
    return code


def matches(root, start, count, seed, resume=False):
    started = perf_counter()
    config = {'models': MODELS, 'seed': seed, 'start': start, 'count': count,
              'samples': MODEL_SAMPLES, 'seconds': 60, 'workers': 4}
    config_path = root / 'config.json'
    if config_path.exists():
        prior = json.loads(config_path.read_text())
        if isinstance(prior['samples'], int):
            prior['samples'] = {model: prior['samples'] for model in MODELS}
        if not resume or prior != config:
            raise ValueError('Existing experiment requires --resume and identical configuration')
    else:
        config_path.write_text(json.dumps(config, indent=2) + '\n')
    if (root / 'STOP.json').exists():
        raise RuntimeError('Unresolved stop record; preserve and investigate before resuming')
    for first in range(start, start + count, 4):
        for model in MODELS:
            children = []
            try:
                for index in range(first, min(first + 4, start + count)):
                    folder = root / model / f'match-{index}'
                    if folder.exists():
                        if resume:
                            row = json.loads((folder / 'matches.jsonl').read_text())
                            assert row['status'] == 'complete'
                            assert row['match_index'] == index
                            assert row['self_continuation'] == MODELS[model]
                            assert (folder / 'games' / f'match-{index:06d}.sim.json').exists()
                            print(f'Keeping completed {model} {index}', flush=True)
                            continue
                        raise FileExistsError(folder)
                    stream = (root / f'{model}-{index}.log').open('x')
                    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                        '--output', str(root), '--worker', model, str(index), '--seed', str(seed),
                        '--old-policy', MODELS['old'], '--new-policy', MODELS['new'],
                        '--old-samples', str(MODEL_SAMPLES['old']), '--new-samples', str(MODEL_SAMPLES['new'])],
                        stdout=stream, stderr=subprocess.STDOUT)
                    children.append((index, child, stream))
                for index, child, stream in children:
                    if child.wait() or (root / 'STOP.json').exists():
                        raise RuntimeError('Match worker failed; inspect logs')
                    row = json.loads((root / model / f'match-{index}' / 'matches.jsonl').read_text())
                    assert row['status'] == 'complete'
                    print(f'{model} {index}: {row["score"]}, win={row["our_win"]}, '
                          f'{row["elapsed_seconds"]:.1f}s', flush=True)
            finally:
                for _, child, stream in children:
                    if child.poll() is None:
                        child.terminate()
                    child.wait()
                    stream.close()
    (root / 'run-summary.json').write_text(json.dumps({
        'elapsed_seconds': perf_counter() - started, 'completed_pairs': count,
        'stopped_on_issue': False}) + '\n')


if __name__ == '__main__':
    from bela.analysis.self_search import SELF_POLICIES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostics', type=Path)
    parser.add_argument('--budgets', type=int, nargs='+', default=[128, 512, 2048])
    parser.add_argument('--matches', type=int, default=0)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--seed', type=int, default=2026102501)
    parser.add_argument('--worker', nargs=2)
    parser.add_argument('--resume', action='store_true', help='Keep completed matches with identical configuration')
    parser.add_argument('--old-policy', choices=SELF_POLICIES, default=MODELS['old'])
    parser.add_argument('--new-policy', choices=SELF_POLICIES, default=MODELS['new'])
    parser.add_argument('--old-samples', type=int, default=128)
    parser.add_argument('--new-samples', type=int, default=128)
    args = parser.parse_args()
    MODELS = {'old': args.old_policy, 'new': args.new_policy}
    MODEL_SAMPLES = {'old': args.old_samples, 'new': args.new_samples}
    if any(not 1 <= n <= 10000 for n in MODEL_SAMPLES.values()):
        parser.error('Trial counts must be between one and 10000')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.worker:
        raise SystemExit(match_worker(args.output, args.worker[0], int(args.worker[1]), args.seed))
    if args.diagnostics:
        if (args.output / 'diagnostics.jsonl').exists():
            raise FileExistsError('Use a fresh diagnostic output folder')
        diagnostic(args.output, args.diagnostics, args.budgets)
    if args.matches:
        with keep_awake():
            matches(args.output, args.start, args.matches, args.seed, args.resume)
