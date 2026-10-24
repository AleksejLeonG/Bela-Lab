"""Per-trick telemetry checked against fixed legal histories."""

import unittest

from bela.gameplay.batch import trick_point_history
from bela.gameplay.simulation import resolve_declarations, settle_play
from test_declarations import SWEEP_HANDS, finish, raw_state


class TrickPointTests(unittest.TestCase):
    def test_no_completed_trick_has_no_snapshot(self):
        self.assertEqual(trick_point_history(raw_state()), [])

    def test_running_points_and_final_bonus_are_separate_from_melds(self):
        state = finish(resolve_declarations(raw_state(score=(100, 200))))
        rows = trick_point_history(state)
        self.assertEqual(len(rows), 8)
        for index, row in enumerate(rows):
            self.assertEqual(row['trick_number'], index + 1)
            self.assertEqual(sum(row['trick_counts']), index + 1)
            self.assertEqual(len(row['plays']), 4)
            self.assertEqual(row['match_score_before_settlement'], [100, 200])
            previous = rows[index - 1]['cumulative_card_points'] if index else [0, 0]
            expected = previous.copy()
            expected[row['winning_team']] += row['card_points']
            self.assertEqual(row['cumulative_card_points'], expected)
            self.assertEqual(sum(row['last_trick_bonus']), 10 if index == 7 else 0)
        self.assertEqual(sum(rows[-1]['cumulative_card_points']), 152)
        self.assertEqual(sum(rows[-1]['cumulative_play_points']), 162)
        self.assertEqual(settle_play(state).total, 182)  # Ordinary meld adds 20 later.
        self.assertIsNot(rows[0]['cumulative_card_points'], rows[1]['cumulative_card_points'])

    def test_sweep_awarded_only_after_eighth_trick(self):
        state = finish(resolve_declarations(raw_state(SWEEP_HANDS)))
        rows = trick_point_history(state)
        self.assertTrue(all(row['sweep_bonus'] == [0, 0] for row in rows[:7]))
        self.assertEqual(rows[-1]['sweep_bonus'], [90, 0])
        self.assertEqual(rows[-1]['last_trick_bonus'], [10, 0])
        self.assertEqual(rows[-1]['cumulative_play_points'], [252, 0])
        self.assertEqual(settle_play(state).total, 292)  # Two ordinary twenties.


if __name__ == '__main__':
    unittest.main()
