"""Playable bot matches must produce complete, private-information-safe reviews."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from bela.domain.game import Seat
from bela.gameplay.bot_game import BotGame
from bela.gameplay.calling import CallingState
from bela.interfaces.dashboard import Dashboard, _trick_data, StaleRevision
from bela.interfaces.review import review_view, historical_match
from bela.paths import EXAMPLES_ROOT
from unittest.mock import patch


def start(seed=42):
    game=replace(BotGame.new("Bot test","tactical_v1"),seed=seed)
    return ready(game.call(game.public_view()["suggestion"] or "H"))


def ready(game):
    while game.calling is not None:
        game=game.call(game.public_view()["suggestion"] or "H") if game.calling.next_player==Seat.ZERO else game.step()
    return game.step() if game.declarations_pending else game


def finish_deal(game):
    while not game.session.current.finished:
        if game.awaiting_trick or game.session.current.next_player!=Seat.ZERO:
            game=game.step()
        else:
            game=game.play(str(game.tracked.state.legal_actions[0]))
    return game


class BotGameTests(unittest.TestCase):
    def test_complete_match_reaches_winner_with_consistent_review_scores(self):
        game=start(17)
        for _ in range(50):
            game=finish_deal(game)
            self.assertEqual(game.tracked.state.score,game.session.score)
            self.assertEqual(game.tracked.state.winner,game.session.winner)
            if game.session.winner is not None:break
            game=ready(game.next_deal())
        self.assertIsNotNone(game.session.winner)
        self.assertGreaterEqual(max(game.session.score),1000)
        self.assertTrue(all(len(d.completed_tricks)==8 for d in game.session.deals))

    def test_six_card_calling_forced_dealer_and_private_view(self):
        game=BotGame.new()
        public=game.public_view()
        self.assertEqual(len(public["hand"]),6)
        self.assertIsNone(game.tracked)
        self.assertNotIn("seed",public)
        self.assertNotIn("profiles",public)
        forced=replace(game,calling=CallingState(Seat.ZERO,(Seat.ONE,Seat.TWO,Seat.THREE)))
        with self.assertRaises(ValueError):forced.call(None)
        called=game.call("H")
        self.assertIsNone(called.tracked)
        self.assertEqual(called.public_view()["caller"],0)
        self.assertEqual(BotGame.loads(called.dumps()).calling,called.calling)
        called=called.step()
        self.assertTrue(called.declarations_pending)
        with self.assertRaises(ValueError):called.play(str(called.tracked.state.legal_actions[0]))
        self.assertEqual(len(called.tracked.initial.hand),8)

    def test_deal_scores_replay_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            game=finish_deal(start())
            self.assertEqual(len(game.session.current.completed_tricks),8)
            self.assertEqual(game.tracked.state.score,game.session.score)
            self.assertEqual(game.tracked.state.result.recorded,game.session.score)
            restored=BotGame.loads(game.dumps())
            self.assertEqual(restored.tracked,game.tracked)
            self.assertEqual(restored.session,game.session)
            review=review_view(game.tracked,Path(tmp),_trick_data)
            self.assertEqual(len(review["deals"][0]["frames"]),32)
            for frame in review["deals"][0]["frames"]:
                if frame["position"]["can_analyse"]:
                    historic=historical_match(game.tracked,frame["key"])
                    self.assertEqual(len(historic.state.hand),len(frame["hand_before"]))
                    self.assertLess(len(historic.deals[-1].events),len(game.tracked.deals[-1].events))
            next_game=game.next_deal()
            self.assertEqual(next_game.public_view()["calling_player"],1)
            self.assertEqual(next_game.public_view()["position"],1)
            next_game=ready(next_game)
            self.assertEqual(len(next_game.session.deals),2)
            self.assertEqual(next_game.session.current.dealer,Seat.ZERO)
            next_game=finish_deal(next_game)
            self.assertEqual(next_game.tracked.state.score,next_game.session.score)

    def test_illegal_move_and_wrong_actor_rejected(self):
        game=start()
        with self.assertRaises(ValueError):game.play("H_2")
        played=game.play(str(game.tracked.state.legal_actions[0]))
        with self.assertRaises(ValueError):played.play(str(next(iter(played.session.current.hands[0]))))

    def test_dashboard_resume_switch_and_stale_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            d=Dashboard(path,EXAMPLES_ROOT/"player_match.json")
            snapshot=d.bot_request("/api/bot/new",{"expected_id":None,"expected_revision":0,"name":"Practice","profile":"mixed"})
            self.assertEqual(snapshot["mode"],"bots")
            b=snapshot["bot"]
            with self.assertRaises(StaleRevision):
                d.bot_request("/api/bot/call",{"expected_id":b["id"],"expected_revision":99,"suit":"H"})
            snapshot=d.bot_request("/api/bot/call",{"expected_id":b["id"],"expected_revision":b["revision"],"suit":"H"})
            self.assertIsNone(snapshot["match"])
            b=snapshot["bot"]
            snapshot=d.bot_request("/api/bot/step",{"expected_id":b["id"],"expected_revision":b["revision"]})
            self.assertEqual(len(snapshot["match"]["hand"]),8)
            with self.assertRaises(ValueError):
                d.mutate("/api/command",{"expected_id":d.match.id,"expected_revision":d.match.revision,"command":{}})
            restored=Dashboard(path,EXAMPLES_ROOT/"player_match.json")
            self.assertEqual(restored.bot_game,d.bot_game)
            self.assertEqual(restored.mode,"bots")
            d.change_mode({"expected_id":d.match.id,"expected_revision":d.match.revision,"mode":"manual"})
            self.assertIsNone(d.match)
            d.change_mode({"expected_id":None,"expected_revision":0,"mode":"bots"})
            self.assertEqual(d.match,restored.match)
            # Public archive cannot contain the private simulator checkpoint.
            archive=json.loads(d._path(d.match.id).read_text())
            self.assertNotIn("session",archive)
            self.assertNotIn("seed",archive)
            self.assertEqual(d.saved()[0]["mode"],"bots")

    def test_failed_private_save_rolls_back_public_archive_and_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Dashboard(Path(tmp),EXAMPLES_ROOT/"player_match.json")
            game=start()
            d._commit_bot(game)
            before={p:p.read_bytes() for p in (d._path(game.id),d._bot_path(game.id),d.storage/"active.json")}
            from bela.interfaces.dashboard import write_archive_text
            failed=False
            def fail_once(path,text):
                nonlocal failed
                if path==d._bot_path(game.id) and not failed:
                    failed=True
                    raise OSError("disk full")
                return write_archive_text(path,text)
            with patch("bela.interfaces.dashboard.write_archive_text",side_effect=fail_once):
                with self.assertRaises(OSError):d._commit_bot(game.play(str(game.tracked.state.legal_actions[0])))
            self.assertEqual(d.bot_game,game)
            for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
