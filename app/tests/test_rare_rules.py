"""Deterministic rare-rule regressions; no random matches or Monte Carlo."""

from dataclasses import replace
import unittest

from bela.domain.cards import Rank, Suit, deck
from bela.domain.game import Seat
from bela.gameplay.session import MatchSession, initial_hands
from bela.gameplay.simulation import declare_belot, resolve_declarations, start_play
from bela.rules.melds import resolve_meld_contest
from bela.rules.scoring import settle_deal
from bela.storage.persistence import dumps_match, loads_match
from test_declarations import TIED_HANDS, finish, raw_state


class RareRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This fixed deal settles 113–69, so both teams cross the boundary.
        cls.finished = finish(resolve_declarations(raw_state()))

    def session_at(self, final_score):
        before = (final_score[0] - 113, final_score[1] - 69)
        self.assertTrue(all(0 <= n <= 1000 for n in before))
        return MatchSession.start(replace(self.finished, match_score=before))

    def next_deal(self, session):
        return session.next_deal(initial_hands(self.finished), trump=Suit.SPADES,
                                 caller=Seat.ONE)

    def test_exactly_1000_allows_next_deal(self):
        session = self.session_at((1000, 999))
        self.assertEqual(session.score, (1000, 999))
        self.assertIsNone(session.winner)
        self.assertEqual(self.next_deal(session).current.match_score, (1000, 999))

    def test_tie_above_1000_survives_save_and_continues(self):
        session = loads_match(dumps_match(self.session_at((1001, 1001))))
        self.assertEqual(session.score, (1001, 1001))
        self.assertIsNone(session.winner)
        continued = loads_match(dumps_match(self.next_deal(session)))
        self.assertEqual(len(continued.deals), 2)
        self.assertEqual(continued.score, (1001, 1001))
        self.assertEqual(continued.current.dealer, session.current.dealer.next)
        self.assertIsNone(continued.winner)

    def test_both_above_1000_higher_team_wins_and_blocks_next_deal(self):
        for score, winner in (((1002, 1001), 0), ((1001, 1002), 1)):
            with self.subTest(score=score):
                session = loads_match(dumps_match(self.session_at(score)))
                self.assertEqual(session.score, score)
                self.assertEqual(session.winner, winner)
                with self.assertRaises(ValueError):
                    self.next_deal(session)

    def test_equal_meld_priority_rotates_with_dealer_and_seats(self):
        for rotation in range(4):
            hands = tuple(TIED_HANDS[(seat - rotation) % 4] for seat in range(4))
            contenders = {rotation, (rotation + 1) % 4}
            for dealer in Seat:
                with self.subTest(rotation=rotation, dealer=dealer):
                    expected = next(Seat((int(dealer) + step) % 4)
                                    for step in range(1, 5)
                                    if (int(dealer) + step) % 4 in contenders)
                    contest = resolve_meld_contest(hands, dealer)
                    self.assertEqual(contest.winning_player, expected)
                    self.assertEqual(tuple(r.player for r in contest.revealed),
                                     (expected,))

    def test_belot_every_seat_and_suit_ends_match_without_points(self):
        for player in Seat:
            for suit in Suit:
                with self.subTest(player=player, suit=suit):
                    hand = tuple(c for c in deck() if c.suit == suit)
                    self.assertEqual(len(hand), len(Rank))
                    remaining = [c for c in deck() if c not in hand]
                    hands = []
                    for seat in Seat:
                        hands.append(hand if seat == player else tuple(remaining[:8]))
                        if seat != player:
                            del remaining[:8]
                    score = (0, 990) if player.team == 0 else (990, 0)
                    trump = next(s for s in Suit if s != suit)
                    state = start_play(hands, trump=trump, dealer=Seat.THREE,
                                       caller=Seat.ZERO, match_score=score)
                    session = loads_match(dumps_match(MatchSession.start(
                        declare_belot(state, player))))
                    self.assertEqual(session.winner, player.team)
                    self.assertEqual(session.score, score)
                    self.assertEqual(session.current.completed_tricks, ())
                    with self.assertRaises(ValueError):
                        self.next_deal(session)

    def test_equal_points_with_meld_and_bela_defeat_either_caller(self):
        # 71 + last trick 10 + meld 20 = 81 + bela 20 = 101.
        for caller in (0, 1):
            with self.subTest(caller=caller):
                result = settle_deal(card_points=(71, 81), trick_counts=(4, 4),
                                     last_trick_team=0, caller_team=caller,
                                     awarded_melds=(20, 0), announced_bela=(0, 20))
                self.assertEqual(result.earned, (101, 101))
                self.assertFalse(result.caller_passed)
                self.assertEqual(result.recorded[caller], 0)
                self.assertEqual(result.recorded[1 - caller], 202)


if __name__ == '__main__':
    unittest.main()
