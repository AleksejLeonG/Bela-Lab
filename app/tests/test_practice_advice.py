"""Reject stale/incomplete snapshots; never guess after a history gap."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from bela.analysis.monte_carlo import MonteCarloConfig
from bela.interfaces.practice_advice import evaluate_snapshot, forced_visible_move
from bela.storage.user_storage import setup_data, event_data
from test_monte_carlo import endgame


def snapshot():
    match, _ = endgame()
    data = {"match_id": match.id, "setup": setup_data(match.initial),
            "events": [event_data(e) for e in match.deals[-1].events],
            "visible_hand": list(map(str, match.state.hand)),
            "visible_trick": [{"player": int(match.state.current_trick.seat_at(i)), "card": str(c)}
                              for i, c in enumerate(match.state.current_trick.cards)]}
    return match, data


class PracticeAdviceTests(unittest.TestCase):
    def test_valid_snapshot_returns_a_legal_local_recommendation_without_mutation(self):
        match, data = snapshot()
        before = deepcopy(data)
        result = evaluate_snapshot(data, MonteCarloConfig(samples=16, seconds=10))
        self.assertIn(result["card"], list(map(str, match.state.legal_actions)))
        self.assertEqual(result["analysis"]["completed_samples"], 16)
        self.assertEqual(result["deal_limit"], 1)
        self.assertEqual(data, before)

    def test_missing_history_or_stale_hand_is_rejected_before_analysis(self):
        _, original = snapshot()
        for change in ("hand", "trick", "history"):
            data = deepcopy(original)
            if change == "hand": data["visible_hand"] = []
            elif change == "trick": data["visible_trick"] = [{"player": 3, "card": "H_J"}]
            else: data["events"] = data["events"][:-1]
            with patch("bela.interfaces.practice_advice.analyze_moves") as analyze:
                with self.assertRaises(ValueError):
                    evaluate_snapshot(data)
                analyze.assert_not_called()

    def test_no_completed_trials_does_not_choose_a_fallback(self):
        _, data = snapshot()
        with self.assertRaisesRegex(ValueError, "No completed"):
            evaluate_snapshot(data, MonteCarloConfig(seconds=0))

    def test_only_unique_visible_move_is_allowed_after_history_loss(self):
        data = {"player": 0, "hand": ["C_K", "S_10"], "trump": "C", "leader": 3, "trick": ["S_J"]}
        result = forced_visible_move(data)
        self.assertEqual(result["card"], "S_10")
        self.assertIsNone(result["success_probability"])
        self.assertFalse(result["complete_history"])
        self.assertEqual(forced_visible_move({**data, "hand": ["C_K"], "leader": 0, "trick": []})["card"], "C_K")
        with self.assertRaisesRegex(ValueError, "More than one"):
            forced_visible_move({**data, "leader": 0, "trick": []})

    def test_visible_only_rejects_wrong_turn_duplicates_and_conflicting_cards(self):
        data = {"player": 0, "hand": ["C_K", "S_10"], "trump": "C", "leader": 3, "trick": ["S_J"]}
        for bad in ({**data, "player": 1}, {**data, "hand": ["C_K", "C_K"]},
                    {**data, "hand": ["S_J"]}, {**data, "leader": True}):
            with self.assertRaises(ValueError):
                forced_visible_move(bad)


if __name__ == "__main__":
    unittest.main()
