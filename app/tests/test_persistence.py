import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, Seat
from bela.domain.melds import MeldKind
from bela.persistence import (InvalidSaveError, dumps_match, load_match, loads_match,
                              save_match)
from bela.rules.melds import detect_melds
from bela.rules.play import legal_cards
from bela.session import MatchSession
from bela.simulation import (announce_meld_value, announce_sequence_high, declare_belot,
                             observe, play_card, resolve_declarations, start_play)


def new_state(seed=42, score=(0, 0)):
    shuffled = list(deck())
    random.Random(seed).shuffle(shuffled)
    return start_play([shuffled[i:i + 8] for i in range(0, 32, 8)],
                      trump=Suit.HEARTS, dealer=Seat.THREE,
                      caller=Seat.ZERO, match_score=score)


def advance(state, count=32):
    if state.phase == Phase.DECLARATIONS:
        state = resolve_declarations(state)
    for _ in range(count):
        if state.finished:
            break
        player = state.next_player
        card = legal_cards(state.hands[player], state.current_trick, state.trump)[0]
        pair = {Card(state.trump, Rank.KING), Card(state.trump, Rank.QUEEN)}
        state = play_card(state, player, card,
                          announce_bela=card in pair and pair.issubset(state.hands[player]))
    return state


def belot_state():
    return declare_belot(start_play(
        [tuple(Card(suit, rank) for rank in Rank) for suit in Suit],
        trump=Suit.HEARTS, dealer=Seat.THREE, caller=Seat.ZERO), Seat.ONE)


class RoundTripTests(unittest.TestCase):
    def round_trip(self, state):
        session = MatchSession.start(state, name="Naša večernja partija")
        loaded = loads_match(dumps_match(session))
        self.assertEqual(session, loaded)
        self.assertEqual(session.score, loaded.score)
        for player in Seat:
            self.assertEqual(observe(state, player), observe(loaded.current, player))
        return loaded

    def test_initial_and_partly_announced_declarations(self):
        state = new_state()
        self.round_trip(state)
        player = next(seat for seat in Seat if detect_melds(state.hands[seat]))
        state = announce_meld_value(state, player)
        self.round_trip(state)
        if detect_melds(state.hands[player])[0].kind == MeldKind.SEQUENCE:
            self.round_trip(announce_sequence_high(state, player))

    def test_all_33_play_checkpoints_including_bela_and_final_settlement(self):
        state = resolve_declarations(new_state())
        found_bela = False
        for turn in range(33):
            with self.subTest(turn=turn):
                loaded = self.round_trip(state)
                self.assertEqual(loaded.current, state)
                found_bela |= bool(state.bela_announcements)
            if turn < 32:
                state = advance(state, 1)
        self.assertTrue(found_bela)

    def test_resume_matches_uninterrupted_game(self):
        state = advance(new_state(), 7)
        loaded = self.round_trip(state)
        self.assertEqual(advance(state), advance(loaded.current))

    def test_missed_bela_is_not_recovered_on_load(self):
        state = resolve_declarations(new_state())
        self.assertTrue({Card.parse("H_Q"), Card.parse("H_K")}.issubset(state.hands[0]))
        state = play_card(state, Seat.ZERO, Card.parse("H_Q"))
        state = self.round_trip(state).current
        while not state.finished:
            player = state.next_player
            legal = legal_cards(state.hands[player], state.current_trick, state.trump)
            if player == Seat.ZERO and Card.parse("H_K") in legal:
                with self.assertRaises(ValueError):
                    play_card(state, player, Card.parse("H_K"), announce_bela=True)
                return
            state = play_card(state, player, legal[0])
        self.fail("Expected the second bela card to be played")

    def test_belot_round_trip_and_winner(self):
        loaded = self.round_trip(belot_state())
        self.assertEqual(loaded.winner, 1)
        self.assertEqual(loaded.score, (0, 0))

    def test_serialization_is_deterministic(self):
        session = MatchSession.start(advance(new_state(), 7))
        first = dumps_match(session)
        self.assertEqual(first, dumps_match(session))
        self.assertEqual(first, dumps_match(loads_match(first)))
        self.assertNotIn("earned", first)  # derived fields are recomputed


class MatchHistoryTests(unittest.TestCase):
    def test_multiple_deals_keep_history_and_apply_points_once(self):
        first = MatchSession.start(advance(new_state()))
        second = first.next_deal(new_state(43).hands, trump=Suit.SPADES, caller=Seat.TWO)
        self.assertEqual(second.current.dealer, Seat.ZERO)
        self.assertEqual(second.current.match_score, first.score)
        self.assertEqual(second.score, first.score)
        self.assertEqual(second.id, first.id)
        self.assertEqual(second.deals[0], first.current)
        second = second.with_current(advance(second.current, 11))
        loaded = loads_match(dumps_match(second))
        self.assertEqual(loaded, second)
        self.assertEqual(loaded.deals[0], first.current)
        complete = loaded.with_current(advance(loaded.current))
        self.assertEqual(loads_match(dumps_match(complete)).score, complete.score)
        self.assertEqual(loads_match(dumps_match(loads_match(dumps_match(complete)))), complete)

    def test_cannot_start_after_unfinished_or_won_match(self):
        for session in (MatchSession.start(new_state()), MatchSession.start(belot_state()),
                        MatchSession.start(advance(new_state(score=(990, 990))))):
            with self.subTest(phase=session.current.phase), self.assertRaises(ValueError):
                session.next_deal(new_state(43).hands, trump=Suit.SPADES, caller=Seat.ZERO)

    def test_checkpoint_must_belong_to_current_deal(self):
        session = MatchSession.start(new_state())
        with self.assertRaises(ValueError):
            session.with_current(new_state(43))
        changed = replace(session.current, caller=Seat.ONE)
        with self.assertRaises(ValueError):
            session.with_current(changed)

    def test_invalid_history_is_rejected(self):
        first = MatchSession.start(advance(new_state()))
        valid = first.next_deal(new_state(43).hands, trump=Suit.CLUBS, caller=Seat.ONE)
        for bad in (replace(valid.current, match_score=(0, 0)),
                    replace(valid.current, dealer=Seat.THREE)):
            # Rebuild a legal individual deal, but with invalid match linkage.
            bad = start_play(bad.hands, trump=bad.trump, dealer=bad.dealer,
                             caller=bad.caller, match_score=bad.match_score)
            with self.subTest(bad=bad), self.assertRaises(InvalidSaveError):
                dumps_match(replace(valid, deals=(first.current, bad)))


class InvalidArchiveTests(unittest.TestCase):
    def data(self):
        return json.loads(dumps_match(MatchSession.start(advance(new_state(), 3))))

    def test_versions_and_metadata(self):
        for field, value in (("schema_version", 2), ("schema_version", True),
                              ("ruleset_version", "some-other-bela")):
            data = self.data()
            data[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidSaveError):
                loads_match(json.dumps(data))
        for field, value in (("id", "bad-id"), ("id", 123), ("name", ""),
                              ("name", None), ("deals", [])):
            data = self.data()
            data["match"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidSaveError):
                loads_match(json.dumps(data))

    def test_invalid_deal_configuration(self):
        for field, value in (("dealer", True), ("caller", 4), ("trump", "X"),
                              ("match_score", [-1, 0]), ("match_score", [False, 0]),
                              ("match_score", [1001, 0]), ("hands", [[], [], [], []])):
            data = self.data()
            data["match"]["deals"][0]["initial"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidSaveError):
                loads_match(json.dumps(data))

    def test_duplicate_cards(self):
        data = self.data()
        hands = data["match"]["deals"][0]["initial"]["hands"]
        hands[0][0] = hands[1][0]
        with self.assertRaises(InvalidSaveError):
            loads_match(json.dumps(data))

    def test_illegal_actions_and_bela_are_rejected(self):
        for field, value in (("player", 2), ("card", "X_A"), ("bela", 1),
                              ("type", "invent_points")):
            data = self.data()
            data["match"]["deals"][0]["actions"][1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InvalidSaveError):
                loads_match(json.dumps(data))
        data = self.data()
        # First action announces bela on H_Q; the next action is not a valid bela.
        data["match"]["deals"][0]["actions"][2]["bela"] = True
        with self.assertRaises(InvalidSaveError):
            loads_match(json.dumps(data))

    def test_spoken_value_and_endpoint_must_match_hand(self):
        state = new_state()
        player = next(seat for seat in Seat if detect_melds(state.hands[seat]))
        state = announce_sequence_high(announce_meld_value(state, player), player)
        base = dumps_match(MatchSession.start(state))
        for index, field, value in ((0, "points", 200), (1, "rank", "7")):
            data = json.loads(base)
            data["match"]["deals"][0]["actions"][index][field] = value
            with self.subTest(field=field), self.assertRaises(InvalidSaveError):
                loads_match(json.dumps(data))

    def test_unknown_fields_duplicate_keys_and_non_json(self):
        data = self.data()
        data["invented_score"] = 200
        invalid = [json.dumps(data), '{"schema_version":1,"schema_version":1}',
                   "not JSON", "[]", "NaN", "{", "[" * 1500 + "]" * 1500]
        for text in invalid:
            with self.subTest(text=text[:40]), self.assertRaises(InvalidSaveError):
                loads_match(text)

    def test_inconsistent_in_memory_checkpoint_is_not_saved(self):
        state = advance(new_state(), 1)
        for bad in (replace(state, phase=Phase.DEAL_FINISHED),
                    replace(state, bela_announcements=(replace(
                        state.bela_announcements[0], player=Seat.ONE),)),
                    replace(state, meld_contest=replace(state.meld_contest, awarded_points=(200, 0)))):
            with self.subTest(bad=bad), self.assertRaises(InvalidSaveError):
                dumps_match(MatchSession.start(bad))


class FileTests(unittest.TestCase):
    def test_file_save_load_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partije" / "Večernja bela.json"
            session = MatchSession.start(new_state(), name="Naša partija")
            self.assertEqual(save_match(session, path), path)
            self.assertEqual(load_match(path), session)
            session = session.with_current(advance(session.current, 5))
            save_match(session, path)
            self.assertEqual(load_match(path), session)
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_failed_replacement_preserves_previous_save_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            session = MatchSession.start(new_state())
            save_match(session, path)
            original = path.read_bytes()
            updated = session.with_current(advance(session.current, 5))
            with patch("bela.persistence.os.replace", side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    save_match(updated, path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_validation_failure_preserves_previous_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            session = MatchSession.start(new_state())
            save_match(session, path)
            original = path.read_bytes()
            with self.assertRaises(InvalidSaveError):
                save_match(replace(session, name=""), path)
            self.assertEqual(path.read_bytes(), original)

    def test_invalid_utf8_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            with self.assertRaises(FileNotFoundError):
                load_match(path)
            path.write_bytes(b"\xff")
            with self.assertRaises(InvalidSaveError):
                load_match(path)

    def test_cli_pause_resume_and_add_another_deal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            env = dict(os.environ, PYTHONIOENCODING="utf-8")

            def run(*args):
                return subprocess.run([sys.executable, "-m", "bela", *map(str, args)],
                                      env=env, capture_output=True, check=True)

            run("--save", path, "--moves", 5, "--name", "Moja partija")
            paused = load_match(path)
            self.assertEqual(sum(map(len, paused.current.hands)), 27)
            run("--load", path, "--save", path)
            completed = load_match(path)
            self.assertTrue(completed.current.finished)
            self.assertEqual(completed.id, paused.id)
            run("--load", path, "--next-deal", "--seed", 43,
                "--moves", 0, "--save", path)
            next_session = load_match(path)
            self.assertEqual(len(next_session.deals), 2)
            self.assertEqual(next_session.current.match_score, completed.score)
            self.assertEqual(next_session.current.dealer, completed.current.dealer.next)
            self.assertEqual(next_session.current.phase, Phase.DECLARATIONS)


if __name__ == "__main__":
    unittest.main()
