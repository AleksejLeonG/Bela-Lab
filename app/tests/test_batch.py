"""Configuration/report plumbing; match simulations are explicitly opt-in."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bela.gameplay.batch import BatchConfig, BatchSummary, MatchRun, run_match, summarize
from bela.interfaces.batch_cli import main


def result(index=0, status="complete", win=True):
    return {"match_index": index, "status": status, "our_win": win if status=="complete" else None,
            "score": [1001, 500] if status=="complete" else [0, 0], "winner": 0 if status=="complete" else None,
            "deals": [], "decisions": 12, "mc_decisions": 0, "completed_trials": 0, "analysis_seconds": 0}


class BatchUnitTests(unittest.TestCase):
    def test_learning_cost_is_reported_separately_from_evaluation(self):
        row = result()
        row.update(completed_trials=128, completed_learning_trials=128, total_completed_trials=256)
        summary = summarize([row])
        self.assertEqual(summary['completed_trials'], 128)
        self.assertEqual(summary['completed_learning_trials'], 128)
        self.assertEqual(summary['total_completed_trials'], 256)

    def test_configuration_rejects_invalid_counts_modes_and_budgets(self):
        for values in ({"mode":"unknown"}, {"matches":0}, {"matches":True}, {"seed":-1},
                       {"start_index":-1}, {"max_deals":0}, {"samples":0}, {"seconds":0},
                       {"seconds":float("nan")}, {"calling_policy":"unknown"}):
            with self.assertRaises(ValueError):
                BatchConfig(**({"mode":"fast"} | values))

    def test_dry_run_never_calls_match_runner_or_creates_results(self):
        for mode in ("fast", "monte-carlo"):
            with tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/"uncreated"
                output = StringIO()
                with patch("bela.interfaces.batch_cli.run_match") as runner, redirect_stdout(output):
                    self.assertEqual(main(["--mode",mode,"--matches","100","--output",str(target),"--dry-run"]),0)
                runner.assert_not_called()
                self.assertFalse(target.exists())
                plan = json.loads(output.getvalue())
                self.assertTrue(plan["dry_run"])
                self.assertFalse(plan["automatic_learning"])
                self.assertFalse(plan["paid_api_required"])

    def test_reports_only_completed_matches_in_win_rate(self):
        summary = summarize([result(0,win=True),result(1,win=False),result(2,"cancelled")])
        self.assertEqual(summary["complete_matches"],2)
        self.assertEqual(summary["incomplete_matches"],1)
        self.assertEqual(summary["our_win_rate"],.5)
        self.assertIsNone(summarize([])["our_win_rate"])

    def test_calling_and_contract_counters_are_distinct(self):
        row=result()
        row["deals"]=[{"calling":[{"position":1,"trump":None},{"position":2,"trump":"H"}],
                       "caller_passed":False}]
        totals=BatchSummary()
        totals.add(row)
        data=totals.result()["calling_by_position"]
        self.assertEqual(data["1"]["passes"],1)
        self.assertEqual(data["2"]["calls"],1)
        self.assertEqual(data["2"]["contracts_failed"],1)
        data["2"]["calls"]=900
        self.assertEqual(totals.result()["calling_by_position"]["2"]["calls"],1)

    def test_cli_persists_mock_results_incrementally_without_playing_cards(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"batch"
            with patch("bela.interfaces.batch_cli.run_match", side_effect=[
                    MatchRun(result(4),None),MatchRun(result(5),None)]) as runner, redirect_stdout(StringIO()):
                code = main(["--mode","fast","--matches","2","--start-index","4","--output",str(target)])
            self.assertEqual(code,0)
            self.assertEqual([c.args[1] for c in runner.call_args_list],[4,5])
            rows = [json.loads(line) for line in (target/"matches.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows),2)
            self.assertEqual(json.loads((target/"summary.json").read_text())["our_wins"],2)

    def test_cancelled_and_failed_mock_matches_stop_batch_and_do_not_count_as_losses(self):
        for response, expected_code in ((MatchRun(result(0,"cancelled"),None),130),(ValueError("test failure"),1)):
            with tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/"batch"
                setting = {"side_effect":response} if isinstance(response,Exception) else {"return_value":response}
                with patch("bela.interfaces.batch_cli.run_match",**setting) as runner, redirect_stdout(StringIO()):
                    code=main(["--mode","monte-carlo","--matches","5","--output",str(target)])
                self.assertEqual(code,expected_code)
                runner.assert_called_once()
                summary=json.loads((target/"summary.json").read_text())
                self.assertEqual(summary["complete_matches"],0)
                self.assertEqual(summary["our_losses"],0)
                self.assertIsNone(summary["our_win_rate"])

    def test_existing_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/"keep.txt"
            marker.write_text("keep")
            with patch("bela.interfaces.batch_cli.run_match") as runner, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    main(["--mode","fast","--output",folder])
            runner.assert_not_called()
            self.assertEqual(marker.read_text(),"keep")

    def test_cancel_before_dealing_does_not_generate_or_play_a_hand(self):
        with patch("bela.gameplay.batch.dealt_hands") as deal, patch("bela.gameplay.batch.play_card") as play:
            run=run_match(BatchConfig("fast"),0,cancelled=lambda:True)
        deal.assert_not_called()
        play.assert_not_called()
        self.assertEqual(run.record["status"],"cancelled")
        self.assertIsNone(run.session)


@unittest.skipUnless(os.environ.get("BELA_RUN_SIMULATIONS")=="1", "Match simulations require explicit opt-in")
class BatchSimulationTests(unittest.TestCase):
    def test_fast_matches_are_reproducible_and_never_invoke_monte_carlo(self):
        config=BatchConfig("fast",matches=1,seed=913)
        with patch("bela.gameplay.batch.analyze_moves",side_effect=AssertionError("Fast mode invoked analysis")):
            first=run_match(config,0)
            second=run_match(config,0)
        self.assertEqual(first.record["status"],"complete")
        self.assertIsNotNone(first.session.winner)
        for row in (first.record,second.record):
            row.pop("elapsed_seconds")
        self.assertEqual(first.record,second.record)
        self.assertEqual(first.session,second.session)

    def test_monte_carlo_match_completes_with_public_observations(self):
        config=BatchConfig("monte-carlo",matches=1,seed=913,samples=2,seconds=10)
        run=run_match(config,0)
        self.assertEqual(run.record["status"],"complete")
        self.assertGreater(run.record["mc_decisions"],0)
        self.assertGreater(run.record["completed_trials"],0)
        self.assertEqual(run.record["winner"],run.session.winner)


if __name__=="__main__":
    unittest.main()
