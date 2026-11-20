"""Future self search, public information boundaries and completed rewards."""

from dataclasses import replace
from random import Random
from threading import Event
import unittest
from unittest.mock import patch

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.policies import choose_move
from bela.analysis.self_search import (SELF_SEARCH, SHARED_SELF_SEARCH, SelfSearch,
                                       BELA_CREDIT_SELF_SEARCH, BelaCreditSelfSearch,
                                       SharedSelfSearch, information_key, shared_context)
from bela.domain.cards import Card, Rank
from bela.domain.game import Seat
from bela.domain.melds import BelaAnnouncement
from bela.gameplay.simulation import observe
from bela.rules.play import legal_cards
from test_monte_carlo import endgame


class SelfSearchTests(unittest.TestCase):
    def credit_views(self):
        _, state = endgame()
        view = observe(state, state.next_player)
        def announced(offset, trick=0):
            player = Seat((int(view.player) + offset) % 4)
            return replace(view, bela_announcements=(
                BelaAnnouncement(player, Card(view.trump, Rank.QUEEN), trick, 0),))
        return view, announced(0), announced(2, 1), announced(1), announced(3, 2)

    def test_bela_guard_has_only_three_public_credit_states(self):
        none, own, partner, opponent, other_opponent = self.credit_views()
        legal = legal_cards(none.hand, none.current_trick, none.trump)
        tree = BelaCreditSelfSearch()
        keys = [tree.context(v, legal) for v in (none, own, partner, opponent, other_opponent)]
        self.assertEqual(len(set(keys)), 3)
        self.assertEqual(keys[1], keys[2])
        self.assertEqual(keys[3], keys[4])
        # Unguarded v2 still deliberately merges all these contexts.
        self.assertEqual(len({shared_context(v, legal) for v in (none, own, opponent)}), 1)

    def test_bela_guard_does_not_borrow_across_credit_states(self):
        none, own, _, opponent, _ = self.credit_views()
        legal = legal_cards(none.hand, none.current_trick, none.trump)
        tree, rng = BelaCreditSelfSearch(), Random(4)
        for _ in range(12):
            _, edge = tree.select(none, legal, rng)
            tree.commit([edge], 0.5)
        for view in (own, opponent):
            tree.select(view, legal, rng)
            self.assertEqual(tree.shared_selections, 0)
            self.assertTrue(all(row[0] == 0 for row in tree.pools[tree.context(view, legal)].values()))
        self.assertEqual(len(tree.pools), 3)

    def test_bela_guard_retains_borrowing_within_same_team_credit(self):
        _, own, partner, _, _ = self.credit_views()
        legal = legal_cards(own.hand, own.current_trick, own.trump)
        tree, rng = BelaCreditSelfSearch(), Random(4)
        for _ in range(12):
            _, edge = tree.select(own, legal, rng)
            tree.commit([edge], 0.5)
        _, edge = tree.select(partner, legal, rng)
        self.assertEqual(tree.shared_selections, 1)
        self.assertEqual(sum(r[0] for r in tree.nodes[edge[0]].values()), 0)
        self.assertTrue(tree.statistics()['bela_credit_compatibility_guard'])

    def test_shared_prior_requires_other_histories_and_completed_rewards(self):
        _, state = endgame()
        view = observe(state, state.next_player)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        tree = SharedSelfSearch()
        rng = Random(19)
        for _ in range(12):
            card, edge = tree.select(view, legal, rng)
            tree.commit([edge], int(card == legal[0]))
        self.assertEqual(tree.shared_selections, 0)  # No double counting itself.
        other = replace(view, match_score=(300, 250))
        self.assertNotEqual(information_key(view), information_key(other))
        self.assertEqual(shared_context(view, legal), shared_context(other, legal))
        before = {c: row[:] for c, row in tree.pools[shared_context(view, legal)].items()}
        card, edge = tree.select(other, legal, rng)
        self.assertEqual(tree.shared_selections, 1)
        self.assertEqual(before, tree.pools[shared_context(view, legal)])
        self.assertTrue(all(row[0] == 0 for row in tree.nodes[information_key(other)].values()))
        tree.commit([edge], 1)
        self.assertEqual(tree.nodes[information_key(other)][card], [1, 1.0])
        self.assertEqual(tree.pools[edge[2]][card][0], before[card][0] + 1)

    def test_shared_search_respects_hidden_worlds_and_cancellation(self):
        match, state = endgame()
        actor = state.next_player
        others = [s for s in range(4) if s != actor]
        hands = list(state.hands)
        hands[others[0]], hands[others[1]] = hands[others[1]], hands[others[0]]
        one, two = observe(state, actor), observe(replace(state, hands=tuple(hands)), actor)
        legal = legal_cards(one.hand, one.current_trick, one.trump)
        self.assertEqual(shared_context(one, legal), shared_context(two, legal))
        self.assertEqual(SharedSelfSearch().select(one, legal, Random(5)),
                         SharedSelfSearch().select(two, legal, Random(5)))
        stopped = Event()
        original = SharedSelfSearch.select
        def stop(tree, *args):
            result = original(tree, *args)
            stopped.set()
            return result
        with patch.object(SharedSelfSearch, 'select', stop):
            result = analyze_moves(match, MonteCarloConfig(seconds=30, self_policy=SHARED_SELF_SEARCH),
                                   cancelled=stopped.is_set)
        self.assertEqual(result['completed_samples'], 0)
        self.assertEqual(result['strategy_model']['self_search']['committed_actions'], 0)
        self.assertEqual(result['strategy_model']['future_replanning'],
                         'approximate_shared_information_set_tree')

    def test_action_values_learn_to_prefer_higher_simulated_rewards(self):
        _, state = endgame()
        view = observe(state, state.next_player)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        tree, rng = SelfSearch(), Random(19)
        for _ in range(100):
            card, edge = tree.select(view, legal, rng)
            tree.commit([edge], int(card == legal[0]))
        node = tree.nodes[information_key(view)]
        self.assertGreater(node[legal[0]][0], node[legal[1]][0])
        self.assertEqual(tree.statistics()['committed_actions'], 100)
        self.assertEqual(tree.statistics()['decision_nodes'], 1)
        self.assertEqual(tree.statistics()['decision_nodes_fully_expanded'], 1)
        self.assertEqual(tree.statistics()['attempted_exploration_selections'], 2)
        self.assertEqual(tree.statistics()['attempted_value_selections'], 98)
        self.assertEqual(tree.statistics()['decision_node_visit_histogram']['eight_plus'], 1)

    def test_forced_nodes_do_not_inflate_decision_coverage(self):
        _, state = endgame(played=28)
        view = observe(state, state.next_player)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        self.assertEqual(len(legal), 1)
        tree = SelfSearch()
        for _ in range(4):
            card, edge = tree.select(view, legal, Random(1))
            tree.commit([edge], 1)
        stats = tree.statistics()
        self.assertEqual(stats['nodes'], 1)
        self.assertEqual(stats['decision_nodes'], 0)
        self.assertEqual(stats['attempted_forced_selections'], 4)
        self.assertEqual(stats['attempted_value_selections'], 0)

    def test_hidden_worlds_have_same_key_and_same_search_choice(self):
        _, state = endgame()
        actor = state.next_player
        others = [seat for seat in range(4) if seat != actor]
        hands = list(state.hands)
        hands[others[0]], hands[others[1]] = hands[others[1]], hands[others[0]]
        one = observe(state, actor)
        two = observe(replace(state, hands=tuple(hands)), actor)
        self.assertEqual(information_key(one), information_key(two))
        legal = legal_cards(one.hand, one.current_trick, one.trump)
        self.assertEqual(SelfSearch().select(one, legal, Random(5)),
                         SelfSearch().select(two, legal, Random(5)))

    def test_default_mixed_rollouts_never_call_fixed_policy_for_self(self):
        match, _ = endgame(played=16)
        own = match.initial.player
        future_choices = []
        def checked(view, rng, policy, legal):
            self.assertNotEqual(view.player, own)
            return choose_move(view, rng, policy)
        for name, search_type in ((SELF_SEARCH, SelfSearch), (SHARED_SELF_SEARCH, SharedSelfSearch),
                                  (BELA_CREDIT_SELF_SEARCH, BelaCreditSelfSearch)):
            with self.subTest(policy=name):
                future_choices.clear()
                original_select = search_type.select
                def selected(tree, view, legal, rng):
                    future_choices.append(len(legal))
                    return original_select(tree, view, legal, rng)
                with patch('bela.analysis.monte_carlo._choose_from_legal', side_effect=checked), \
                     patch.object(search_type, 'select', selected):
                    result = analyze_moves(match, MonteCarloConfig(samples=12, seconds=30, self_policy=name))
                self.assertEqual(result['completed_samples'], 12)
                self.assertEqual(result['strategy_model']['self_policy'], name)
                self.assertGreater(result['strategy_model']['self_search']['committed_actions'], 0)
                self.assertTrue(any(count > 1 for count in future_choices))
                self.assertEqual(result['method'], 'information_set_monte_carlo_v1')

    def test_interrupted_trial_does_not_update_future_action_values(self):
        match, _ = endgame()
        stopped = Event()
        original = SelfSearch.select
        def stop_after_select(tree, *args):
            result = original(tree, *args)
            stopped.set()
            return result
        with patch.object(SelfSearch, 'select', stop_after_select):
            result = analyze_moves(match, MonteCarloConfig(seconds=30), cancelled=stopped.is_set)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(result['completed_samples'], 0)
        self.assertEqual(result['strategy_model']['self_search']['committed_actions'], 0)


if __name__ == '__main__':
    unittest.main()
