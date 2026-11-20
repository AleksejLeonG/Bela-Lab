"""Direct competent Monte Carlo: fixed style mixture, no tree or learning."""
from fractions import Fraction
from math import sqrt
from pathlib import Path
import unittest
from unittest.mock import patch

import bela.analysis.monte_carlo as mc
from bela.analysis.endgame_reference import solve_known_endgame
from bela.analysis.learned_policy import COMPETENT_FALLBACK_PROFILES, fallback_profile
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.self_search import DIRECT_COMPETENT_SELF_POLICY
from bela.storage.user_storage import loads_user_match
from test_endgame_reference import known_endgame


class DirectCompetentTests(unittest.TestCase):
    def config(self, **kwargs):
        return MonteCarloConfig(**({'samples': 8, 'seconds': 30,
            'self_policy': DIRECT_COMPETENT_SELF_POLICY} | kwargs))

    def test_no_tree_or_training_and_one_style_for_all_candidates(self):
        match = loads_user_match((Path(__file__).parent / 'fixtures' / 'known_endgame_planning.json').read_text())
        original_choose = mc._choose_from_legal
        assignments, styles = [], []
        active = [None]
        def assigned(match_id, seed, trial):
            active[0] = fallback_profile(match_id, seed, trial)
            assignments.append(trial)
            return active[0]
        def choose(view, rng, policy, legal):
            if view.player == match.initial.player:
                self.assertEqual(policy, active[0])
                self.assertIn(policy, COMPETENT_FALLBACK_PROFILES)
                styles.append(policy)
            return original_choose(view, rng, policy, legal)
        with patch.object(mc, 'SelfSearch', side_effect=AssertionError('Direct mode made a tree')), \
             patch.object(mc, 'FrozenSelfPolicy', side_effect=AssertionError('Direct mode froze a tree')), \
             patch.object(mc, 'learning_seed', side_effect=AssertionError('Direct mode started learning')), \
             patch.object(mc, 'fallback_profile', assigned), patch.object(mc, '_choose_from_legal', choose):
            result = analyze_moves(match, self.config())
        self.assertEqual(assignments, list(range(8)))
        self.assertTrue(styles)
        self.assertEqual(result['completed_learning_samples'], 0)
        self.assertEqual(result['total_completed_trials'], 8)
        self.assertIsNone(result['strategy_model']['self_search'])
        self.assertEqual(result['strategy_model']['self_profile_weights'], {p: 1/3 for p in COMPETENT_FALLBACK_PROFILES})
        self.assertEqual(len(result['strategy_model']['other_player_weights']), 5)
        self.assertEqual(result['interval_target'], 'fixed_policy_rollout_value')

    def test_direct_estimates_match_exact_fixed_profile_mixture(self):
        match, state = known_endgame(played=20)
        references = [solve_known_endgame(state, self_policy=p) for p in COMPETENT_FALLBACK_PROFILES]
        result = analyze_moves(match, self.config(samples=600, seed=119))
        self.assertEqual(result['completed_samples'], 600)
        for row in result['moves']:
            rr = [next(r for r in ref['moves'] if r['card'] == row['card']) for ref in references]
            means = [Fraction(r['objective_fraction']) for r in rr]
            mean = sum(means)/3
            second = sum(Fraction(r['objective_variance_fraction']) + m*m for r,m in zip(rr,means))/3
            variance = second - mean*mean
            probability = sum(Fraction(r['success_fraction']) for r in rr)/3
            self.assertLessEqual(abs(row['objective_mean']-float(mean)), 6*sqrt(float(variance)/600)+1e-9)
            self.assertLessEqual(abs(row['success_probability']-float(probability)),
                                 6*sqrt(float(probability*(1-probability))/600)+1e-9)

    def test_exact_endgame_integrates_fixed_profiles_and_respects_the_work_limit(self):
        match, state = known_endgame(played=20)
        references = [solve_known_endgame(state, self_policy=p) for p in COMPETENT_FALLBACK_PROFILES]
        config = self.config(exact_endgame=True)
        result = analyze_moves(match, config)
        self.assertEqual(result['status'], 'exact_endgame')
        self.assertEqual(result['exact_layouts'], 1)
        self.assertEqual(result['completed_samples'], 0)
        self.assertEqual(result['moves'], analyze_moves(
            match, self.config(exact_endgame=True, samples=80, seed=123))['moves'])
        for row in result['moves']:
            reference_rows = [next(r for r in ref['moves'] if r['card'] == row['card']) for ref in references]
            expected = sum(Fraction(r['objective_fraction']) for r in reference_rows) / len(reference_rows)
            self.assertEqual(row['objective_mean'], float(expected))
            expected_success = sum(Fraction(r['success_fraction']) for r in reference_rows) / len(reference_rows)
            self.assertEqual(row['success_probability'], float(expected_success))
        with patch.object(mc.exact_endgame, 'MAX_NODES', 1):
            fallback = analyze_moves(match, config)
        self.assertEqual(fallback['method'], 'direct_competent_monte_carlo_v1')
        self.assertEqual(fallback['completed_samples'], config.samples)
        self.assertEqual(fallback['moves'], analyze_moves(match, self.config())['moves'])

    def test_extra_trials_extend_the_same_rollout_sequence(self):
        match, _ = known_endgame(played=20)
        base_choose = mc._choose_from_legal

        def choices(samples):
            selected = []

            def record(view, rng, policy, legal):
                move = base_choose(view, rng, policy, legal)
                selected.append((view, policy, move))
                return move

            with patch.object(mc, '_choose_from_legal', side_effect=record):
                result = analyze_moves(match, self.config(samples=samples))
            self.assertEqual(result['completed_samples'], samples)
            return selected

        quick = choices(4)
        deep = choices(12)
        self.assertTrue(quick)
        self.assertGreater(len(deep), len(quick))
        self.assertEqual(quick, deep[:len(quick)])

    def test_direct_mode_rejects_a_learning_budget(self):
        with self.assertRaises(ValueError):
            self.config(learning_samples=8)


if __name__ == '__main__':
    unittest.main()
