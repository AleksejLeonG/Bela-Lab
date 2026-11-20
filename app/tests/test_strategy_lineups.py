"""Latent profile distributions, match lifetime and public-information policies."""

from collections import Counter
from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from bela.analysis.lineups import StrategyLineup, StrategyMatch
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.policies import MIXED_POLICY, POLICIES, choose_move
from bela.domain.cards import Card, Suit
from bela.domain.game import Phase, PlayerObservation, Seat, Trick
from bela.domain.melds import CardsRevealedAnnouncement
from bela.gameplay.simulation import observe, resolve_declarations, start_play
from bela.storage.user_storage import dumps_user_match
from test_monte_carlo import HANDS, cards, endgame


def view(hand, trick, *, history=(), completed=()):
    return PlayerObservation(trick.next_player, frozenset(cards(hand)), Suit.HEARTS,
                             Seat.THREE, Seat.ZERO, (0, 0), trick, completed,
                             (7, 7, 7, 7), trick.next_player, Phase.PLAYING,
                             None, (), (), None, history)


class StrategyLineupTests(unittest.TestCase):
    def test_five_independent_profiles_with_duplicates_and_fixed_self(self):
        self.assertEqual(len(POLICIES), 5)
        for player in Seat:
            counts = {seat: Counter() for seat in Seat if seat != player}
            duplicates = False
            for seed in range(1500):
                lineup = StrategyLineup.assign(player, seed)
                self.assertEqual(lineup.for_player(player), "tactical_v1")
                others = [lineup.for_player(seat) for seat in counts]
                duplicates |= len(set(others)) < 3
                for seat in counts:
                    counts[seat][lineup.for_player(seat)] += 1
            self.assertTrue(duplicates)
            for distribution in counts.values():
                self.assertEqual(set(distribution), set(POLICIES))
                self.assertTrue(all(abs(count - 300) < 80 for count in distribution.values()))

    def test_virtual_match_identity_is_independent_of_deal_and_rejection_counts(self):
        first = StrategyLineup.for_trial("match-a", 42, 12, Seat.TWO)
        self.assertEqual(first, StrategyLineup.for_trial("match-a", 42, 12, Seat.TWO))
        # No deal/revision/card/rejection inputs enter this identity.
        self.assertGreater(len({StrategyLineup.for_trial("match-a", 42, i, Seat.TWO).policies
                                for i in range(30)}), 10)
        self.assertNotEqual(first.seed, StrategyLineup.for_trial("match-b", 42, 12, Seat.TWO).seed)
        self.assertNotEqual(first.seed, StrategyLineup.for_trial("match-a", 43, 12, Seat.TWO).seed)

    def test_lineup_stays_fixed_until_a_whole_match_ends(self):
        state = resolve_declarations(start_play(HANDS, trump=Suit.HEARTS,
                                               dealer=Seat.THREE, caller=Seat.ONE))
        game = StrategyMatch.start(state, player=Seat.ZERO, seed=145)
        initial = game.lineup
        rng = Random(17)
        deals = 0
        while game.winner is None:
            while not game.current.finished:
                game = game.play_next(rng)
                self.assertIs(game.lineup, initial)
            deals += 1
            self.assertLess(deals, 30)
            if game.winner is not None:
                break
            next_score = game.score
            previous_dealer = game.current.dealer
            game = game.next_deal(HANDS, trump=Suit.HEARTS, caller=Seat.ONE)
            self.assertIs(game.lineup, initial)
            self.assertEqual(game.current.match_score, next_score)
            self.assertEqual(game.current.dealer, previous_dealer.next)
            game = game.with_current(resolve_declarations(game.current))
        self.assertGreater(deals, 1)
        self.assertGreater(max(game.score), 1000)
        with self.assertRaises(ValueError):
            game.next_deal(HANDS, trump=Suit.HEARTS, caller=Seat.ONE)

    def test_mixed_trials_share_lineups_between_all_candidate_cards(self):
        match, _ = endgame()
        before = dumps_user_match(match)
        calls = []
        original = choose_move
        def record(observation, rng, policy, legal):
            self.assertIsInstance(observation, PlayerObservation)
            self.assertFalse(hasattr(observation, "lineup"))
            self.assertFalse(hasattr(observation, "policies"))
            calls.append((observation.player, policy))
            return original(observation, rng, policy)
        with patch("bela.analysis.monte_carlo._choose_from_legal", side_effect=record):
            result = analyze_moves(match, MonteCarloConfig(samples=8, seconds=30, seed=9, self_policy="tactical_v1"))
        self.assertEqual(result["config"]["policy"], MIXED_POLICY)
        self.assertEqual(result["completed_samples"], 8)
        self.assertEqual(len(calls), 8 * 2 * 7)
        for trial in range(8):
            lineup = StrategyLineup.for_trial(match.id, 9, trial, match.initial.player)
            for seat, policy in calls[trial * 14:(trial + 1) * 14]:
                self.assertEqual(policy, lineup.for_player(seat))
        self.assertEqual(before, dumps_user_match(match))
        self.assertFalse(result["strategy_model"]["real_player_profiles_known"])
        self.assertNotIn("lineup", result)
        self.assertNotIn("seat_strategies", result["strategy_model"])
        self.assertEqual(result["strategy_model"]["other_player_weights"], {p: .2 for p in POLICIES})

    def test_every_profile_is_legal_and_uses_identical_observations(self):
        for policy in POLICIES:
            state = resolve_declarations(start_play(HANDS, trump=Suit.HEARTS,
                                                   dealer=Seat.THREE, caller=Seat.ONE))
            for _ in range(32):
                player = state.next_player
                observed = observe(state, player)
                hidden = [s for s in Seat if s != player]
                swapped = list(state.hands)
                swapped[hidden[0]], swapped[hidden[1]] = swapped[hidden[1]], swapped[hidden[0]]
                alternative = replace(state, hands=tuple(swapped))
                self.assertEqual(choose_move(observed, Random(18), policy),
                                 choose_move(observe(alternative, player), Random(18), policy))
                from bela.gameplay.simulation import play_card
                move = choose_move(observed, Random(19), policy)
                state = play_card(state, player, move.card, announce_bela=move.bela)

    def test_informed_profiles_do_not_feed_an_unsecured_partner(self):
        current = Trick(Seat.ZERO, cards("S_A S_7"))
        observed = view("S_10 S_8", current)
        self.assertEqual(choose_move(observed, Random(1), "simple_v1").card, Card.parse("S_10"))
        for policy in ("cautious_v1", "counting_v1", "tactical_v1"):
            self.assertEqual(choose_move(observed, Random(1), policy).card, Card.parse("S_8"))
        # Revealing a held spade proves the last opponent must follow suit.
        shown = replace(observed, declaration_history=(CardsRevealedAnnouncement(Seat.THREE, cards("S_K")),))
        for policy in ("counting_v1", "tactical_v1"):
            self.assertEqual(choose_move(shown, Random(1), policy).card, Card.parse("S_10"))

    def test_fourth_player_donates_points_and_counting_recognizes_promoted_ten(self):
        observed = view("S_10 S_8", Trick(Seat.ZERO, cards("S_7 S_A S_9")))
        for policy in ("cautious_v1", "counting_v1", "tactical_v1"):
            self.assertEqual(choose_move(observed, Random(1), policy).card, Card.parse("S_10"))
        prior = Trick(Seat.ZERO, cards("S_A S_7 S_8 S_9"))
        observed = view("S_10 D_7", Trick(Seat.ZERO), completed=(prior,))
        self.assertEqual(choose_move(observed, Random(1), "cautious_v1").card, Card.parse("D_7"))
        self.assertEqual(choose_move(observed, Random(1), "counting_v1").card, Card.parse("S_10"))

    def test_invalid_lineup_settings_are_rejected(self):
        for args in ((0, 1), (Seat.ZERO, -1), (Seat.ZERO, True)):
            with self.assertRaises(ValueError):
                StrategyLineup.assign(*args)
        with self.assertRaises(ValueError):
            StrategyLineup(Seat.ZERO, 1, ("oracle",) * 4)
        with self.assertRaises(ValueError):
            StrategyLineup.for_trial("m", 42, -1, Seat.ZERO)


if __name__ == "__main__":
    unittest.main()
