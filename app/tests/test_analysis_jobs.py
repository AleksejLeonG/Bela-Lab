import json
from pathlib import Path
import tempfile
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from bela.analysis.monte_carlo import MonteCarloConfig
from bela.gameplay.tracking import AddEvent, FinishDeclarations, Presence, Seat
from bela.interfaces.analysis_jobs import AnalysisBusy, AnalysisJobs, interactive_config
from bela.interfaces.dashboard import Dashboard, StaleRevision
from bela.paths import EXAMPLES_ROOT
from test_sampling import match_with


def wait_for(manager, job_id, source):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        result = manager.view(job_id, source)
        if result["state"] in ("finished", "failed", "stale"):
            return result
        sleep(.005)
    raise AssertionError("Analysis worker did not finish.")


class AnalysisJobsTests(unittest.TestCase):
    def test_one_worker_cancellation_and_stale_result_suppression(self):
        match = match_with(FinishDeclarations(None))
        source = (match.id, match.revision, 1)
        manager = AnalysisJobs()
        entered, release = Event(), Event()
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {"status": "cancelled" if kwargs["cancelled"]() else "complete"}
        with patch("bela.interfaces.analysis_jobs.analyze_moves", side_effect=blocked):
            job_id = manager.start(match, MonteCarloConfig())
            self.assertTrue(entered.wait(2))
            try:
                with self.assertRaises(AnalysisBusy):
                    manager.start(match, MonteCarloConfig())
                manager.invalidate()
                self.assertEqual(manager.view(job_id, source)["state"], "cancelling")
                self.assertIsNone(manager.view(job_id, (match.id, match.revision + 1, 1))["result"])
            finally:
                release.set()
            result = wait_for(manager, job_id, source)
        self.assertEqual(result["result"]["status"], "cancelled")
        self.assertEqual(manager.view(job_id, ("other", 1, 1))["state"], "stale")

    def test_retention_is_bounded_and_worker_errors_are_reported(self):
        match = match_with(FinishDeclarations(None))
        source = (match.id, match.revision, 1)
        manager = AnalysisJobs()
        ids = []
        with patch("bela.interfaces.analysis_jobs.analyze_moves", return_value={"status": "complete"}):
            for _ in range(10):
                ids.append(manager.start(match, MonteCarloConfig()))
                wait_for(manager, ids[-1], source)
        with self.assertRaises(ValueError):
            manager.view(ids[0], source)
        self.assertEqual(len(manager._jobs), 8)
        with patch("bela.interfaces.analysis_jobs.analyze_moves", side_effect=ValueError("Invalid analysis state.")):
            job_id = manager.start(match, MonteCarloConfig())
            result = wait_for(manager, job_id, source)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["error"], "Invalid analysis state.")

    def test_analysis_requests_never_change_game_archives(self):
        with tempfile.TemporaryDirectory() as folder:
            dashboard = Dashboard(Path(folder), EXAMPLES_ROOT / "player_match.json")
            dashboard.mutate("/api/demo", {"expected_id": None, "expected_revision": 0})
            match = dashboard.match
            path = dashboard._path(match.id)
            before = path.read_bytes()
            payload = {"expected_id": match.id, "expected_revision": match.revision,
                       "config": {"samples": 4, "seconds": 1, "seed": 42,
                                  "policy": "mixed_match_v1", "objective": "point_difference"}}
            job = dashboard.analysis_request("/api/analysis/start", payload)
            result = wait_for(dashboard.analysis, job["id"], (match.id, match.revision, len(match.deals)))
            self.assertEqual(result["result"]["status"], "forced_move")
            self.assertEqual(result["result"]["strategy_model"]["mode"], "hidden_match_lineups_v1")
            self.assertFalse(result["result"]["strategy_model"]["real_player_profiles_known"])
            self.assertIs(dashboard.match, match)
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn('"hands"', json.dumps(result))
            with self.assertRaises(StaleRevision):
                dashboard.analysis_request("/api/analysis/start", {**payload, "expected_revision": 0})
            self.assertEqual(dashboard.analysis_view(job["id"]), result)

    def test_invalid_inputs_do_not_launch_workers(self):
        manager = AnalysisJobs()
        with self.assertRaises(ValueError):
            manager.start(match_with(), MonteCarloConfig())
        config = {"samples": 128, "seconds": 8, "seed": 42,
                  "policy": "simple_v1", "objective": "point_difference"}
        for value in ({}, {**config, "samples": 1001}, {**config, "seconds": 16},
                      {**config, "unknown": 1}):
            with self.assertRaises(ValueError):
                interactive_config(value)
        with self.assertRaises(ValueError):
            manager.cancel("missing")
