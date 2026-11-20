"""Optimized internal rollouts must match the validated public simulator."""
from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from bela.analysis.policies import (POLICIES, _choose_from_legal, choose_move,
                                    _public_context, _completed_public_context)
from bela.domain.game import Seat
from bela.gameplay.simulation import (_prepare_turn, _play_prepared, observe,
                                      play_card, resolve_declarations, start_play)
from bela.domain.cards import Suit
from bela.rules.play import legal_cards
from bela.analysis.rollout_random import TrialRandomness
from test_monte_carlo import HANDS


class PreparedTurnTests(unittest.TestCase):
    def test_forced_move_skips_strategy_but_preserves_random_stream_and_bela(self):
        from bela.analysis.policies import announce_bela
        from bela.domain.cards import Card, Rank
        state = self.initial()
        view = observe(state, state.next_player)
        king = Card(view.trump, Rank.KING)
        queen = Card(view.trump, Rank.QUEEN)
        view = replace(view, hand=(king, queen), bela_announcements=())
        for policy in POLICIES:
            with self.subTest(policy=policy):
                rng = Random(42)
                expected_rng = Random(42)
                expected_rng.randrange(1)
                with patch('bela.analysis.policies._informed_choices',
                           side_effect=AssertionError('Forced moves need no strategy')):
                    move = _choose_from_legal(view, rng, policy, (king,))
                self.assertEqual(move.card, king)
                self.assertTrue(move.bela)
                self.assertEqual(move.bela, announce_bela(view, king))
                self.assertEqual(rng.getstate(), expected_rng.getstate())

    def initial(self):
        return resolve_declarations(start_play(HANDS, trump=Suit.HEARTS,
                                               dealer=Seat.THREE, caller=Seat.ZERO))

    def test_prepared_and_public_moves_match_for_every_profile(self):
        for policy in POLICIES:
            state = self.initial()
            for ply in range(32):
                turn = _prepare_turn(state)
                one = _choose_from_legal(turn.view, Random(ply), policy, turn.legal)
                two = choose_move(observe(state, state.next_player), Random(ply), policy)
                self.assertEqual(one, two)
                checked = play_card(state, state.next_player, two.card, announce_bela=two.bela)
                optimized = _play_prepared(state, turn, one.card, announce_bela=one.bela)
                self.assertEqual(optimized, checked)
                state = optimized

    def test_stale_or_different_state_cannot_reuse_legal_cards(self):
        state = self.initial()
        turn = _prepare_turn(state)
        with self.assertRaises(ValueError):
            _play_prepared(replace(state), turn, turn.legal[0])
        changed = play_card(state, state.next_player, turn.legal[0])
        with self.assertRaises(ValueError):
            _play_prepared(changed, turn, turn.legal[0])
        absent = next(c for hand in state.hands[1:] for c in hand)
        with self.assertRaises(ValueError):
            _play_prepared(state, turn, absent)
        with self.assertRaises(ValueError):
            _play_prepared(state, turn, turn.legal[0], announce_bela='yes')

    def test_single_legal_calculation_is_reused_without_disabling_public_validation(self):
        state = self.initial()
        with patch('bela.gameplay.simulation.legal_cards', wraps=legal_cards) as rules:
            turn = _prepare_turn(state)
            move = _choose_from_legal(turn.view, Random(1), 'tactical_v1', turn.legal)
            _play_prepared(state, turn, move.card, announce_bela=move.bela)
            self.assertEqual(rules.call_count, 1)
            play_card(state, state.next_player, move.card, announce_bela=move.bela)
            self.assertEqual(rules.call_count, 2)

    def test_internal_state_copy_preserves_public_records_and_analysis_marker(self):
        from bela.domain.melds import CardsRevealedAnnouncement
        state = self.initial()
        state = replace(state, match_score=(810, 770), analysis_only=True,
                        declaration_history=(CardsRevealedAnnouncement(Seat.ONE, tuple(state.hands[1])),))
        for ply in range(32):
            turn = _prepare_turn(state)
            move = _choose_from_legal(turn.view, Random(ply), 'tactical_v1', turn.legal)
            expected = play_card(state, turn.view.player, move.card, announce_bela=move.bela)
            state = _play_prepared(state, turn, move.card, announce_bela=move.bela)
            self.assertEqual(state, expected)
            self.assertTrue(state.analysis_only)
            self.assertEqual(state.match_score, (810, 770))

    def test_cached_public_facts_match_history_and_are_immutable(self):
        state = self.initial()
        _completed_public_context.cache_clear()
        first = _public_context(observe(state, Seat.ZERO))
        _public_context(observe(state, Seat.ONE))
        self.assertGreater(_completed_public_context.cache_info().hits, 0)
        with self.assertRaises(TypeError):
            first[1][next(iter(state.hands[0]))] = Seat.ZERO
        with self.assertRaises(AttributeError):
            first[2][0].add(Suit.HEARTS)
        for ply in range(32):
            view = observe(state, state.next_player)
            played, known, voids = _public_context(view)
            expected_played = set()
            expected_voids = [set() for _ in range(4)]
            for trick in (*state.completed_tricks, state.current_trick):
                for index, card in enumerate(trick.cards):
                    expected_played.add(card)
                    if card.suit != trick.cards[0].suit:
                        seat = trick.seat_at(index)
                        expected_voids[seat].add(trick.cards[0].suit)
                        if card.suit != state.trump:
                            expected_voids[seat].add(state.trump)
            self.assertEqual(played, expected_played)
            self.assertEqual(voids, tuple(frozenset(s) for s in expected_voids))
            move = choose_move(view, Random(ply), 'tactical_v1')
            state = play_card(state, view.player, move.card, announce_bela=move.bela)


class PairedRandomTests(unittest.TestCase):
    def test_cached_draws_exactly_match_original_generators_in_any_branch_order(self):
        for seed in (0, 19, 2**127+17):
            cache = TrialRandomness(seed)
            for ply in range(32):
                for size in (8, 1, 5, 3, 8, 2, 7, 4, 6, 3):
                    expected = Random((seed << 6) + ply).randrange(size)
                    self.assertEqual(cache.at(ply).randrange(size), expected)

    def test_multiple_draws_or_invalid_choice_counts_fail_explicitly(self):
        cache = TrialRandomness(42)
        draw = cache.at(5)
        draw.randrange(3)
        with self.assertRaises(RuntimeError):
            draw.randrange(3)
        for invalid in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                cache.at(5).randrange(invalid)


if __name__=='__main__':
    unittest.main()
