import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, Seat
from bela.domain.melds import BelotResult
from bela.storage.persistence import InvalidSaveError, loads_match
from bela.rules.play import legal_cards
from bela.gameplay.simulation import (observe, play_card, resolve_declarations, settle_play, start_play)
from bela.gameplay.tracking import (AddEvent, Belot, DealSetup, DeleteEvent, FinishDeclarations,
                           InconsistentInput, InsertEvent, MeldValue, NextDeal, Play,
                           Presence, ReplaceEvent, ReplaceSetup, Reveal, SequenceHigh,
                           UserMatch, ValidationLimit, _allocation_exists)
from bela.interfaces.player_cli import parse_event, parse_suit
from bela.storage.user_storage import (dumps_user_match, load_user_match, loads_user_match,
                               save_user_match)


def cards(text):
    return tuple(Card.parse(value) for value in text.split())


def setup():
    return DealSetup(Seat.ZERO, cards("H_Q H_K S_9 S_10 S_A D_K C_8 C_9"),
                     Seat.THREE, Seat.ZERO, Suit.HEARTS)


def started():
    return UserMatch.start(setup()).perform(AddEvent(FinishDeclarations(None)))


def add(match, event):
    return match.perform(AddEvent(event))


class UserInputTests(unittest.TestCase):
    def test_only_own_hand_is_required_and_stored(self):
        match = UserMatch.start(setup())
        self.assertFalse(hasattr(match.state, "hands"))
        self.assertEqual(match.state.hand, frozenset(setup().hand))
        self.assertEqual(match.state.remaining_counts, (8, 8, 8, 8))
        self.assertEqual(match.state.revealed, (frozenset(),) * 4)
        data = json.loads(dumps_user_match(match))
        self.assertNotIn("hands", dumps_user_match(match))
        self.assertEqual(len(data["initial"]["hand"]), 8)
        self.assertEqual(data["commands"], [])

    def test_setup_validation(self):
        for changes in ({"hand": setup().hand[:-1]}, {"hand": (setup().hand[0],) * 8},
                        {"player": 0}, {"match_score": (-1, 0)}, {"match_score": (1001, 0)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(setup(), **changes)

    def test_requires_declarations_and_correct_turn(self):
        with self.assertRaises(InconsistentInput):
            add(UserMatch.start(setup()), Play(Seat.ZERO, Card.parse("H_Q")))
        match = started()
        with self.assertRaises(InconsistentInput):
            add(match, Play(Seat.ONE, Card.parse("H_7")))

    def test_own_legal_cards_and_duplicate_rejection(self):
        match = started()
        self.assertEqual(set(match.state.legal_actions), set(setup().hand))
        after = add(match, Play(Seat.ZERO, Card.parse("H_Q")))
        self.assertEqual(after.state.remaining_counts, (7, 8, 8, 8))
        self.assertNotIn(Card.parse("H_Q"), after.state.hand)
        self.assertEqual(after.state.legal_actions, ())
        with self.assertRaises(InconsistentInput):
            add(after, Play(Seat.ONE, Card.parse("H_Q")))
        with self.assertRaises(InconsistentInput):
            add(after, Play(Seat.ONE, Card.parse("S_A")))  # our private card

    def test_unknown_hand_play_is_allowed_when_a_legal_world_exists(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("S_9")))
        match = add(match, Play(Seat.ONE, Card.parse("H_7")))  # possible: no spades
        self.assertEqual(match.state.current_trick.cards, cards("S_9 H_7"))

    def test_follow_obligation_from_shown_cards(self):
        match = add(UserMatch.start(setup()), Reveal(Seat.ONE, cards("S_7")))
        match = add(match, FinishDeclarations(None))
        match = add(match, Play(Seat.ZERO, Card.parse("S_9")))
        with self.assertRaises(InconsistentInput):
            add(match, Play(Seat.ONE, Card.parse("H_7")))

    def test_nonheading_excludes_stronger_cards(self):
        match = add(UserMatch.start(setup()), Reveal(Seat.ONE, cards("S_K")))
        match = add(match, FinishDeclarations(None))
        match = add(match, Play(Seat.ZERO, Card.parse("S_9")))
        with self.assertRaises(InconsistentInput):
            add(match, Play(Seat.ONE, Card.parse("S_7")))

    def test_after_cut_following_does_not_require_heading(self):
        match = add(UserMatch.start(setup()), Reveal(Seat.TWO, cards("S_K S_7")))
        match = add(match, FinishDeclarations(None))
        for event in (Play(Seat.ZERO, Card.parse("S_9")), Play(Seat.ONE, Card.parse("H_7")),
                      Play(Seat.TWO, Card.parse("S_7"))):
            match = add(match, event)
        self.assertEqual(len(match.state.current_trick.cards), 3)

    def test_partner_does_not_waive_overtrumping(self):
        match = add(UserMatch.start(setup()), Reveal(Seat.THREE, cards("H_J")))
        match = add(match, FinishDeclarations(None))
        for event in (Play(Seat.ZERO, Card.parse("S_9")), Play(Seat.ONE, Card.parse("H_9")),
                      Play(Seat.TWO, Card.parse("S_7"))):
            match = add(match, event)
        with self.assertRaises(InconsistentInput):
            add(match, Play(Seat.THREE, Card.parse("H_7")))

    def test_capacity_constraints_catch_jointly_impossible_ownership(self):
        match = add(UserMatch.start(setup()), Reveal(Seat.ONE, cards("H_7 H_8 H_9 H_10 H_J H_A S_7 S_8")))
        with self.assertRaises(InconsistentInput):
            add(match, Reveal(Seat.ONE, cards("S_J")))

    def test_validation_timeout_is_not_reported_as_proven_impossibility(self):
        with self.assertRaises(ValidationLimit):
            _allocation_exists([15] * 32, {}, max_nodes=0)
        self.assertFalse(_allocation_exists([1] * 9 + [14] * 23, {}))


class ObservedDeclarationsTests(unittest.TestCase):
    def test_values_do_not_reveal_exact_cards(self):
        match = add(UserMatch.start(setup()), MeldValue(Seat.ONE, 50))
        self.assertEqual(match.state.revealed[1], frozenset())
        match = add(match, SequenceHigh(Seat.ONE, Rank.ACE))
        self.assertEqual(match.state.revealed[1], frozenset())

    def test_nonsense_endpoint_and_false_own_meld_are_rejected(self):
        match = add(UserMatch.start(setup()), MeldValue(Seat.ONE, 50))
        with self.assertRaises(InconsistentInput):
            add(match, SequenceHigh(Seat.ONE, Rank.NINE))
        with self.assertRaises(InconsistentInput):
            add(UserMatch.start(setup()), Presence(Seat.ZERO, True))

    def test_winning_melds_must_be_shown_and_are_counted(self):
        with self.assertRaises(InconsistentInput):
            add(UserMatch.start(setup()), FinishDeclarations(1))
        match = add(UserMatch.start(setup()), Reveal(Seat.TWO, cards("H_8 H_9 H_10")))
        match = add(match, FinishDeclarations(0))
        self.assertEqual(match.state.awarded_melds, (20, 0))
        self.assertEqual(match.state.revealed[2], frozenset(cards("H_8 H_9 H_10")))

    def test_losing_value_cannot_exceed_winning_shown_meld(self):
        match = add(UserMatch.start(setup()), MeldValue(Seat.ONE, 200))
        match = add(match, Reveal(Seat.TWO, cards("H_8 H_9 H_10")))
        with self.assertRaises(InconsistentInput):
            add(match, FinishDeclarations(0))

    def test_bela_is_timed_and_survives_storage(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("H_Q"), True))
        loaded = loads_user_match(dumps_user_match(match))
        self.assertEqual(loaded.state.bela_announcements[0].player, Seat.ZERO)
        self.assertEqual(match.state, loaded.state)
        self.assertEqual(loaded.state.revealed[1], frozenset())

    def test_opponents_bela_cannot_use_our_king(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("S_9")))
        with self.assertRaises(InconsistentInput):
            add(match, Play(Seat.ONE, Card.parse("H_Q"), True))

    def test_belot_requires_real_shown_cards(self):
        hand = tuple(Card(Suit.CLUBS, rank) for rank in Rank)
        own = replace(setup(), hand=cards("H_Q H_K S_9 S_10 S_A D_K D_7 D_8"))
        match = add(UserMatch.start(own), Belot(Seat.ONE, hand))
        self.assertEqual(match.state.winner, 1)
        self.assertIsInstance(match.state.result, BelotResult)
        self.assertEqual(match.state.score, (0, 0))
        self.assertEqual(loads_user_match(dumps_user_match(match)), match)
        with self.assertRaises(InconsistentInput):
            add(UserMatch.start(setup()), Belot(Seat.ONE))
        with self.assertRaises(InconsistentInput):
            add(UserMatch.start(setup()), Belot(Seat.ONE, hand))  # our C_8/C_9 forbid it


class CorrectionTests(unittest.TestCase):
    def test_replacement_rebuilds_hand_and_preserves_old_input(self):
        old = add(started(), Play(Seat.ZERO, Card.parse("H_Q")))
        new = old.perform(ReplaceEvent(1, Play(Seat.ZERO, Card.parse("H_K"))))
        self.assertIn(Card.parse("H_Q"), new.state.hand)
        self.assertNotIn(Card.parse("H_K"), new.state.hand)
        self.assertEqual(old.state.current_trick.cards, cards("H_Q"))
        data = dumps_user_match(new)
        self.assertIn('"H_Q"', data)
        self.assertIn('"H_K"', data)
        self.assertEqual(loads_user_match(data), new)
        self.assertEqual(new.revision, 3)

    def test_invalid_correction_does_not_change_match(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("H_Q")))
        with self.assertRaises(InconsistentInput):
            match.perform(ReplaceEvent(1, Play(Seat.ONE, Card.parse("H_7"))))
        self.assertEqual(match.state.current_trick.cards, cards("H_Q"))

    def test_delete_and_insert_replay_constraints(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("S_9")))
        match = add(match, Play(Seat.ONE, Card.parse("H_7")))
        with self.assertRaises(InconsistentInput):
            match.perform(InsertEvent(0, Reveal(Seat.ONE, cards("S_7"))))
        match = match.perform(DeleteEvent(2))
        match = match.perform(InsertEvent(0, Reveal(Seat.ONE, cards("S_7"))))
        self.assertEqual(match.state.revealed[1], frozenset(cards("S_7")))
        self.assertEqual(loads_user_match(dumps_user_match(match)), match)

    def test_setup_correction_revalidates_history(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("H_Q")))
        with self.assertRaises(InconsistentInput):
            match.perform(ReplaceSetup(replace(setup(), dealer=Seat.ZERO)))
        changed = match.perform(ReplaceSetup(replace(setup(), caller=Seat.ONE)))
        self.assertEqual(changed.state.setup.caller, Seat.ONE)


class ReplayAgainstSimulatorTests(unittest.TestCase):
    def test_real_observations_reproduce_complete_simulator_results(self):
        for seed in range(3):
            shuffled = list(deck())
            random.Random(seed + 40).shuffle(shuffled)
            full = resolve_declarations(start_play([shuffled[i:i + 8] for i in range(0, 32, 8)],
                                        trump=Suit.HEARTS, dealer=Seat.THREE, caller=Seat.ZERO))
            player = Seat(seed)
            match = UserMatch.start(DealSetup(player, tuple(sorted(full.hands[player], key=lambda c: c.id)),
                                             full.dealer, full.caller, full.trump))
            for reveal in full.meld_contest.revealed:
                match = add(match, Reveal(reveal.player, tuple(sorted(reveal.cards, key=lambda c: c.id))))
            match = add(match, FinishDeclarations(full.meld_contest.winning_team))
            while not full.finished:
                actor = full.next_player
                card = legal_cards(full.hands[actor], full.current_trick, full.trump)[0]
                pair = {Card(full.trump, Rank.KING), Card(full.trump, Rank.QUEEN)}
                bela = card in pair and pair.issubset(full.hands[actor])
                full = play_card(full, actor, card, announce_bela=bela)
                match = add(match, Play(actor, card, bela))
                self.assertEqual(match.state.hand, full.hands[player])
                self.assertEqual(match.state.current_trick, full.current_trick)
                self.assertEqual(match.state.completed_tricks, full.completed_tricks)
            self.assertEqual(match.state.result, settle_play(full))
            self.assertEqual(loads_user_match(dumps_user_match(match)), match)
            if match.state.winner is None:
                hand = tuple(sorted(full.hands[player], key=lambda c: c.id))  # empty after deal
                self.assertEqual(hand, ())
                next_setup = DealSetup(player, setup().hand, full.dealer.next, Seat.ONE,
                                       Suit.SPADES, match.state.score)
                next_match = match.perform(NextDeal(next_setup))
                self.assertEqual(len(next_match.deals), 2)
                self.assertEqual(next_match.state.score, match.state.score)
                self.assertEqual(loads_user_match(dumps_user_match(next_match)), next_match)


class UserStorageAndCliTests(unittest.TestCase):
    def test_user_archive_rejects_bad_versions_types_and_history(self):
        original = dumps_user_match(started())
        for field, value in (("schema_version", True), ("schema_version", 2),
                              ("format", "simulator"), ("ruleset_version", "other"),
                              ("id", "invalid"), ("name", "")):
            data = json.loads(original)
            data[field] = value
            with self.subTest(field=field), self.assertRaises(InvalidSaveError):
                loads_user_match(json.dumps(data))
        for text in ("{}", "not JSON", '{"format":"a","format":"b"}', "NaN"):
            with self.subTest(text=text), self.assertRaises(InvalidSaveError):
                loads_user_match(text)

    def test_file_round_trip_and_separate_format(self):
        match = add(started(), Play(Seat.ZERO, Card.parse("H_Q"), True))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "moja partija.json"
            save_user_match(match, path)
            self.assertEqual(load_user_match(path), match)
            with self.assertRaises(InvalidSaveError):
                loads_match(path.read_text(encoding="utf-8"))
        data = json.loads(dumps_user_match(match))
        data["commands"][1]["event"]["player"] = 1
        with self.assertRaises(InvalidSaveError):
            loads_user_match(json.dumps(data))

    def test_parser_and_suit_names(self):
        self.assertEqual(parse_suit("žir"), Suit.CLUBS)
        self.assertEqual(parse_suit("zelena"), Suit.SPADES)
        self.assertEqual(parse_event("potez 0 H_Q bela".split(), started().state),
                         Play(Seat.ZERO, Card.parse("H_Q"), True))
        for text in ("potez", "potez 4 H_7", "igraj H_7 nonsense", "ima 1 mozda", "zvanje 1"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_event(text.split(), started().state)

    def test_console_new_save_correct_load_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "moja partija.json"
            inputs = ["Test partija", "0", "3", "0:0", "0", "herc",
                      "H_Q H_K S_9 S_10 S_A D_K C_8 C_9", "zvanja nema",
                      "potez 0 H_Q bela", "povijest", "ispravi 2 potez 0 H_K bela", "izlaz"]
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, "-m", "bela", "track", "--save", str(path)],
                                    input=("\n".join(inputs) + "\n").encode("utf-8"),
                                    capture_output=True, env=env, check=True)
            output = result.stdout.decode("utf-8")
            self.assertNotIn("Unos nije prihvaćen", output)
            match = load_user_match(path)
            self.assertEqual(match.state.current_trick.cards, cards("H_K"))
            self.assertEqual(match.state.next_player, Seat.ONE)
            result = subprocess.run([sys.executable, "-m", "bela", "track", "--load", str(path)],
                                    input="potez 1 H_7\nizlaz\n".encode("utf-8"),
                                    capture_output=True, env=env, check=True)
            self.assertNotIn("Unos nije prihvaćen", result.stdout.decode("utf-8"))
            self.assertEqual(load_user_match(path).state.current_trick.cards, cards("H_K H_7"))


if __name__ == "__main__":
    unittest.main()
