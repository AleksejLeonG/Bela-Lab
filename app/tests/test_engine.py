import random
import os
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError

from bela.advisor import analyze
from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Seat, Trick
from bela.rules.play import card_points, legal_cards, strength, trick_winner
from bela.rules.scoring import match_winner, settle_deal
from bela.rules.melds import detect_melds
from bela.simulation import observe, play_card, resolve_declarations, settle_play, start_play


def cards(*values):
    return tuple(Card.parse(value) for value in values)


def initial(seed=42):
    shuffled = list(deck())
    random.Random(seed).shuffle(shuffled)
    return resolve_declarations(start_play([shuffled[i:i + 8] for i in range(0, 32, 8)],
                                trump=Suit.HEARTS, dealer=Seat.THREE, caller=Seat.ZERO))


class CardTests(unittest.TestCase):
    def test_deck_and_ids(self):
        self.assertEqual(len(set(deck())), 32)
        self.assertEqual([card.id for card in deck()], list(range(32)))
        for card in deck():
            self.assertEqual(Card.parse(str(card)), card)

    def test_parse(self):
        self.assertEqual(Card.parse(" s_10 "), Card(Suit.SPADES, Rank.TEN))
        for value in ("H_11", "X_A", "HA", "H_A_extra", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Card.parse(value)

    def test_typed_card(self):
        with self.assertRaises(ValueError):
            Card("H", "J")

    def test_points_total_for_each_trump(self):
        for trump in Suit:
            self.assertEqual(sum(card_points(card, trump) for card in deck()), 152)

    def test_orders_and_values(self):
        trump = cards("H_7", "H_8", "H_Q", "H_K", "H_10", "H_A", "H_9", "H_J")
        plain = cards("S_7", "S_8", "S_9", "S_J", "S_Q", "S_K", "S_10", "S_A")
        self.assertEqual([strength(c, Suit.HEARTS) for c in trump], list(range(8)))
        self.assertEqual([strength(c, Suit.HEARTS) for c in plain], list(range(8)))
        self.assertEqual(card_points(Card.parse("H_J"), Suit.HEARTS), 20)
        self.assertEqual(card_points(Card.parse("S_J"), Suit.HEARTS), 2)

    def test_seat_direction_and_partners(self):
        self.assertEqual(Seat.THREE.next, Seat.ZERO)
        for seat in Seat:
            self.assertEqual(seat.partner.partner, seat)
            self.assertEqual(seat.team, seat.partner.team)


class PlayRuleTests(unittest.TestCase):
    def legal(self, hand, table):
        return set(legal_cards(cards(*hand), Trick(Seat.ZERO, cards(*table)), Suit.HEARTS))

    def test_opening_any_card(self):
        hand = ("H_J", "S_7", "C_A")
        self.assertEqual(self.legal(hand, ()), set(cards(*hand)))

    def test_follow_and_head(self):
        self.assertEqual(self.legal(("S_7", "S_K", "S_A", "H_J"), ("S_8",)),
                         set(cards("S_K", "S_A")))

    def test_follow_lower_when_cannot_head(self):
        self.assertEqual(self.legal(("S_7", "S_K", "H_J"), ("S_A",)),
                         set(cards("S_7", "S_K")))

    def test_head_current_highest_not_first_card(self):
        self.assertEqual(self.legal(("S_J", "S_A"), ("S_8", "S_K")),
                         set(cards("S_A")))

    def test_follow_after_cut_without_heading(self):
        self.assertEqual(self.legal(("S_7", "S_A", "H_J"), ("S_8", "H_7")),
                         set(cards("S_7", "S_A")))

    def test_must_trump_when_void(self):
        self.assertEqual(self.legal(("H_7", "C_A"), ("S_A",)), set(cards("H_7")))

    def test_overtrump(self):
        self.assertEqual(self.legal(("H_7", "H_9", "H_J", "C_A"), ("S_A", "H_A")),
                         set(cards("H_9", "H_J")))

    def test_undertrump_if_cannot_overtrump(self):
        self.assertEqual(self.legal(("H_7", "H_A", "C_A"), ("S_A", "H_9")),
                         set(cards("H_7", "H_A")))

    def test_trump_lead_requires_heading(self):
        self.assertEqual(self.legal(("H_7", "H_9", "C_A"), ("H_A",)),
                         set(cards("H_9")))

    def test_discard_when_void_in_both(self):
        self.assertEqual(self.legal(("C_7", "D_A"), ("S_A", "H_9")),
                         set(cards("C_7", "D_A")))

    def test_partner_does_not_waive_heading(self):
        # Player 2 follows, partner 0 currently winning.
        self.assertEqual(self.legal(("S_7", "S_A"), ("S_K", "S_8")),
                         set(cards("S_A")))

    def test_partner_does_not_waive_trumping(self):
        self.assertEqual(self.legal(("H_7", "C_A"), ("S_A", "S_8")),
                         set(cards("H_7")))

    def test_partner_does_not_waive_overtrumping(self):
        # Player 3 must overtrump partner 1.
        self.assertEqual(self.legal(("H_7", "H_J"), ("S_A", "H_9", "S_7")),
                         set(cards("H_J")))

    def test_off_suit_ace_cannot_win(self):
        trick = Trick(Seat.THREE, cards("S_7", "C_A", "D_A", "S_8"))
        self.assertEqual(trick_winner(trick, Suit.HEARTS), Seat.TWO)

    def test_trump_beats_plain_ace(self):
        trick = Trick(Seat.ONE, cards("S_A", "H_7", "S_10", "H_9"))
        self.assertEqual(trick_winner(trick, Suit.HEARTS), Seat.ZERO)

    def test_invalid_trick_and_hand(self):
        with self.assertRaises(ValueError):
            Trick(Seat.ZERO, cards("S_A", "S_A"))
        with self.assertRaises(ValueError):
            legal_cards(cards("S_A", "S_A"), Trick(Seat.ZERO), Suit.HEARTS)
        with self.assertRaises(ValueError):
            legal_cards(cards("S_A"), Trick(Seat.ZERO, cards("S_A")), Suit.HEARTS)
        with self.assertRaises(ValueError):
            legal_cards(cards("H_A"), Trick(Seat.ZERO, cards("S_A", "S_7", "S_8", "S_9")), Suit.HEARTS)
        with self.assertRaises(ValueError):
            trick_winner(Trick(Seat.ZERO), Suit.HEARTS)


class ScoringTests(unittest.TestCase):
    def settle(self, points, *, tricks=(4, 4), last=0, caller=0, melds=(0, 0), bela=(0, 0)):
        return settle_deal(card_points=points, trick_counts=tricks,
                           last_trick_team=last, caller_team=caller,
                           awarded_melds=melds, announced_bela=bela)

    def test_tie_falls(self):
        result = self.settle((71, 81))
        self.assertEqual(result.earned, (81, 81))
        self.assertEqual(result.recorded, (0, 162))
        self.assertFalse(result.caller_passed)

    def test_82_passes(self):
        self.assertEqual(self.settle((72, 80)).recorded, (82, 80))

    def test_caller_can_be_other_team(self):
        self.assertEqual(self.settle((80, 72), last=1, caller=1).recorded, (80, 82))

    def test_melds_change_threshold(self):
        result = self.settle((46, 106), melds=(50, 0))
        self.assertEqual(result.earned, (106, 106))
        self.assertEqual(result.recorded, (0, 212))
        self.assertEqual(self.settle((47, 105), melds=(50, 0)).recorded, (107, 105))

    def test_sweep(self):
        self.assertEqual(self.settle((152, 0), tricks=(8, 0)).recorded, (252, 0))

    def test_defenders_sweep(self):
        self.assertEqual(self.settle((0, 152), tricks=(0, 8), last=1).recorded, (0, 252))

    def test_no_trick_no_melds_or_bela(self):
        result = self.settle((0, 152), tricks=(0, 8), last=1,
                             melds=(50, 0), bela=(20, 0))
        self.assertEqual(result.total, 252)
        self.assertEqual(result.earned, (0, 252))

    def test_bela_independent_of_ordinary_melds(self):
        result = self.settle((80, 72), melds=(50, 0), bela=(0, 20))
        self.assertEqual(result.earned, (140, 92))
        self.assertEqual(result.total, 232)

    def test_invalid_totals(self):
        for points, tricks, last in [((80, 80), (4, 4), 0),
                                      ((80, 72), (3, 4), 0),
                                      ((0, 152), (0, 8), 0),
                                      ((1, 151), (0, 8), 1)]:
            with self.subTest(points=points, tricks=tricks), self.assertRaises(ValueError):
                self.settle(points, tricks=tricks, last=last)
        for kwargs in ({"melds": (20, 50)}, {"bela": (20, 20)}, {"bela": (10, 0)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.settle((80, 72), **kwargs)

    def test_match_end(self):
        for score, expected in [((1000, 900), None), ((1001, 900), 0),
                                ((1070, 1042), 0), ((1042, 1070), 1),
                                ((1100, 1100), None), ((0, 0), None)]:
            with self.subTest(score=score):
                self.assertEqual(match_winner(score), expected)


class SimulationTests(unittest.TestCase):
    def test_invalid_start(self):
        hand = deck()[:8]
        with self.assertRaises(ValueError):
            start_play([hand] * 4, trump=Suit.HEARTS, dealer=Seat.ZERO, caller=Seat.ONE)
        with self.assertRaises(ValueError):
            start_play([hand], trump=Suit.HEARTS, dealer=Seat.ZERO, caller=Seat.ONE)

    def test_no_mutation_on_move(self):
        before = initial()
        card = analyze(observe(before, Seat.ZERO)).legal_actions[0]
        after = play_card(before, Seat.ZERO, card)
        self.assertEqual(len(before.hands[0]), 8)
        self.assertEqual(len(after.hands[0]), 7)
        self.assertEqual(after.next_player, Seat.ONE)
        with self.assertRaises(FrozenInstanceError):
            before.trump = Suit.CLUBS

    def test_out_of_turn_and_missing_card(self):
        state = initial()
        with self.assertRaises(ValueError):
            play_card(state, Seat.ONE, next(iter(state.hands[1])))
        with self.assertRaises(ValueError):
            play_card(state, Seat.ZERO, next(iter(state.hands[1])))
        with self.assertRaises(ValueError):
            settle_play(state)
        with self.assertRaises(ValueError):
            analyze(observe(state, Seat.ONE))

    def test_observation_does_not_include_hidden_hands(self):
        # Both worlds have identical public declarations: no ordinary melds.
        state = next(initial(seed) for seed in range(1000)
                     if not any(detect_melds(hand) for hand in initial(seed).hands))
        view = observe(state, Seat.ZERO)
        self.assertFalse(hasattr(view, "hands"))
        swapped = (state.hands[0], state.hands[3], state.hands[2], state.hands[1])
        alternative = resolve_declarations(start_play(
            swapped, trump=state.trump, dealer=state.dealer,
            caller=state.caller, match_score=state.match_score))
        self.assertEqual(observe(state, Seat.ZERO), observe(alternative, Seat.ZERO))
        self.assertEqual(analyze(view), analyze(observe(alternative, Seat.ZERO)))

    def test_complete_deals_conserve_cards_and_follow_winner(self):
        for seed in range(100):
            with self.subTest(seed=seed):
                state = initial(seed)
                rng = random.Random(seed)
                played = set()
                for turn in range(32):
                    view = observe(state, state.next_player)
                    action = rng.choice(analyze(view).legal_actions)
                    self.assertNotIn(action, played)
                    played.add(action)
                    state = play_card(state, state.next_player, action)
                    self.assertEqual(sum(map(len, state.hands)), 31 - turn)
                    if (turn + 1) % 4 == 0 and turn != 31:
                        self.assertEqual(state.next_player,
                                         trick_winner(state.completed_tricks[-1], state.trump))
                self.assertTrue(state.finished)
                self.assertIsNone(state.next_player)
                self.assertEqual(played, set(deck()))
                result = settle_play(state)
                self.assertGreaterEqual(result.total, 162)
                self.assertEqual(result.total % 10, 2)
                self.assertEqual(sum(result.recorded), result.total)
                with self.assertRaises(ValueError):
                    play_card(state, Seat.ZERO, deck()[0])


class CommandLineTests(unittest.TestCase):
    def test_demo_defaults_to_english_with_legacy_windows_encoding(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        result = subprocess.run([sys.executable, "-m", "bela", "--seed", "42"],
                                env=env, capture_output=True, check=True)
        output = result.stdout.decode("utf-8")
        self.assertIn("Recorded:", output)
        self.assertIn("statistics are not implemented yet", output)


if __name__ == "__main__":
    unittest.main()
