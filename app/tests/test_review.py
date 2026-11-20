"""Review must preserve evidence, isolate edits and persist independent notes."""
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from time import monotonic, sleep
from unittest.mock import patch

from bela.domain.cards import Card
from bela.domain.game import Seat
from bela.gameplay.tracking import AddEvent, FinishDeclarations, Play, InsertEvent, Presence, ReplaceSetup
from bela.interfaces.review import historical_match
from bela.interfaces.dashboard import Dashboard, StaleRevision
from bela.paths import EXAMPLES_ROOT
from bela.storage.analysis_log import save_analysis
from bela.storage.user_storage import _setup, save_user_match, dumps_user_match


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = Path(self.tmp.name)
        self.dashboard = Dashboard(self.storage, EXAMPLES_ROOT / "player_match.json")
        from bela.gameplay.tracking import UserMatch
        setup = _setup({"player": 0, "hand": "H_Q H_K S_9 S_10 S_A D_K C_8 C_9".split(),
                        "dealer": 3, "caller": 0, "trump": "H", "match_score": [0, 0]})
        self.before = UserMatch.start(setup).perform(AddEvent(FinishDeclarations(None)))
        self.play = Play(Seat(0), Card.parse("H_Q"), True)
        self.dashboard.match = self.before.perform(AddEvent(self.play))
        save_user_match(self.dashboard.match, self.dashboard._path(self.before.id))

    def payload(self):
        frame = self.dashboard.review()["deals"][0]["frames"][0]
        return {"expected_id": self.before.id, "expected_revision": self.dashboard.match.revision,
                "key": frame["key"], "version": 0, "flagged": True,
                "alternative": "H_K", "note": "Why spend the queen?"}

    def test_replay_shows_original_hand_and_original_advice_without_mutation(self):
        advice = {"moves": [{"card": "H_K", "rank": 1}], "status": "completed"}
        save_analysis(self.before, advice, directory=self.storage / "analysis")
        path = self.dashboard._path(self.before.id)
        raw = path.read_bytes()
        view = self.dashboard.review()
        frame = view["deals"][0]["frames"][0]
        self.assertIn("H_Q", frame["hand_before"])
        self.assertEqual(frame["played"]["card"], "H_Q")
        self.assertEqual(frame["advice"][0]["advice"], advice)
        self.assertEqual(frame["trick"]["plays"], [{"player": 0, "card": "H_Q"}])
        self.assertEqual(path.read_bytes(), raw)
        self.assertNotIn("hands", json.dumps(view))

    def test_variations_use_legal_root_moves_and_leave_archive_untouched(self):
        raw = self.dashboard._path(self.before.id).read_bytes()
        request = {key: value for key, value in self.payload().items()
                   if key in {"expected_id", "expected_revision", "key"}}
        request["seed"] = 42
        result = self.dashboard.review_variations(request)
        self.assertEqual(result, self.dashboard.review_variations(request))
        self.assertEqual({line["card"] for line in result["branches"]},
                         {str(card) for card in self.before.state.legal_actions})
        for line in result["branches"]:
            self.assertEqual(line["steps"][0]["card"], line["card"])
            self.assertEqual(len(line["steps"]), 32)
            self.assertEqual(line["steps"][-1]["hand"], [])
        self.assertEqual(self.dashboard._path(self.before.id).read_bytes(), raw)

    def test_changed_declarations_do_not_reuse_old_advice(self):
        save_analysis(self.before, {"moves": []}, directory=self.storage / "analysis")
        changed = self.before.perform(InsertEvent(0, Presence(Seat(0), False)))
        self.dashboard.match = changed.perform(AddEvent(self.play))
        self.assertEqual(self.dashboard.review()["deals"][0]["frames"][0]["advice"], [])

    def test_notes_persist_without_changing_archive_and_reject_conflicts(self):
        raw = self.dashboard._path(self.before.id).read_bytes()
        payload = self.payload()
        self.dashboard.feedback(payload)
        other = Dashboard(self.storage, EXAMPLES_ROOT / "player_match.json")
        other.match = self.dashboard.match
        note = other.review()["deals"][0]["frames"][0]["feedback"]
        self.assertEqual(note["note"], payload["note"])
        self.assertEqual(note["version"], 1)
        self.assertEqual(self.dashboard._path(self.before.id).read_bytes(), raw)
        with self.assertRaises(ValueError):
            other.feedback(payload)
        with self.assertRaises(StaleRevision):
            other.feedback({**payload, "expected_revision": 0})

    def test_completed_trick_reports_winner_and_cumulative_points(self):
        for player, card in ((1, "H_A"), (2, "H_9"), (3, "H_J")):
            self.dashboard.match = self.dashboard.match.perform(AddEvent(Play(Seat(player), Card.parse(card))))
        frames = self.dashboard.review()["deals"][0]["frames"]
        self.assertEqual(len(frames), 4)
        self.assertFalse(frames[0]["trick_complete"])
        self.assertTrue(frames[-1]["trick_complete"])
        self.assertEqual(frames[-1]["trick"]["winner"], 3)
        self.assertEqual(frames[-1]["trick"]["points"], 48)
        self.assertEqual(frames[-1]["trick_points"], (0, 48))

    def test_historical_snapshot_uses_corrected_setup_without_future_information(self):
        match = self.dashboard.match.perform(ReplaceSetup(replace(self.before.initial, caller=Seat(2))))
        match = match.perform(AddEvent(Play(Seat(1), Card.parse("H_A"))))
        self.dashboard.match = match
        frame = self.dashboard.review()["deals"][0]["frames"][0]
        snapshot = historical_match(match, frame["key"])
        self.assertEqual(snapshot.state.setup.caller, Seat(2))
        self.assertEqual(snapshot.state.current_trick.cards, ())
        self.assertIn(Card.parse("H_Q"), snapshot.state.hand)
        self.assertNotIn('"card": "H_A"', dumps_user_match(snapshot))
        self.assertEqual(len(snapshot.deals[0].events), 1)
        # Public panel and simulated input stop before the selected move.
        self.assertEqual(frame["position"]["trick"]["plays"], [])
        self.assertTrue(frame["position"]["can_analyse"])
        other = self.dashboard.review()["deals"][0]["frames"][1]
        with self.assertRaises(ValueError):
            historical_match(match, other["key"])

    def test_saved_match_review_and_feedback_do_not_replace_live_match(self):
        saved = self.dashboard.match
        self.dashboard.match = replace(saved, id="e4f14aa8-ea90-432c-b5e9-cbd89de7953e", name="Another live game")
        live = self.dashboard.match
        view = self.dashboard.review(saved.id)
        frame = view["deals"][0]["frames"][0]
        self.dashboard.feedback({"expected_id":saved.id,"expected_revision":saved.revision,
            "key":frame["key"],"version":0,"flagged":True,"alternative":"H_K","note":"Independent review"})
        self.assertEqual(self.dashboard.match, live)
        self.assertTrue(self.dashboard.review(saved.id)["deals"][0]["frames"][0]["feedback"]["flagged"])

    def test_historical_job_preserves_input_and_is_separate_from_live_advice(self):
        frame = self.dashboard.review()["deals"][0]["frames"][0]
        original = self.dashboard.match
        payload={"expected_id":original.id,"expected_revision":original.revision,"key":frame["key"],
            "config":{"samples":8,"seconds":1,"seed":42,"policy":"mixed_match_v1","objective":"point_difference"}}
        captured=[]
        def analyze(snapshot, config, **kwargs):
            captured.append(snapshot)
            return {"moves":[],"status":"complete","completed_samples":8}
        with patch("bela.interfaces.analysis_jobs.analyze_moves", side_effect=analyze):
            job=self.dashboard.review_analysis_request("/api/review/analysis/start",payload)
            deadline=monotonic()+3
            while job["state"]=="running" and monotonic()<deadline:
                sleep(.01)
                job=self.dashboard.review_analysis_view(job["id"])
        self.assertEqual(job["state"],"finished")
        self.assertEqual(job["position_key"],frame["key"])
        self.assertEqual(captured[0].state.current_trick.cards,())
        self.assertEqual(self.dashboard.match,original)
        self.assertEqual(len(self.dashboard.analysis._jobs),0)
        record=json.loads(next((self.storage/"analysis").glob("*.jsonl")).read_text())
        self.assertEqual(record["context"]["source"],"dashboard_review")
        self.assertEqual(len(record["input"]["commands"]),1)
        view=self.dashboard.review()
        self.assertEqual(view["deals"][0]["frames"][0]["advice"][0]["source"],"dashboard_review")
        self.dashboard.match=self.dashboard.match.perform(AddEvent(Play(Seat(1),Card.parse("H_A"))))
        self.assertEqual(self.dashboard.review_analysis_view(job["id"])["state"],"stale")

    def test_invalid_alternatives_and_failed_writes_preserve_notes(self):
        payload = self.payload()
        for changes in ({"alternative": "D_A"}, {"flagged": 1}, {"note": "x" * 4001},
                        {"key": "../wrong"}, {"version": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.dashboard.feedback({**payload, **changes})
        with patch("bela.interfaces.review.write_archive_text", side_effect=OSError("full")):
            with self.assertRaises(OSError):
                self.dashboard.feedback(payload)
        self.assertEqual(self.dashboard.review()["deals"][0]["frames"][0]["feedback"]["version"], 0)


if __name__ == "__main__":
    unittest.main()
