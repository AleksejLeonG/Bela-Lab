"""Calling legality, six-card information boundaries and baseline decisions."""

from dataclasses import replace
from itertools import permutations
from random import Random
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from bela.analysis.trump import BASELINE_POLICY, POLICY, advise_trump
from bela.domain.cards import Card, Suit, deck
from bela.domain.players import Seat
from bela.gameplay.calling import CallingObservation, CallingState
from bela.interfaces.trump_cli import main


def cards(text):
    return tuple(Card.parse(c) for c in text.split())


def observation(hand, *, forced=False):
    state = CallingState(Seat.ZERO if forced else Seat.THREE)
    if forced:
        for seat in (Seat.ONE, Seat.TWO, Seat.THREE):
            state = state.pass_turn(seat)
    return CallingObservation(Seat.ZERO, cards(hand), state)


class CallingTests(unittest.TestCase):
    def test_single_round_order_for_every_dealer_and_mandatory_call(self):
        for dealer in Seat:
            state = CallingState(dealer)
            for step in range(1, 4):
                player = Seat((int(dealer) + step) % 4)
                self.assertEqual(state.next_player, player)
                self.assertFalse(state.forced)
                with self.assertRaises(ValueError):
                    state.pass_turn(player.next)
                state = state.pass_turn(player)
            self.assertEqual(state.next_player, dealer)
            self.assertTrue(state.forced)
            with self.assertRaises(ValueError):
                state.pass_turn(dealer)
            complete = state.call_trump(dealer, Suit.CLUBS)
            self.assertEqual((complete.caller, complete.trump), (dealer, Suit.CLUBS))
            self.assertIsNone(complete.next_player)
            self.assertFalse(complete.forced)
            with self.assertRaises(ValueError):
                complete.call_trump(dealer, Suit.HEARTS)

    def test_any_seat_can_end_calling_early(self):
        for stop in range(4):
            state = CallingState(Seat.THREE)
            for _ in range(stop):
                state = state.pass_turn(state.next_player)
            result = state.call_trump(Seat(stop), Suit.DIAMONDS)
            self.assertEqual(result.caller, Seat(stop))
            self.assertEqual(len(result.passes), stop)

    def test_invalid_calling_histories_and_types(self):
        for kwargs in ({"dealer": 0}, {"dealer": Seat.ZERO, "passes": (Seat.TWO,)},
                       {"dealer": Seat.ZERO, "passes": (Seat.ONE, Seat.TWO, Seat.THREE, Seat.ZERO)},
                       {"dealer": Seat.ZERO, "caller": Seat.ONE},
                       {"dealer": Seat.ZERO, "caller": Seat.TWO, "trump": Suit.CLUBS}):
            with self.assertRaises(ValueError):
                CallingState(**kwargs)
        with self.assertRaises(ValueError):
            CallingState(Seat.THREE).call_trump(Seat.ZERO, "C")

    def test_visible_online_hand_selects_clubs_using_control_and_side_aces(self):
        view = observation("C_9 C_J C_K H_A S_Q D_A", forced=True)
        advice = advise_trump(view)
        self.assertEqual(advice.action, Suit.CLUBS)
        self.assertEqual(advice.rankings[0].trump_count, 3)
        self.assertGreater(advice.rankings[0].score, advice.rankings[1].score)
        parts = dict(advice.rankings[0].components)
        self.assertGreater(parts["Trump jack"], 0)
        self.assertGreater(parts["Trump nine"], 0)
        self.assertGreater(parts["Side aces"], 0)

    def test_weak_hand_passes_but_same_forced_dealer_calls(self):
        hand = "C_7 C_8 H_7 H_8 S_Q D_K"
        optional = advise_trump(observation(hand))
        forced = advise_trump(observation(hand, forced=True))
        self.assertIsNone(optional.action)
        self.assertIsInstance(forced.action, Suit)
        self.assertEqual([r.suit for r in optional.rankings], [r.suit for r in forced.rankings])
        self.assertTrue(forced.forced)
        self.assertIn(forced.action, {c.suit for c in cards(hand)})

    def test_trump_control_can_outweigh_length(self):
        advice = advise_trump(observation("H_J H_9 C_7 C_8 C_Q D_7", forced=True))
        self.assertEqual(advice.action, Suit.HEARTS)

    def test_strong_six_card_suit_calls_without_talon(self):
        advice = advise_trump(observation("H_9 H_10 H_J H_Q H_K H_A"))
        self.assertEqual(advice.action, Suit.HEARTS)
        self.assertTrue(advice.rankings[0].qualifies)
        self.assertGreater(dict(advice.rankings[0].components)["Visible bela pair"], 0)

    def test_six_card_boundary_rejects_future_talon_and_other_players_turns(self):
        good = observation("C_9 C_J C_K H_A S_Q D_A")
        for hand in (good.hand[:5], good.hand + cards("H_7 S_7"), good.hand[:5] + good.hand[:1], list(good.hand)):
            with self.assertRaises(ValueError):
                replace(good, hand=hand)
        with self.assertRaises(ValueError):
            replace(good, player=Seat.ONE)
        with self.assertRaises(ValueError):
            advise_trump(object())

    def test_card_input_order_cannot_change_rankings_or_choice(self):
        view = observation("C_9 C_J C_K H_A S_Q D_A")
        expected = advise_trump(view)
        for hand in permutations(view.hand):
            self.assertEqual(advise_trump(replace(view, hand=hand)), expected)

    def test_random_hands_always_produce_four_explained_suits_and_legal_actions(self):
        rng = Random(182)
        for _ in range(300):
            hand = tuple(rng.sample(deck(), 6))
            for forced in (False, True):
                state = CallingState(Seat.ZERO if forced else Seat.THREE)
                while state.next_player != Seat.ZERO:
                    state = state.pass_turn(state.next_player)
                view = CallingObservation(Seat.ZERO, hand, state)
                advice = advise_trump(view)
                self.assertEqual({r.suit for r in advice.rankings}, set(Suit))
                self.assertEqual(len(advice.rankings), 4)
                for row in advice.rankings:
                    self.assertEqual(row.score, sum(v for _, v in row.components))
                if forced:
                    self.assertIsInstance(advice.action, Suit)
                    self.assertIn(advice.action, {c.suit for c in hand})
                elif advice.action is not None:
                    self.assertTrue(next(r for r in advice.rankings if r.suit == advice.action).qualifies)

    def test_cli_json_is_explicit_about_passes_and_has_no_fake_probabilities(self):
        output = StringIO()
        with redirect_stdout(output):
            main(["C_9", "C_J", "C_K", "H_A", "S_Q", "D_A",
                  "--dealer", "0", "--player", "0", "--json"])
        result = json.loads(output.getvalue())
        self.assertEqual(result["trump"], "C")
        self.assertTrue(result["forced"])
        self.assertEqual(result["assumed_prior_passes"], [1, 2, 3])
        self.assertEqual(result["score_kind"], "heuristic_not_probability")
        self.assertNotIn("success_probability", result)

    def test_same_hand_calls_first_and_third_but_passes_second(self):
        hand = cards("C_J C_10 H_A S_A D_Q D_K")
        decisions = []
        for position, dealer in enumerate((Seat.THREE, Seat.TWO, Seat.ONE, Seat.ZERO), 1):
            state = CallingState(dealer)
            while state.next_player != Seat.ZERO:
                state = state.pass_turn(state.next_player)
            advice = advise_trump(CallingObservation(Seat.ZERO, hand, state))
            decisions.append(advice)
            self.assertEqual(advice.position, position)
        self.assertEqual([a.action for a in decisions[:3]], [Suit.CLUBS, None, Suit.CLUBS])
        self.assertEqual([a.threshold for a in decisions], [45, 49, 45, None])
        self.assertEqual(decisions[2].first_leader, "partner")
        self.assertGreater(decisions[2].rankings[0].score, decisions[0].rankings[0].score)

    def test_third_position_favors_jack_without_making_it_a_requirement(self):
        state = CallingState(Seat.ONE).pass_turn(Seat.TWO).pass_turn(Seat.THREE)
        strong_without_jack = CallingObservation(Seat.ZERO, cards("C_9 C_10 C_Q C_K H_A S_7"), state)
        advice = advise_trump(strong_without_jack)
        self.assertEqual(advice.action, Suit.CLUBS)
        self.assertLess(dict(advice.rankings[0].components)["Third-position call without the jack"], 0)

    def test_forced_dealer_avoids_overvaluing_a_lone_jack(self):
        view = observation("C_J H_9 H_A S_8 S_10 S_Q", forced=True)
        self.assertEqual(advise_trump(view, BASELINE_POLICY).action, Suit.CLUBS)
        self.assertEqual(advise_trump(view).action, Suit.HEARTS)

    def test_position_is_relative_to_dealer_not_absolute_seat(self):
        hand = cards("C_J C_10 H_A S_A D_Q D_K")
        for position in range(1, 5):
            decisions = []
            for dealer in Seat:
                state = CallingState(dealer)
                for _ in range(position-1):
                    state = state.pass_turn(state.next_player)
                decisions.append(advise_trump(CallingObservation(state.next_player, hand, state)))
            self.assertTrue(all(a == decisions[0] for a in decisions))

    def test_original_baseline_remains_position_independent(self):
        first = observation("C_J H_9 H_A S_8 S_10 S_Q")
        forced = observation("C_J H_9 H_A S_8 S_10 S_Q", forced=True)
        self.assertEqual(advise_trump(first, BASELINE_POLICY).rankings,
                         advise_trump(forced, BASELINE_POLICY).rankings)
        with self.assertRaises(ValueError):
            advise_trump(first, "unknown")


if __name__ == "__main__":
    unittest.main()
