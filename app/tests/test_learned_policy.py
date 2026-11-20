"""Learning/evaluation separation, information boundaries and planning regression."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from random import Random
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bela.analysis.learned_policy import FrozenSelfPolicy, learning_seed
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
import bela.analysis.monte_carlo as mc
from bela.analysis.self_search import LEARN_EVALUATE_SELF_SEARCH, SelfSearch, information_key
from bela.gameplay.simulation import observe
from bela.rules.play import legal_cards
from bela.storage.user_storage import loads_user_match
from test_endgame_reference import known_endgame


class LearnedPolicyTests(unittest.TestCase):
    def fixture(self):
        return loads_user_match((Path(__file__).parent / 'fixtures' / 'known_endgame_planning.json').read_text())

    def config(self, **kwargs):
        return MonteCarloConfig(**({'samples': 8, 'seconds': 30,
            'self_policy': LEARN_EVALUATE_SELF_SEARCH} | kwargs))

    def test_greedy_snapshot_is_deeply_frozen_and_has_no_exploration_bonus(self):
        _, state = known_endgame()
        view = observe(state, state.next_player)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        key = information_key(view)
        source = {key: {legal[0]: [1, 0.8], legal[1]: [100, 50.0]}}
        policy = FrozenSelfPolicy(source)
        source[key][legal[0]][1] = 0.0
        before = {k: dict(v) for k, v in policy.nodes.items()}
        for seed in range(40):
            self.assertEqual(policy.select(view, legal, Random(seed)), legal[0])
        self.assertEqual(before, {k: dict(v) for k, v in policy.nodes.items()})
        with self.assertRaises(TypeError):
            policy.nodes[key][legal[0]] = (99, 0)
        self.assertEqual(policy.statistics()['attempted_exploration_selections'], 0)

    def test_unseen_and_incomplete_states_use_uniform_legal_fallback(self):
        _, state = known_endgame()
        view = observe(state, state.next_player)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        class Last:
            def randrange(self, stop):
                self.stop = stop
                return stop - 1
        unseen = FrozenSelfPolicy({})
        draw = Last()
        self.assertEqual(unseen.select(view, legal, draw), legal[-1])
        self.assertEqual(draw.stop, len(legal))
        incomplete = FrozenSelfPolicy({information_key(view): {legal[0]: (2, 2), legal[1]: (0, 0)}})
        self.assertEqual(incomplete.select(view, legal, Last()), legal[-1])
        self.assertEqual(incomplete.statistics()['fallback_incomplete_selections'], 1)

    def test_snapshot_does_not_depend_on_other_private_hands(self):
        _, state = known_endgame()
        own = state.next_player
        other = [s for s in range(4) if s != own]
        hands = list(state.hands)
        hands[other[0]], hands[other[1]] = hands[other[1]], hands[other[0]]
        one, two = observe(state, own), observe(replace(state, hands=tuple(hands)), own)
        legal = legal_cards(one.hand, one.current_trick, one.trump)
        policy = FrozenSelfPolicy({information_key(one): {c: (2, 1) for c in legal}})
        self.assertEqual(policy.select(one, legal, Random(9)), policy.select(two, legal, Random(9)))

    def test_learning_outcomes_never_enter_evaluation_estimates_or_update_frozen_values(self):
        match = self.fixture()
        team, caller = match.initial.player.team, match.initial.caller.team
        stage = {'frozen': False}
        original_select, original_commit = SelfSearch.select, SelfSearch.commit
        counts = {'select': 0, 'commit': 0}
        def selected(tree, *args):
            self.assertFalse(stage['frozen'])
            counts['select'] += 1
            return original_select(tree, *args)
        def committed(tree, *args):
            self.assertFalse(stage['frozen'])
            counts['commit'] += 1
            return original_commit(tree, *args)
        def freeze(nodes):
            stage['frozen'] = True
            stage['before'] = deepcopy(nodes)
            stage['source'] = nodes
            return FrozenSelfPolicy(nodes)
        def settled(state):
            scores = [0, 0]
            scores[1-team if stage['frozen'] else team] = 162
            own_success = not stage['frozen']
            return SimpleNamespace(recorded=tuple(scores),
                caller_passed=own_success if team == caller else not own_success)
        with patch.object(SelfSearch, 'select', selected), patch.object(SelfSearch, 'commit', committed), \
             patch.object(mc, 'FrozenSelfPolicy', freeze), patch.object(mc, 'settle_play', settled):
            result = analyze_moves(match, self.config(learning_samples=12))
        self.assertEqual((result['completed_learning_samples'], result['completed_samples']), (12, 8))
        self.assertEqual(result['total_completed_trials'], 20)
        self.assertEqual(result['sampled_deals'], 20)
        self.assertEqual(counts, {'select': 72, 'commit': 36})
        self.assertEqual(stage['before'], stage['source'])
        self.assertTrue(all(r['samples'] == 8 and r['expected_point_difference'] == -162
                            and r['success_probability'] == 0 for r in result['moves']))
        self.assertEqual(result['interval_target'], 'fixed_learned_policy_conditional_on_training')

    def test_evaluation_worlds_and_latent_lineups_use_original_independent_stream(self):
        match = self.fixture()
        original_sample = mc.HandSampler.sample
        original_lineup = mc.StrategyLineup.for_trial
        seeds, lineups = [], []
        def sample(sampler, *args, **kwargs):
            seeds.append(kwargs['seed'])
            return original_sample(sampler, *args, **kwargs)
        def lineup(*args):
            lineups.append(args[1:3])
            return original_lineup(*args)
        with patch.object(mc.HandSampler, 'sample', sample), patch.object(mc.StrategyLineup, 'for_trial', lineup):
            result = analyze_moves(match, self.config(learning_samples=12))
            trained_seeds, trained_lineups = seeds[:], lineups[:]
            seeds.clear(); lineups.clear()
            analyze_moves(match, MonteCarloConfig(samples=8, seconds=30))
        self.assertEqual(result['completed_samples'], 8)
        self.assertEqual(trained_seeds[12:], seeds)
        self.assertEqual(trained_lineups[12:], lineups)
        self.assertNotEqual(trained_seeds[:8], seeds)
        self.assertNotEqual(learning_seed(42, match.id), 42)

    def test_cancelled_learning_cannot_produce_probabilities(self):
        match = self.fixture()
        stopped = Event()
        original = SelfSearch.select
        def select(tree, *args):
            result = original(tree, *args)
            stopped.set()
            return result
        with patch.object(SelfSearch, 'select', select):
            result = analyze_moves(match, self.config(), cancelled=stopped.is_set)
        self.assertEqual((result['completed_samples'], result['completed_learning_samples']), (0, 0))
        self.assertEqual(result['discarded_trials'], 1)
        self.assertTrue(all(r['success_probability'] is None for r in result['moves']))
        self.assertEqual(result['strategy_model']['self_search']['committed_actions'], 0)

    def test_interrupted_evaluation_discards_the_entire_paired_trial(self):
        match = self.fixture()
        stopped = Event()
        original = FrozenSelfPolicy.select
        calls = [0]
        def selected(policy, *args):
            result = original(policy, *args)
            calls[0] += 1
            if calls[0] == 7:  # Six self selections make one complete paired trial.
                stopped.set()
            return result
        with patch.object(FrozenSelfPolicy, 'select', selected):
            result = analyze_moves(match, self.config(learning_samples=4), cancelled=stopped.is_set)
        self.assertEqual((result['completed_learning_samples'], result['completed_samples']), (4, 1))
        self.assertEqual(result['discarded_trials'], 1)
        self.assertTrue(all(r['samples'] == 1 for r in result['moves']))
        self.assertEqual(result['strategy_model']['self_search']['committed_actions'], 24)

    def test_planning_regression_now_chooses_spade_eight(self):
        match = self.fixture()
        result = analyze_moves(match, self.config(samples=512, seed=42))
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['moves'][0]['card'], 'S_8')
        self.assertEqual(result['completed_learning_samples'], 512)
        self.assertEqual(result['completed_samples'], 512)

    def test_learning_time_cap_reserves_budget_for_evaluation(self):
        clock = [0.0]
        original = SelfSearch.commit
        def committed(tree, *args):
            original(tree, *args)
            clock[0] = 16.0  # Half of the 30-second budget has elapsed.
        with patch.object(mc, 'monotonic', lambda: clock[0]), patch.object(SelfSearch, 'commit', committed):
            result = analyze_moves(self.fixture(), self.config())
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['completed_learning_samples'], 1)
        self.assertEqual(result['completed_samples'], 8)

    def test_invalid_learning_budgets_are_rejected_and_forced_moves_do_no_learning(self):
        for value in (0, -1, True, 10_001):
            with self.assertRaises(ValueError):
                self.config(learning_samples=value)
        with self.assertRaises(ValueError):
            MonteCarloConfig(learning_samples=4)
        match, _ = known_endgame(played=28)
        result = analyze_moves(match, self.config())
        self.assertEqual(result['status'], 'forced_move')
        self.assertEqual(result['total_completed_trials'], 0)


if __name__ == '__main__':
    unittest.main()
