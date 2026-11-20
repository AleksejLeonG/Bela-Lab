"""Known-card endgame accuracy and exact-model estimator checks.

This diagnostic is not a hidden-card or full-match strength test. It compares
root choices with an exact optimal self continuation against the five-profile
mixture. A separate fixed-tactical reference tests like-for-like MC estimates.
"""
import argparse
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
from math import sqrt
from pathlib import Path
from random import Random
import shutil
import statistics
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from bela.analysis.endgame_reference import solve_known_endgame
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.policies import POLICIES, choose_move
from bela.analysis.sampling import SampledDeal
from bela.analysis.self_search import (SELF_POLICIES, SELF_SEARCH, SHARED_SELF_SEARCH,
                                      BELA_CREDIT_SELF_SEARCH, LEARN_EVALUATE_SELF_SEARCH)
from bela.analysis.simulation_bridge import SimulationBridge
from bela.domain.game import Seat
from bela.gameplay.batch import call_deal, dealt_hands, derived_seed
from bela.gameplay.simulation import observe, play_card, resolve_declarations, start_play
from bela.gameplay.tracking import AddEvent, DealSetup, FinishDeclarations, Play, Reveal, UserMatch
from bela.rules.melds import has_belot
from bela.rules.play import legal_cards
from bela.storage.analysis_log import analysis_record, append_analysis
from bela.storage.user_storage import dumps_user_match
from compare_search import keep_awake


MODELS = ('tactical_v1', SELF_SEARCH, SHARED_SELF_SEARCH, BELA_CREDIT_SELF_SEARCH)


def make_cases(seed, count, *, three_card_only=False):
    """Select only by size/legal branching, never by search performance."""
    draw = 0
    skipped = []
    for index in range(count):
        size = 'three_card' if three_card_only else ('two_card' if index < count // 2 else 'three_card')
        played = (24 if size == 'two_card' else 20) + index % 4
        for _ in range(1000):
            draw += 1
            hands = dealt_hands(seed, draw)
            if any(has_belot(hand) for hand in hands):
                skipped.append({'draw': draw, 'reason': 'belot'})
                continue
            dealer = Seat(draw % 4)
            calling, _ = call_deal(hands, dealer)
            state = resolve_declarations(start_play(hands, trump=calling.trump, dealer=dealer, caller=calling.caller))
            contest = state.meld_contest
            history = []
            for ply in range(played):
                actor = state.next_player
                policy = POLICIES[(draw + int(actor)) % len(POLICIES)]
                move = choose_move(observe(state, actor),
                    Random(derived_seed(seed, 'endgame-prefix', draw, ply)), policy)
                history.append(Play(actor, move.card, move.bela))
                state = play_card(state, actor, move.card, announce_bela=move.bela)
            if len(legal_cards(state.hands[state.next_player], state.current_trick, state.trump)) < 2:
                skipped.append({'draw': draw, 'reason': 'forced_root'})
                continue
            own = state.next_player
            setup = DealSetup(own, hands[own], dealer, calling.caller, calling.trump)
            match = UserMatch.start(setup, name=f'Known-card endgame {index}')
            identity = ((derived_seed(seed, 'oracle-id-high', draw, played) << 64) |
                        derived_seed(seed, 'oracle-id-low', draw, played))
            match = replace(match, id=str(UUID(int=identity)))
            for seat in Seat:
                match = match.perform(AddEvent(Reveal(seat, hands[seat])))
            match = match.perform(AddEvent(FinishDeclarations(contest.winning_team)))
            for event in history:
                match = match.perform(AddEvent(event))
            full = SimulationBridge.from_match(match).resume(
                SampledDeal(tuple(sum(1 << c.id for c in hand) for hand in hands)))
            assert full.hands == state.hands and full.current_trick == state.current_trick
            yield {'case': index, 'size': size, 'draw': draw, 'played': played,
                   'trump': calling.trump.value, 'bela_credit':
                   [a.player.team for a in full.bela_announcements],
                   'skipped_before_case': skipped}, match, full
            skipped = []
            break
        else:
            raise RuntimeError('Could not generate a nonforced known-card endgame')


def fingerprint():
    digest = hashlib.sha256()
    source = Path(__file__).resolve().parents[1] / 'src' / 'bela'
    for path in sorted(source.rglob('*.py')):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def reference_cases(root, seed, count, challenges):
    for metadata, match, full in make_cases(seed, count):
        metadata['category'] = 'baseline'
        yield metadata, match, solve_known_endgame(full), solve_known_endgame(full, self_policy='tactical_v1')
    if not challenges:
        return
    accepted = 0
    challenge_seed = derived_seed(seed, 'known-endgame-challenges')
    for metadata, match, full in make_cases(challenge_seed, 256, three_card_only=True):
        exact = solve_known_endgame(full)
        fixed = solve_known_endgame(full, self_policy='tactical_v1')
        meaningful = len(exact['best_cards']) < len(exact['moves'])
        gains = [Fraction(a['objective_fraction']) - Fraction(b['objective_fraction'])
                 for a, b in zip(exact['moves'], fixed['moves'])]
        usable = meaningful and max(gains) > 0
        with (root / 'challenge-screening.jsonl').open('a') as stream:
            stream.write(json.dumps({'seed': challenge_seed, 'draw': metadata['draw'],
                'played': metadata['played'], 'meaningful_root_choice': meaningful,
                'max_optimal_continuation_gain': str(max(gains)), 'accepted': usable}) + '\n')
        if not usable:
            continue
        metadata |= {'case': count + accepted, 'category': 'challenge',
                     'challenge_seed': challenge_seed, 'optimal_continuation_gain': str(max(gains))}
        yield metadata, match, exact, fixed
        accepted += 1
        if accepted == challenges:
            return
    raise RuntimeError('Insufficient challenge positions within the predefined candidate limit')


def run(root, *, seed, cases, challenges, budgets, trial_seeds):
    root.mkdir(parents=True, exist_ok=False)
    config = {'case_seed': seed, 'baseline_cases': cases, 'challenge_cases': challenges,
              'budgets': budgets, 'trial_seeds': trial_seeds,
              'self_models': MODELS, 'opponent_profiles': POLICIES,
              'scope': 'known_cards_and_stated_profile_model_only',
              'selection': 'baseline_nonforced_only; challenges_exact_root_difference_and_future_control_gain; no_MC_selection',
              'engine_source_sha256': fingerprint(), 'python': sys.version,
              'exact_limits': {'max_nodes': 100000, 'seconds': 30}}
    (root / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    shutil.copytree(Path(__file__).resolve().parents[1] / 'src' / 'bela', root / 'source' / 'bela',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(Path(__file__), root / 'benchmark.py')
    measurements, case_records = [], []
    for metadata, match, exact, fixed in reference_cases(root, seed, cases, challenges):
        case = metadata['case']
        before = dumps_user_match(match)
        optimal_values = {r['card']: Fraction(r['objective_fraction']) for r in exact['moves']}
        fixed_values = {r['card']: r for r in fixed['moves']}
        best = max(optimal_values.values())
        meaningful = len(exact['best_cards']) < len(exact['moves'])
        metadata |= {'meaningful_choice': meaningful, 'legal_cards': len(exact['moves'])}
        case_record = {'metadata': metadata, 'input': json.loads(before),
                       'optimal_reference': exact, 'fixed_tactical_reference': fixed}
        (root / f'case-{case:02d}.json').write_text(json.dumps(case_record, indent=2) + '\n')
        case_records.append(case_record)
        for samples in budgets:
            for trial_seed in trial_seeds:
                # Counterbalance version order; do not claim a controlled speed benchmark.
                order = MODELS if (case + trial_seed) % 2 else tuple(reversed(MODELS))
                for model in order:
                    advice = analyze_moves(match, MonteCarloConfig(samples=samples, seconds=30,
                        seed=trial_seed, self_policy=model))
                    record = analysis_record(match, advice, case=case, purpose='known_card_accuracy',
                                             case_seed=seed, trial_seed=trial_seed)
                    append_analysis(root / 'analyses.jsonl', record)
                    if advice['status'] != 'complete' or advice['completed_samples'] != samples:
                        raise RuntimeError(f'Incomplete benchmark at case {case}, {model}')
                    selected = min(advice['moves'], key=lambda r: r['rank'])['card']
                    regret = best - optimal_values[selected]
                    stats = advice['strategy_model']['self_search']
                    row = {'case': case, 'size': metadata['size'], 'meaningful_choice': meaningful,
                           'category': metadata['category'],
                           'model': model, 'samples': samples, 'seed': trial_seed,
                           'selected': selected, 'optimal': selected in exact['best_cards'],
                           'root_regret_points': float(regret), 'root_regret_fraction': str(regret),
                           'seconds': advice['elapsed_seconds'], 'search': stats}
                    row['learning_samples'] = advice.get('completed_learning_samples', 0)
                    row['total_trials'] = advice.get('total_completed_trials', advice['completed_samples'])
                    assert regret >= 0
                    if model == 'tactical_v1':
                        errors = []
                        for move in advice['moves']:
                            reference = fixed_values[move['card']]
                            error = abs(move['objective_mean'] - reference['objective_value'])
                            stderr = sqrt(reference['objective_variance'] / samples)
                            errors.append({'card': move['card'], 'absolute_error': error,
                                           'six_standard_errors': 6*stderr,
                                           'within_six_standard_errors': error <= 6*stderr + 1e-9})
                        row['like_for_like_estimator_checks'] = errors
                        if not all(e['within_six_standard_errors'] for e in errors):
                            (root / 'estimator-warning.json').write_text(json.dumps(row, indent=2))
                            raise RuntimeError('Fixed-policy estimates failed the conservative exact-model check')
                    measurements.append(row)
                    with (root / 'measurements.jsonl').open('a') as stream:
                        stream.write(json.dumps(row) + '\n')
        assert before == dumps_user_match(match)
        print(f'Case {case}: {metadata["size"]}, {len(exact["moves"])} choices, '
              f'exact best {exact["best_cards"]}, {exact["nodes"]} reference nodes', flush=True)
    groups = []
    for samples in budgets:
        for model in MODELS:
            rr = [r for r in measurements if r['model'] == model and r['samples'] == samples]
            choices = [r for r in rr if r['meaningful_choice']]
            groups.append({'model': model, 'samples': samples, 'analyses': len(rr),
                           'optimal_root_choices': sum(r['optimal'] for r in rr),
                           'meaningful_analyses': len(choices),
                           'meaningful_optimal_choices': sum(r['optimal'] for r in choices),
                           'baseline_analyses': sum(r['category'] == 'baseline' for r in rr),
                           'baseline_optimal_choices': sum(r['category'] == 'baseline' and r['optimal'] for r in rr),
                           'challenge_analyses': sum(r['category'] == 'challenge' for r in rr),
                           'challenge_optimal_choices': sum(r['category'] == 'challenge' and r['optimal'] for r in rr),
                           'mean_root_regret_points': statistics.mean(r['root_regret_points'] for r in rr),
                           'max_root_regret_points': max(r['root_regret_points'] for r in rr),
                           'mean_analysis_seconds': statistics.mean(r['seconds'] for r in rr),
                           'mean_total_trials': statistics.mean(r['total_trials'] for r in rr),
                           'nonoptimal_cases': sorted({r['case'] for r in rr if not r['optimal']})})
    checks = [e for r in measurements for e in r.get('like_for_like_estimator_checks', [])]
    assert len(case_records) == cases + challenges
    report = {'cases': len(case_records), 'baseline_cases': cases, 'challenge_cases': challenges,
              'meaningful_positions': sum(c['metadata']['meaningful_choice'] for c in case_records),
              'completed_analyses': len(measurements), 'all_requested_trials_completed': True,
              'fixed_policy_exact_comparisons': len(checks),
              'all_fixed_policy_estimates_within_six_standard_errors': all(e['within_six_standard_errors'] for e in checks) if checks else None,
              'groups': groups, 'engine_source_unchanged': fingerprint() == config['engine_source_sha256'],
              'limits': ['Synthetic known-card diagnostic, not hidden-card playing strength.',
                        'Exact means optimal against this stated opponent mixture, not arbitrary human opponents.',
                        'Regret evaluates the root card assuming optimal self continuation afterward.',
                        'Tree rollout intervals target evolving continuation values, not these optimal values.',
                        'Only fixed-self estimator checks have identical continuation targets.',
                        'Repeated seeds on one position are correlated, not independent games.',
                        'Challenge positions are deliberately selected for root and future-control differences using only exact references.',
                        'No live-advice default or persistent model weights were changed.']}
    assert report['engine_source_unchanged']
    (root / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=2026102504)
    parser.add_argument('--cases', type=int, default=16)
    parser.add_argument('--challenges', type=int, default=4)
    parser.add_argument('--budgets', type=int, nargs='+', default=[128, 512])
    parser.add_argument('--trial-seeds', type=int, nargs='+', default=[7, 42, 119])
    parser.add_argument('--self-models', nargs='+', choices=SELF_POLICIES, default=MODELS)
    args = parser.parse_args()
    MODELS = tuple(args.self_models)
    if not 4 <= args.cases <= 128 or args.cases % 2:
        parser.error('--cases must be even, between four and 128')
    if not 0 <= args.challenges <= 32:
        parser.error('--challenges must be between zero and 32')
    if not 0 <= args.seed < 2**64 or any(not 0 <= s < 2**64 for s in args.trial_seeds):
        parser.error('Seeds must be nonnegative 64-bit integers')
    for count in args.budgets:
        MonteCarloConfig(samples=count)
    with keep_awake():
        run(args.output, seed=args.seed, cases=args.cases, challenges=args.challenges,
            budgets=args.budgets, trial_seeds=args.trial_seeds)
