import json
import unittest
from unittest.mock import patch

from bela.domain.cards import Card, Rank, deck
from bela.domain.game import Seat
from bela.domain.cards import Suit
from bela.analysis.knowledge import _owner_possible, knowledge_view
from bela.gameplay.tracking import (AddEvent, DealSetup, DeleteEvent, FinishDeclarations, InsertEvent,
                           MeldValue, Play, Presence, Reveal, SequenceHigh, UserMatch, ValidationLimit)
from bela.storage.user_storage import dumps_user_match, loads_user_match


def cards(text):
    return tuple(Card.parse(c) for c in text.split())


def match_with(*events):
    setup = DealSetup(Seat.ZERO, cards("H_Q H_K S_9 S_10 S_A D_K C_8 C_9"),
                      Seat.THREE, Seat.ZERO, Suit.HEARTS)
    match = UserMatch.start(setup)
    for event in events:
        match = match.perform(AddEvent(event))
    return match


def row(data, card):
    return next(item for item in data["cards"] if item["card"] == card)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        _owner_possible.cache_clear()

    def test_initial_candidates_do_not_expose_a_chosen_hidden_deal(self):
        match = match_with()
        data = knowledge_view(match)
        self.assertTrue(data["complete"])
        self.assertEqual(len(data["cards"]), 24)
        self.assertEqual(data["facts"], [])
        for card in data["cards"]:
            self.assertEqual(card["owners"], [1, 2, 3])
            self.assertEqual(card["confirmed_possible"], [1, 2, 3])
        self.assertNotIn('"hands"', json.dumps(data))
        self.assertNotIn('"witness"', json.dumps(data))
        self.assertNotIn('"constraints"', json.dumps(data))
        self.assertNotIn('"evidence"', dumps_user_match(match))

    def test_discard_proves_void_suits_with_the_correct_source(self):
        match = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                           Play(Seat.ONE, Card.parse("C_7")))
        data = knowledge_view(match)
        reasons = [r for r in data["deductions"] if r["kind"] == "void_suit" and r["player"] == 1]
        self.assertEqual({r["suit"] for r in reasons}, {"S", "H"})
        self.assertTrue(all(r["events"] == (2,) for r in reasons))
        self.assertNotIn(1, row(data, "S_7")["owners"])
        self.assertNotIn(1, row(data, "H_7")["owners"])
        self.assertNotIn("C_7", [r["card"] for r in data["cards"]])

    def test_after_cut_following_does_not_claim_no_higher_plain_card(self):
        match = match_with(Reveal(Seat.TWO, cards("S_K S_7")), FinishDeclarations(None),
                           Play(Seat.ZERO, Card.parse("S_9")), Play(Seat.ONE, Card.parse("H_7")),
                           Play(Seat.TWO, Card.parse("S_7")))
        data = knowledge_view(match)
        self.assertFalse(any(r["kind"] == "no_higher" and r["player"] == 2 and r["suit"] == "S"
                             for r in data["deductions"]))
        self.assertEqual(row(data, "S_K")["owners"], [2])
        self.assertTrue(row(data, "S_K")["revealed"])

    def test_failure_to_head_proves_absence_of_higher_cards(self):
        match = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                           Play(Seat.ONE, Card.parse("S_7")))
        data = knowledge_view(match)
        reason = next(r for r in data["deductions"] if r["kind"] == "no_higher" and r["player"] == 1)
        self.assertEqual(reason["threshold"], "S_9")
        self.assertEqual(reason["events"], (2,))
        self.assertNotIn(1, row(data, "S_K")["owners"])

    def test_announced_quad_is_deduced_not_revealed(self):
        data = knowledge_view(match_with(MeldValue(Seat.ONE, 200)))
        for suit in "HSDC":
            card = row(data, suit + "_J")
            self.assertEqual(card["owners"], [1])
            self.assertFalse(card["revealed"])
            self.assertEqual(card["origin"]["kind"], "announced_quad")
            self.assertEqual(card["origin"]["events"], (0,))

    def test_losing_spoken_information_remains_a_public_fact(self):
        match = match_with(MeldValue(Seat.ONE, 20), SequenceHigh(Seat.ONE, Rank.KING),
                           Reveal(Seat.TWO, cards("H_7 H_8 H_9 H_10")), FinishDeclarations(0))
        data = knowledge_view(match)
        self.assertEqual(data["facts"][0]["event"], {"type": "meld_value", "player": 1, "points": 20})
        self.assertEqual(data["facts"][1]["event"]["type"], "sequence_high")
        self.assertEqual(data["facts"][-1]["event"]["winning_team"], 0)

    def test_own_winning_meld_reveal_is_a_public_fact_without_extra_cards(self):
        setup = DealSetup(Seat.ZERO, cards("H_7 H_8 H_9 H_10 H_Q H_K S_A D_A"),
                          Seat.THREE, Seat.ZERO, Suit.HEARTS)
        match = UserMatch.start(setup).perform(AddEvent(FinishDeclarations(0)))
        data = knowledge_view(match)
        newly_public = data["facts"][0]["revealed_cards"]
        self.assertEqual({c["card"] for c in newly_public}, {"H_7", "H_8", "H_9", "H_10"})
        self.assertTrue(all(c["player"] == 0 for c in newly_public))
        self.assertEqual(data["revealed_count"], 4)

    def test_combined_hand_and_sequence_clues_prove_ownership(self):
        match = match_with(MeldValue(Seat.ONE, 50), SequenceHigh(Seat.ONE, Rank.ACE))
        data = knowledge_view(match)
        for code in ("C_J", "C_Q", "C_K", "C_A"):
            self.assertEqual(row(data, code)["owners"], [1])
            self.assertFalse(row(data, code)["revealed"])
        # Delete the high-card clue: hearts can provide 50 instead, so the club
        # cards must no longer be displayed as proven to belong to player 1.
        corrected = match.perform(DeleteEvent(1))
        updated = knowledge_view(corrected)
        self.assertGreater(len(row(updated, "C_J")["owners"]), 1)
        self.assertEqual(updated["revision"], corrected.revision)
        for card in updated["cards"]:
            for excluded in card["excluded"]:
                self.assertTrue(all(i < 1 for i in excluded["reason"]["events"]))

    def test_capacity_can_prove_an_unrevealed_hand(self):
        match = match_with()
        other = [c for c in deck() if c not in match.initial.hand]
        match = match.perform(AddEvent(Reveal(Seat.ONE, tuple(other[:8]))))
        match = match.perform(AddEvent(Reveal(Seat.TWO, tuple(other[8:16]))))
        data = knowledge_view(match)
        for card in other[16:]:
            inferred = row(data, str(card))
            self.assertEqual(inferred["owners"], [3])
            self.assertFalse(inferred["revealed"])

    def test_corrections_rebuild_reasons_and_shift_source_indexes(self):
        match = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                           Play(Seat.ONE, Card.parse("H_7")))
        changed = match.perform(InsertEvent(0, Presence(Seat.ZERO, False)))
        data = knowledge_view(changed)
        reason = next(r for r in data["deductions"] if r["kind"] == "void_suit" and r["player"] == 1)
        self.assertEqual(reason["events"], (3,))
        without_play = changed.perform(DeleteEvent(3))
        restored = knowledge_view(without_play)
        self.assertIn(1, row(restored, "S_7")["owners"])
        self.assertFalse(any(r["kind"] == "void_suit" and r["player"] == 1 and r["suit"] == "S"
                             for r in restored["deductions"]))
        self.assertEqual(restored, knowledge_view(loads_user_match(dumps_user_match(without_play))))

    def test_unfinished_checks_never_exclude_an_owner_or_invent_certainty(self):
        match = match_with()
        with patch("bela.analysis.knowledge._owner_possible", side_effect=ValidationLimit("test budget")):
            data = knowledge_view(match)
        self.assertFalse(data["complete"])
        self.assertEqual(data["pending_checks"], 72)
        self.assertTrue(all(r["owners"] == [1, 2, 3] and not r["confirmed_possible"] for r in data["cards"]))
        self.assertTrue(knowledge_view(match)["complete"])
        self.assertFalse(knowledge_view(match, seconds=0)["complete"])
