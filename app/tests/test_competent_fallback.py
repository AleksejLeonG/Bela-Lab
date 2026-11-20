"""Competent cold-state fallback, fixed trial styles and unchanged learning."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch

from bela.analysis.learned_policy import (COMPETENT_FALLBACK_PROFILES,
    FrozenSelfPolicy, fallback_profile)
from bela.analysis.policies import _choose_from_legal
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
import bela.analysis.monte_carlo as mc
from bela.analysis.rollout_random import TrialRandomness
from bela.analysis.self_search import (COMPETENT_LEARN_EVALUATE_SELF_SEARCH,
    LEARN_EVALUATE_SELF_SEARCH, information_key)
from bela.gameplay.simulation import observe
from bela.rules.play import legal_cards
from bela.storage.user_storage import loads_user_match
from test_endgame_reference import known_endgame


class CompetentFallbackTests(unittest.TestCase):
    def test_competent_fallback_fixes_low_budget_planning_regression(self):
        for seed in (7, 42, 119):
            with self.subTest(seed=seed):
                result = analyze_moves(self.fixture(), MonteCarloConfig(samples=128, seconds=30,
                    seed=seed, self_policy=COMPETENT_LEARN_EVALUATE_SELF_SEARCH))
                self.assertEqual(result['status'], 'complete')
                self.assertEqual(result['moves'][0]['card'], 'S_8')
                self.assertEqual(result['total_completed_trials'], 256)

    def view(self):
        _, state = known_endgame()
        view = observe(state, state.next_player)
        return view, legal_cards(view.hand, view.current_trick, view.trump)

    def fixture(self):
        return loads_user_match((Path(__file__).parent / 'fixtures' / 'known_endgame_planning.json').read_text())

    def test_only_competent_profiles_handle_unseen_and_incomplete_nodes(self):
        view, legal = self.view()
        for nodes in ({}, {information_key(view): {legal[0]: (1, 1), legal[1]: (0, 0)}}):
            policy = FrozenSelfPolicy(nodes, fallback_mode='competent_mix_v1')
            with patch('bela.analysis.learned_policy._choose_from_legal', wraps=_choose_from_legal) as chooser:
                for profile in COMPETENT_FALLBACK_PROFILES:
                    result = policy.select(view, legal, Random(3), fallback_policy=profile)
                    self.assertIn(result, legal)
                    self.assertEqual(chooser.call_args.args[2], profile)
                self.assertEqual(chooser.call_count, 3)
            self.assertEqual(policy.statistics()['fallback_profile_weights'], {p: 1/3 for p in COMPETENT_FALLBACK_PROFILES})
            with self.assertRaises(ValueError):
                policy.select(view, legal, Random(3), fallback_policy='random_v1')

    def test_learned_choices_override_fallback_without_mutating_values(self):
        view, legal = self.view()
        source = {information_key(view): {legal[0]: [1, .9], legal[1]: [10, 1]}}
        before = deepcopy(source)
        policy = FrozenSelfPolicy(source, fallback_mode='competent_mix_v1')
        with patch('bela.analysis.learned_policy._choose_from_legal', side_effect=AssertionError('Learned node used fallback')):
            for profile in COMPETENT_FALLBACK_PROFILES:
                self.assertEqual(policy.select(view, legal, Random(4), fallback_policy=profile), legal[0])
        self.assertEqual(source, before)
        self.assertEqual(policy.statistics()['attempted_value_selections'], 3)

    def test_each_fallback_move_uses_only_one_paired_tie_break(self):
        view, legal = self.view()
        policy = FrozenSelfPolicy({}, fallback_mode='competent_mix_v1')
        draws = TrialRandomness(91)
        for profile in COMPETENT_FALLBACK_PROFILES:
            draw = draws.at(12)
            self.assertIn(policy.select(view, legal, draw, fallback_policy=profile), legal)
            self.assertTrue(draw.used)

    def test_style_schedule_is_repeatable_and_contains_only_the_three_profiles(self):
        one = [fallback_profile('match', 42, i) for i in range(128)]
        two = [fallback_profile('match', 42, i) for i in range(128)]
        self.assertEqual(one, two)
        self.assertEqual(set(one), set(COMPETENT_FALLBACK_PROFILES))

    def test_hidden_private_hands_cannot_change_the_fallback_choice(self):
        _, state = known_endgame()
        own = state.next_player
        other = [s for s in range(4) if s != own]
        hands = list(state.hands)
        hands[other[0]], hands[other[1]] = hands[other[1]], hands[other[0]]
        one, two = observe(state, own), observe(replace(state, hands=tuple(hands)), own)
        legal = legal_cards(one.hand, one.current_trick, one.trump)
        policy = FrozenSelfPolicy({}, fallback_mode='competent_mix_v1')
        for profile in COMPETENT_FALLBACK_PROFILES:
            self.assertEqual(policy.select(one, legal, Random(7), fallback_policy=profile),
                             policy.select(two, legal, Random(7), fallback_policy=profile))

    def test_one_style_per_evaluation_trial_and_identical_training_and_sampling(self):
        match = self.fixture()
        original_freeze, original_sample = mc.FrozenSelfPolicy, mc.HandSampler.sample
        original_profile, original_select = mc.fallback_profile, FrozenSelfPolicy.select
        snapshots, sampling_seeds, assignments = [], [], []
        active = [None]
        def freeze(nodes, **kwargs):
            snapshots.append(deepcopy(nodes))
            return original_freeze(nodes, **kwargs)
        def sample(sampler, *args, **kwargs):
            sampling_seeds.append(kwargs['seed'])
            return original_sample(sampler, *args, **kwargs)
        def assigned(match_id, seed, trial):
            active[0] = original_profile(match_id, seed, trial)
            assignments.append((trial, active[0]))
            return active[0]
        def selected(policy, *args, **kwargs):
            if policy.fallback_mode == 'competent_mix_v1':
                self.assertEqual(kwargs['fallback_policy'], active[0])
            return original_select(policy, *args, **kwargs)
        with patch.object(mc, 'FrozenSelfPolicy', freeze), patch.object(mc.HandSampler, 'sample', sample), \
             patch.object(mc, 'fallback_profile', assigned), patch.object(FrozenSelfPolicy, 'select', selected):
            first = analyze_moves(match, MonteCarloConfig(samples=8, learning_samples=12, seconds=30,
                self_policy=LEARN_EVALUATE_SELF_SEARCH))
            old_seeds = sampling_seeds[:]
            sampling_seeds.clear()
            second = analyze_moves(match, MonteCarloConfig(samples=8, learning_samples=12, seconds=30,
                self_policy=COMPETENT_LEARN_EVALUATE_SELF_SEARCH))
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(old_seeds, sampling_seeds)
        self.assertEqual([i for i, _ in assignments], list(range(8)))
        self.assertEqual(first['strategy_model']['other_player_weights'], second['strategy_model']['other_player_weights'])
        self.assertEqual(second['completed_learning_samples'], 12)
        self.assertEqual(second['completed_samples'], 8)
        self.assertEqual(second['strategy_model']['self_search']['evaluation']['fallback_policy'], 'competent_mix_v1')


if __name__ == '__main__':
    unittest.main()
