"""Future-self preference boundaries: preserve trumps only in a certain loss."""
from dataclasses import replace
from pathlib import Path
from random import Random
import unittest

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.learned_policy import FrozenSelfPolicy
from bela.analysis.self_search import (SelfSearch, SharedSelfSearch, BelaCreditSelfSearch,
    information_key, losing_trump_discard)
from bela.domain.cards import Card
from bela.domain.game import Seat, Trick
from bela.gameplay.simulation import observe, play_card
from bela.rules.play import legal_cards
from bela.storage.user_storage import loads_user_match
from test_monte_carlo import cards, endgame
from test_strategy_lineups import view


class LosingTrumpTests(unittest.TestCase):
    def observation(self, hand='H_8 H_9', trick='H_J H_7 H_Q', leader=Seat.ZERO):
        return view(hand, Trick(leader, cards(trick)))

    def test_preserves_nine_under_opponents_jack_and_commits_only_completed_rewards(self):
        v = self.observation()
        legal = legal_cards(v.hand, v.current_trick, v.trump)
        for cls in (SelfSearch, SharedSelfSearch, BelaCreditSelfSearch):
            with self.subTest(tree=cls.__name__):
                tree = cls()
                for seed in range(10):
                    card, edge = tree.select(v, legal, Random(seed))
                    self.assertEqual(str(card), 'H_8')
                node = tree.nodes[information_key(v)]
                self.assertEqual(set(node), set(legal))
                self.assertTrue(all(n == 0 for n,_ in node.values()))
                tree.commit([edge], 1)
                self.assertEqual(node[card], [1, 1.0])
                self.assertEqual(tree.statistics()['attempted_losing_trump_selections'], 10)
                self.assertEqual(tree.statistics()['attempted_forced_selections'], 0)

    def test_fourth_seat_saves_ace_when_both_trumps_lose_to_nine(self):
        v = self.observation('H_K H_A', 'S_A S_7 H_9')
        legal = legal_cards(v.hand, v.current_trick, v.trump)
        self.assertEqual(str(losing_trump_discard(v, legal)), 'H_K')

    def test_does_not_override_when_partner_is_winning_or_can_rescue(self):
        for hand, trick, leader in (
            ('H_8 H_9', 'H_J H_7', Seat.ZERO),  # Partner has the jack.
            ('H_8 H_A', 'S_7 H_9', Seat.ONE),  # Partner plays fourth, may hold jack.
        ):
            v = self.observation(hand, trick, leader)
            legal = legal_cards(v.hand, v.current_trick, v.trump)
            self.assertGreater(len(legal), 1)
            self.assertIsNone(losing_trump_discard(v, legal))

    def test_does_not_override_winnable_trick_plain_discard_lead_or_forced_move(self):
        for hand, trick in (
            ('H_9 H_J', 'H_8 H_Q H_K'),
            ('D_7 D_A', 'S_J S_8 S_Q'),
            ('H_8 H_9', ''),
            ('H_8', 'H_J H_7 H_Q'),
        ):
            v = self.observation(hand, trick)
            legal = legal_cards(v.hand, v.current_trick, v.trump)
            self.assertIsNone(losing_trump_discard(v, legal))

    def test_earlier_seat_requires_unbeatable_enemy_jack(self):
        v = self.observation('H_8 H_9', 'H_J')
        legal = legal_cards(v.hand, v.current_trick, v.trump)
        self.assertEqual(str(losing_trump_discard(v, legal)), 'H_8')
        # Only the public view enters the preference; scores and caller do not.
        changed = replace(v, match_score=(950, 990), caller=Seat.TWO)
        self.assertEqual(losing_trump_discard(v, legal), losing_trump_discard(changed, legal))

    def test_hidden_hands_cannot_change_preference(self):
        _, state = endgame(played=24)
        state = play_card(state, state.next_player, Card.parse('H_J'))
        actor = state.next_player
        others = [s for s in range(4) if s != actor]
        hands = list(state.hands)
        hands[others[0]], hands[others[1]] = hands[others[1]], hands[others[0]]
        one = observe(state, actor)
        two = observe(replace(state, hands=tuple(hands)), actor)
        legal = legal_cards(one.hand, one.current_trick, one.trump)
        self.assertEqual(str(losing_trump_discard(one, legal)), 'H_8')
        self.assertEqual(losing_trump_discard(one, legal), losing_trump_discard(two, legal))

    def test_frozen_evaluation_uses_same_preference_without_changing_values(self):
        v = self.observation()
        legal = legal_cards(v.hand, v.current_trick, v.trump)
        key = information_key(v)
        source = {key: {c: [2, 2.0 if str(c)=='H_9' else 0.0] for c in legal}}
        for mode in ('uniform_legal_v1', 'competent_mix_v1'):
            for nodes in ({}, source):
                policy = FrozenSelfPolicy(nodes, fallback_mode=mode)
                self.assertEqual(str(policy.select(v, legal, Random(3))), 'H_8')
                self.assertEqual(policy.statistics()['attempted_losing_trump_selections'], 1)
                self.assertEqual(policy.statistics()['attempted_value_selections'], 0)
                if nodes:
                    self.assertEqual({c: tuple(r) for c,r in source[key].items()}, dict(policy.nodes[key]))

    def test_root_candidates_and_opponent_profile_weights_are_unchanged(self):
        match = loads_user_match((Path(__file__).parent/'fixtures'/'known_endgame_planning.json').read_text())
        for seed in (7, 42, 119):
            result = analyze_moves(match, MonteCarloConfig(samples=128, seconds=30, seed=seed))
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['moves'][0]['card'], 'S_8')
            self.assertEqual(set(r['card'] for r in result['moves']), set(map(str, match.state.legal_actions)))
            self.assertEqual(result['strategy_model']['other_player_weights'], {
                p: .2 for p in ('random_v1','simple_v1','cautious_v1','counting_v1','tactical_v1')})
            self.assertGreater(result['strategy_model']['self_search']['attempted_losing_trump_selections'], 0)


if __name__ == '__main__':
    unittest.main()
