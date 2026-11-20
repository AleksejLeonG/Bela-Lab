"""Replay paired search experiments and compare shared-deal results."""
import argparse
import json
from pathlib import Path
from random import Random

from bela.gameplay.batch import trick_point_history
from bela.gameplay.session import initial_hands
from bela.storage.persistence import load_match
from bela.storage.user_storage import loads_user_match

POLICIES = {'old': 'information_set_tree_v1', 'new': 'shared_information_set_tree_v2'}


def audit(root):
    config = json.loads((root / 'config.json').read_text())
    policies = config['models']
    pairs, details = [], []
    decision_count = trial_count = 0
    for index in range(config['start'], config['start'] + config['count']):
        results = {}
        for model, policy in policies.items():
            expected_samples = config['samples'][model] if isinstance(config['samples'], dict) else config['samples']
            folder = root / model / f'match-{index}'
            row = json.loads((folder / 'matches.jsonl').read_text())
            path = folder / 'games' / f'match-{index:06d}.sim.json'
            session = load_match(path)
            raw_deals = json.loads(path.read_text())['match']['deals']
            assert row['status'] == 'complete'
            assert list(session.score) == row['score'] and session.winner == row['winner']
            assert len(session.deals) == len(row['deals'])
            journal = [json.loads(line) for line in (folder / 'analyses.jsonl').read_text().splitlines()]
            assert journal == row['decision_estimates']
            assert len(journal) == row['decisions']
            assert row['completed_trials'] == expected_samples * row['mc_decisions']
            learning_trials = sum(e['advice'].get('completed_learning_samples', 0) for e in journal)
            if 'total_completed_trials' in row:
                assert row['completed_learning_trials'] == learning_trials
                assert row['total_completed_trials'] == row['completed_trials'] + learning_trials
            seconds, coverage = [], [0, 0, 0]
            for entry in journal:
                match = loads_user_match(json.dumps(entry['input']))
                advice, context = entry['advice'], entry['context']
                assert entry['provenance'] == 'original_analysis'
                assert match.revision == advice['revision']
                assert advice['config']['self_policy'] == policy
                assert advice['strategy_model']['self_policy'] == policy
                assert set(r['card'] for r in advice['moves']) == set(map(str, match.state.legal_actions))
                actions = [a for a in raw_deals[context['deal_index']]['actions'] if a['type'] == 'play_card']
                applied = actions[context['ply']]
                assert applied['player'] == row['player']
                assert context['selected_move'] == {'card': applied['card'], 'bela': applied['bela']}
                assert '"hands"' not in json.dumps(entry)
                if advice['status'] == 'forced_move':
                    assert advice['completed_samples'] == 0
                    assert all(r['success_probability'] is None for r in advice['moves'])
                else:
                    assert advice['status'] == 'complete' and advice['completed_samples'] == expected_samples
                    assert all(r['samples'] == expected_samples and 0 <= r['success_probability'] <= 1
                               for r in advice['moves'])
                    seconds.append(advice['elapsed_seconds'])
                chosen = min(advice['moves'], key=lambda r: r['rank']) if advice['status'] == 'complete' else advice['moves'][0]
                assert context['selected_move'] == {'card': chosen['card'], 'bela': chosen['bela']}
                stats = advice['strategy_model']['self_search']
                if policy == 'bela_credit_shared_tree_v3':
                    assert stats['bela_credit_compatibility_guard'] is True
                if policy in ('learn_then_evaluate_v1', 'learn_then_evaluate_v2') and advice['status'] != 'forced_move':
                    assert advice['interval_target'] == 'fixed_learned_policy_conditional_on_training'
                    assert stats['evaluation']['values_frozen'] is True
                    if policy == 'learn_then_evaluate_v2':
                        ev = stats['evaluation']
                        assert ev['fallback_policy'] == 'competent_mix_v1'
                        assert set(ev['fallback_profile_weights']) == {'cautious_v1', 'counting_v1', 'tactical_v1'}
                        assert sum(ev['fallback_profile_selections'].values()) == (
                            ev['fallback_unseen_selections'] + ev['fallback_incomplete_selections'])
                stats = stats.get('evaluation') or stats
                coverage[0] += stats['selections'] - stats['attempted_forced_selections']
                coverage[1] += stats['attempted_value_selections']
                coverage[2] += stats.get('attempted_shared_value_selections', 0)
            for state, deal in zip(session.deals, row['deals']):
                assert state.finished
                assert deal['tricks'] == trick_point_history(state)
                if not deal['belot']:
                    assert len(state.completed_tricks) == 8
                    assert sum(deal['tricks'][-1]['cumulative_card_points']) == 152
            details.append({'model': model, 'index': index, 'score': row['score'],
                'win': row['our_win'], 'deals': len(row['deals']), 'analyses': len(seconds),
                'analysis_seconds': sum(seconds), 'max_analysis_seconds': max(seconds, default=0),
                'elapsed_seconds': row['elapsed_seconds'], 'search_selections': coverage,
                'evaluation_trials': row['completed_trials'], 'learning_trials': learning_trials,
                'total_trials': row['completed_trials'] + learning_trials})
            decision_count += len(journal)
            trial_count += row['completed_trials']
            results[model] = (row, session)
        old, os = results['old']
        new, ns = results['new']
        for field in ('match_seed', 'match_id', 'player', 'team', 'initial_dealer', 'profiles', 'calling_policy'):
            assert old[field] == new[field]
        changes, contracts = [], {'old': [0, 0], 'new': [0, 0]}
        team = new['team']
        for od, nd, ost, nst in zip(old['deals'], new['deals'], os.deals, ns.deals):
            assert initial_hands(ost) == initial_hands(nst)
            for field in ('dealer', 'caller', 'trump', 'calling'):
                assert od[field] == nd[field]
            before = od['recorded'][team] - od['recorded'][1 - team]
            after = nd['recorded'][team] - nd['recorded'][1 - team]
            changes.append(after - before)
            for model, deal in (('old', od), ('new', nd)):
                if deal['caller'] % 2 == team:
                    contracts[model][0] += int(deal['caller_passed'])
                    contracts[model][1] += 1
        pairs.append({'index': index, 'old_win': old['our_win'], 'new_win': new['our_win'],
            'shared_deals': len(changes), 'net_change': sum(changes), 'deal_changes': changes,
            'own_contracts_passed_and_called': contracts})
        print(f'Audited pair {index}: {len(changes)} shared deals, net change {sum(changes):+}', flush=True)
    total_deals = sum(p['shared_deals'] for p in pairs)
    rng = Random(2026102502)
    boot = []
    for _ in range(5000):
        sample = rng.choices(pairs, k=len(pairs))
        boot.append(sum(p['net_change'] for p in sample) / sum(p['shared_deals'] for p in sample))
    boot.sort()
    report = {'pairs': pairs, 'details': details, 'paired_matches': len(pairs),
        'old_wins': sum(p['old_win'] for p in pairs), 'new_wins': sum(p['new_win'] for p in pairs),
        'shared_deals': total_deals, 'mean_net_change_per_shared_deal': sum(p['net_change'] for p in pairs) / total_deals,
        'match_cluster_bootstrap_95_percent': [boot[124], boot[4874]],
        'journal_records_audited': decision_count, 'completed_trials': trial_count,
        'full_replays_and_trick_histories_verified': True,
        'mean_analysis_seconds': {m: sum(d['analysis_seconds'] for d in details if d['model'] == m) /
            sum(d['analyses'] for d in details if d['model'] == m) for m in POLICIES},
        'all_workers_finished': (root / 'run-summary.json').exists()}
    interrupted = list((root / 'interrupted').glob('*/*/match-*/matches.jsonl'))
    report['archived_interrupted_attempts_excluded'] = len(interrupted)
    report['models'] = policies
    report['trial_cost_by_model'] = {model: {
        'evaluation': sum(d['evaluation_trials'] for d in details if d['model'] == model),
        'learning': sum(d['learning_trials'] for d in details if d['model'] == model),
        'total': sum(d['total_trials'] for d in details if d['model'] == model)} for model in policies}
    report['runtime_note'] = ('Per-decision timings use completed attempts only; run-summary elapsed time '
                              'covers the final invocation when an experiment was resumed.')
    report['small_match_screen_passed'] = (
        report['mean_net_change_per_shared_deal'] >= -5 and
        report['new_wins'] >= report['old_wins'] - 1)
    report['own_contracts_on_shared_deals'] = {model: {
        'passed': sum(p['own_contracts_passed_and_called'][model][0] for p in pairs),
        'called': sum(p['own_contracts_passed_and_called'][model][1] for p in pairs)} for model in POLICIES}
    report['future_value_guided_fraction'] = {model:
        sum(sum(d['search_selections'][1:]) for d in details if d['model'] == model) /
        sum(d['search_selections'][0] for d in details if d['model'] == model) for model in POLICIES}
    report['win_flips'] = {
        'loss_to_win': sum(not p['old_win'] and p['new_win'] for p in pairs),
        'win_to_loss': sum(p['old_win'] and not p['new_win'] for p in pairs)}
    changes = [change for p in pairs for change in p['deal_changes']]
    report['shared_deal_changes'] = {'improved': sum(c > 0 for c in changes),
                                   'tied': sum(c == 0 for c in changes),
                                   'worse': sum(c < 0 for c in changes)}
    (root / 'validation-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('pairs', 'details')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    audit(parser.parse_args().root)
