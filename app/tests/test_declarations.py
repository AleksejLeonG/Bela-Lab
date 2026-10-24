import unittest

from bela.analysis.advisor import analyze
from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, Seat
from bela.domain.melds import BelotResult, Meld, MeldKind, SequenceHighAnnouncement
from bela.rules.melds import compare_melds, detect_melds, has_belot, resolve_meld_contest
from bela.gameplay.simulation import (announce_meld_value, announce_sequence_high, declare_belot,
                             observe, play_card, resolve_declarations, settle_play, start_play)


def cards(text):
    return tuple(Card.parse(value) for value in text.split())


def sequence(suit, start, end):
    ranks = tuple(Rank)
    return Meld(MeldKind.SEQUENCE, tuple(Card(suit, rank)
                for rank in ranks[ranks.index(start):ranks.index(end) + 1]))


def quad(rank):
    return Meld(MeldKind.FOUR_OF_A_KIND, tuple(Card(suit, rank) for suit in Suit))


TIED_HANDS = tuple(map(cards, (
    "H_7 H_8 H_9 C_8 H_Q C_10 D_Q C_A",
    "S_7 S_8 S_9 D_7 H_J D_9 C_9 C_7",
    "H_A D_J C_J C_K S_J S_Q H_10 H_K",
    "S_K D_A S_10 C_Q D_8 S_A D_10 D_K",
)))

# Team 0 has four twenties (80 total), but team 1 has the strongest meld (50).
STRONGEST_HANDS = tuple(map(cards, (
    "H_7 H_8 H_9 S_7 S_8 S_9 D_7 C_7",
    "H_10 H_J H_Q H_K S_Q S_K D_Q C_K",
    "D_8 D_9 D_10 C_8 C_9 C_10 H_A S_A",
    "S_10 S_J D_J D_K D_A C_J C_Q C_A",
)))

SWEEP_HANDS = tuple(map(cards, (
    "H_J H_9 H_A H_10 S_A S_10 D_A D_10",
    "H_Q H_K H_7 H_8 S_7 S_8 D_7 D_8",
    "C_A C_10 C_K C_Q S_K S_Q D_K D_Q",
    "S_9 S_J D_9 D_J C_7 C_8 C_9 C_J",
)))


def raw_state(hands=TIED_HANDS, dealer=Seat.THREE, score=(0, 0)):
    return start_play(hands, trump=Suit.HEARTS, dealer=dealer,
                      caller=Seat.ZERO, match_score=score)


def state_with_hand(hand):
    rest = [card for card in deck() if card not in hand]
    return raw_state((hand, tuple(rest[:8]), tuple(rest[8:16]), tuple(rest[16:])))


def finish(state, *, call_bela=False):
    """Deterministic legal continuation; bela is called only on a valid first card."""
    while not state.finished:
        player = state.next_player
        action = analyze(observe(state, player)).legal_actions[0]
        pair = {Card(state.trump, Rank.KING), Card(state.trump, Rank.QUEEN)}
        call = call_bela and action in pair and pair.issubset(state.hands[player])
        state = play_card(state, player, action, announce_bela=call)
    return state


class MeldDetectionTests(unittest.TestCase):
    def test_maximal_run_once_for_each_length(self):
        for length, expected in ((3, 20), (4, 50), (5, 100), (6, 100), (7, 100)):
            with self.subTest(length=length):
                hand = tuple(Card(Suit.HEARTS, rank) for rank in tuple(Rank)[:length])
                melds = detect_melds(hand)
                self.assertEqual(len(melds), 1)
                self.assertEqual(melds[0].points, expected)
                self.assertEqual(set(melds[0].cards), set(hand))

    def test_two_separated_runs(self):
        melds = detect_melds(cards("S_7 S_8 S_9 S_J S_Q S_K"))
        self.assertEqual(len(melds), 2)
        self.assertEqual(sum(m.points for m in melds), 40)

    def test_each_scoring_quad(self):
        for rank, expected in ((Rank.JACK, 200), (Rank.NINE, 150),
                               (Rank.ACE, 100), (Rank.TEN, 100),
                               (Rank.KING, 100), (Rank.QUEEN, 100)):
            with self.subTest(rank=rank):
                self.assertEqual(detect_melds(quad(rank).cards), (quad(rank),))
                self.assertEqual(quad(rank).points, expected)

    def test_sevens_eights_do_not_score(self):
        hand = tuple(Card(suit, rank) for suit in Suit for rank in (Rank.SEVEN, Rank.EIGHT))
        self.assertEqual(detect_melds(hand), ())

    def test_overlap_quad_and_run_is_allowed(self):
        melds = detect_melds(cards("H_10 H_J H_Q H_K H_A S_Q D_Q C_Q"))
        self.assertEqual(len(melds), 2)
        self.assertEqual(sum(m.points for m in melds), 200)
        self.assertIn(Card.parse("H_Q"), set(melds[0].cards) & set(melds[1].cards))

    def test_belot_is_not_an_ordinary_meld(self):
        for suit in Suit:
            hand = tuple(Card(suit, rank) for rank in Rank)
            self.assertTrue(has_belot(hand))
            self.assertEqual(detect_melds(hand), ())
        self.assertFalse(has_belot(cards("H_7 H_8 H_9 H_10 H_J H_Q H_K S_A")))

    def test_malformed_inputs(self):
        for hand in (cards("H_7 H_7"), deck()[:9], ("H_7",)):
            with self.subTest(hand=hand), self.assertRaises(ValueError):
                detect_melds(hand)
        for hand in (cards("H_7 H_9 H_J"), cards("H_7 H_8 S_9"),
                     cards("H_7 H_8"), tuple(Card(Suit.HEARTS, rank) for rank in Rank)):
            with self.subTest(hand=hand), self.assertRaises(ValueError):
                Meld(MeldKind.SEQUENCE, hand)
        with self.assertRaises(ValueError):
            Meld(MeldKind.FOUR_OF_A_KIND, tuple(Card(s, Rank.SEVEN) for s in Suit))


class MeldComparisonTests(unittest.TestCase):
    def test_full_quad_hierarchy(self):
        ordered = [quad(r) for r in (Rank.JACK, Rank.NINE, Rank.ACE,
                                     Rank.TEN, Rank.KING, Rank.QUEEN)]
        for stronger, weaker in zip(ordered, ordered[1:]):
            self.assertEqual(compare_melds(stronger, weaker), 1)
            self.assertEqual(compare_melds(weaker, stronger), -1)

    def test_quad_hundred_beats_run_hundred(self):
        self.assertEqual(compare_melds(quad(Rank.QUEEN),
                         sequence(Suit.SPADES, Rank.TEN, Rank.ACE)), 1)

    def test_five_to_ace_beats_six_to_king(self):
        self.assertEqual(compare_melds(sequence(Suit.HEARTS, Rank.TEN, Rank.ACE),
                         sequence(Suit.SPADES, Rank.EIGHT, Rank.KING)), 1)

    def test_equal_endpoint_hundred_ignores_length(self):
        self.assertEqual(compare_melds(sequence(Suit.HEARTS, Rank.TEN, Rank.ACE),
                         sequence(Suit.SPADES, Rank.EIGHT, Rank.ACE)), 0)

    def test_value_precedes_endpoint(self):
        self.assertEqual(compare_melds(sequence(Suit.HEARTS, Rank.SEVEN, Rank.TEN),
                         sequence(Suit.SPADES, Rank.QUEEN, Rank.ACE)), 1)

    def test_trump_suit_has_no_priority(self):
        self.assertEqual(compare_melds(sequence(Suit.HEARTS, Rank.SEVEN, Rank.NINE),
                         sequence(Suit.SPADES, Rank.SEVEN, Rank.NINE)), 0)

    def test_tie_uses_dealer_order(self):
        self.assertEqual(resolve_meld_contest(TIED_HANDS, Seat.THREE).winning_player, Seat.ZERO)
        self.assertEqual(resolve_meld_contest(TIED_HANDS, Seat.ZERO).winning_player, Seat.ONE)

    def test_strongest_meld_not_team_sum(self):
        result = resolve_meld_contest(STRONGEST_HANDS, Seat.THREE)
        self.assertEqual(result.winning_player, Seat.ONE)
        self.assertEqual(result.awarded_points, (0, 50))
        self.assertEqual(tuple(reveal.player for reveal in result.revealed), (Seat.ONE,))

    def test_both_partners_show_and_score_all_melds(self):
        # Exchange seats 1 and 2: fifty and two twenties now belong to one team.
        hands = (STRONGEST_HANDS[0], STRONGEST_HANDS[2],
                 STRONGEST_HANDS[1], STRONGEST_HANDS[3])
        result = resolve_meld_contest(hands, Seat.THREE)
        self.assertEqual(result.awarded_points, (90, 0))
        self.assertEqual(tuple(reveal.player for reveal in result.revealed), (Seat.ZERO, Seat.TWO))
        self.assertEqual(len(result.revealed[0].melds), 2)
        self.assertEqual(len(result.revealed[1].melds), 1)


class DeclarationPhaseTests(unittest.TestCase):
    def test_no_play_before_resolution(self):
        state = raw_state()
        self.assertEqual(state.phase, Phase.DECLARATIONS)
        self.assertIsNone(state.next_player)
        with self.assertRaises(ValueError):
            play_card(state, Seat.ZERO, next(iter(state.hands[0])))
        with self.assertRaises(ValueError):
            analyze(observe(state, Seat.ZERO))

    def test_presence_order_and_loser_privacy(self):
        state = resolve_declarations(raw_state(dealer=Seat.ZERO))
        public = observe(state, Seat.THREE)
        self.assertEqual(public.meld_contest.presence,
                         ((Seat.ONE, True), (Seat.TWO, False),
                          (Seat.THREE, False), (Seat.ZERO, True)))
        self.assertEqual(tuple(r.player for r in public.meld_contest.revealed), (Seat.ONE,))
        self.assertEqual(public.meld_contest.revealed[0].cards, frozenset(cards("S_7 S_8 S_9")))
        self.assertEqual(public.meld_announcements, ())
        self.assertFalse(hasattr(public, "hands"))

    def test_losing_spoken_information_is_retained(self):
        state = announce_meld_value(raw_state(dealer=Seat.ZERO), Seat.ZERO)
        state = announce_sequence_high(state, Seat.ZERO)
        state = resolve_declarations(state)
        public = observe(state, Seat.THREE)
        self.assertEqual(len(public.meld_announcements), 2)
        self.assertEqual(public.meld_announcements[0].points, 20)
        self.assertEqual(public.meld_announcements[1], SequenceHighAnnouncement(Seat.ZERO, Rank.NINE))
        self.assertNotIn(Seat.ZERO, tuple(r.player for r in public.meld_contest.revealed))

    def test_announcements_must_be_valid_and_before_play(self):
        state = raw_state()
        with self.assertRaises(ValueError):
            announce_meld_value(state, Seat.THREE)
        with self.assertRaises(ValueError):
            announce_sequence_high(state, Seat.ZERO)
        state = announce_meld_value(state, Seat.ZERO)
        with self.assertRaises(ValueError):
            announce_meld_value(state, Seat.ZERO)
        state = announce_sequence_high(state, Seat.ZERO)
        with self.assertRaises(ValueError):
            announce_sequence_high(state, Seat.ZERO)
        state = resolve_declarations(state)
        with self.assertRaises(ValueError):
            announce_meld_value(state, Seat.ONE)
        with self.assertRaises(ValueError):
            resolve_declarations(state)

    def test_detected_melds_reach_final_settlement(self):
        state = finish(resolve_declarations(raw_state()))
        result = settle_play(state)
        # Both sides win at least a trick in this fixture, so the winner's 20 is retained.
        self.assertEqual(result.total, 182)
        self.assertEqual(sum(result.recorded), 182)


class BelaTests(unittest.TestCase):
    def first_turn(self):
        return resolve_declarations(state_with_hand(
            cards("H_Q H_K S_7 S_9 S_J D_7 D_9 C_7")))

    def test_can_call_on_either_first_card(self):
        for code in ("H_Q", "H_K"):
            with self.subTest(code=code):
                before = self.first_turn()
                after = play_card(before, Seat.ZERO, Card.parse(code), announce_bela=True)
                self.assertEqual(before.bela_announcements, ())
                announcement = observe(after, Seat.ONE).bela_announcements[0]
                self.assertEqual(announcement.player, Seat.ZERO)
                self.assertEqual(announcement.card, Card.parse(code))
                self.assertEqual((announcement.trick_index, announcement.position), (0, 0))

    def test_cannot_call_without_both_cards_or_on_unrelated_card(self):
        state = self.first_turn()
        with self.assertRaises(ValueError):
            play_card(state, Seat.ZERO, Card.parse("S_7"), announce_bela=True)
        state = resolve_declarations(raw_state())  # seat 0 has H_Q but no H_K
        with self.assertRaises(ValueError):
            play_card(state, Seat.ZERO, Card.parse("H_Q"), announce_bela=True)

    def test_missed_first_card_cannot_be_repaired(self):
        state = play_card(self.first_turn(), Seat.ZERO, Card.parse("H_Q"))
        target = Card.parse("H_K")
        while not state.finished:
            player = state.next_player
            legal = analyze(observe(state, player)).legal_actions
            if player == Seat.ZERO and target in legal:
                with self.assertRaises(ValueError):
                    play_card(state, player, target, announce_bela=True)
                self.assertEqual(state.bela_announcements, ())
                return
            state = play_card(state, player, legal[0])
        self.fail("Fixture must offer the second bela card")

    def test_repeated_announcement_rejected(self):
        state = play_card(self.first_turn(), Seat.ZERO, Card.parse("H_Q"), announce_bela=True)
        target = Card.parse("H_K")
        while not state.finished:
            player = state.next_player
            legal = analyze(observe(state, player)).legal_actions
            if player == Seat.ZERO and target in legal:
                with self.assertRaises(ValueError):
                    play_card(state, player, target, announce_bela=True)
                after = play_card(state, player, target)
                self.assertEqual(len(after.bela_announcements), 1)
                return
            state = play_card(state, player, legal[0])
        self.fail("Fixture must offer the second bela card")

    def test_bela_is_additional_to_overlapping_meld(self):
        raw = state_with_hand(cards("H_10 H_J H_Q H_K H_A S_7 D_7 C_7"))
        before = resolve_declarations(raw)
        with_bela = play_card(before, Seat.ZERO, Card.parse("H_Q"), announce_bela=True)
        without_bela = play_card(before, Seat.ZERO, Card.parse("H_Q"))
        earned_with = settle_play(finish(with_bela)).earned
        earned_without = settle_play(finish(without_bela)).earned
        self.assertEqual(earned_with[0], earned_without[0] + 20)
        self.assertEqual(earned_with[1], earned_without[1])

    def test_called_bela_without_a_trick_does_not_score(self):
        state = finish(resolve_declarations(raw_state(SWEEP_HANDS)), call_bela=True)
        self.assertEqual(state.bela_announcements[0].player, Seat.ONE)
        result = settle_play(state)
        self.assertEqual(result.earned, (292, 0))
        self.assertEqual(result.total, 292)  # 252 sweep + two twenties, no bela


class BelotTests(unittest.TestCase):
    def test_instant_match_win_regardless_of_score(self):
        hand = tuple(Card(Suit.HEARTS, rank) for rank in Rank)
        raw = state_with_hand(hand)
        # All four players have a belot in this constructed deal. Only an actual
        # declaration determines the winner; detecting hidden hands does not.
        raw = start_play(raw.hands, trump=raw.trump, dealer=raw.dealer,
                         caller=raw.caller, match_score=(0, 990))
        state = declare_belot(raw, Seat.ZERO)
        result = settle_play(state)
        self.assertIsInstance(result, BelotResult)
        self.assertEqual(result.winning_team, 0)
        self.assertEqual(result.previous_score, (0, 990))
        self.assertEqual(state.match_score, (0, 990))
        self.assertEqual(state.phase, Phase.MATCH_FINISHED)
        self.assertTrue(state.finished)
        self.assertIsNone(state.next_player)
        self.assertEqual(state.completed_tricks, ())
        self.assertEqual(observe(state, Seat.ONE).belot.revealed_cards, frozenset(hand))
        with self.assertRaises(ValueError):
            play_card(state, Seat.ZERO, hand[0])
        with self.assertRaises(ValueError):
            declare_belot(state, Seat.ONE)

    def test_belot_can_be_non_trump(self):
        hand = tuple(Card(Suit.CLUBS, rank) for rank in Rank)
        state = declare_belot(state_with_hand(hand), Seat.ZERO)
        self.assertEqual(state.belot.winning_team, 0)

    def test_no_false_or_late_claim(self):
        with self.assertRaises(ValueError):
            declare_belot(raw_state(), Seat.ZERO)
        with self.assertRaises(ValueError):
            declare_belot(resolve_declarations(raw_state()), Seat.ZERO)

    def test_belot_cannot_be_silently_treated_as_an_ordinary_deal(self):
        hand = tuple(Card(Suit.HEARTS, rank) for rank in Rank)
        with self.assertRaises(ValueError):
            resolve_declarations(state_with_hand(hand))


if __name__ == "__main__":
    unittest.main()
