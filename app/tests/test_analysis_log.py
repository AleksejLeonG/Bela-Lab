"""Original estimates survive process exit, cancellation and journal failures."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bela.gameplay.batch import BatchConfig, MatchRun, run_match
from bela.interfaces.batch_cli import main
from bela.storage.analysis_log import analysis_record, append_analysis
from bela.storage.user_storage import loads_user_match
from test_batch import result
from test_monte_carlo import endgame


class AnalysisLogTests(unittest.TestCase):
    def test_full_estimates_and_replayable_original_input_are_preserved(self):
        match, _ = endgame()
        advice = {'moves': [{'card': 'H_J', 'rank': 1, 'success_probability': .75,
                             'objective_interval': [-20, 80]}],
                  'comparisons': [{'first': 'H_J', 'second': 'H_7', 'mean_difference': 4}],
                  'config': {'seed': 17}, 'status': 'complete'}
        entry = analysis_record(match, advice, selected_move={'card': 'H_J', 'bela': False})
        with tempfile.TemporaryDirectory() as folder:
            path = append_analysis(Path(folder)/'analyses.jsonl', entry)
            stored = json.loads(path.read_text())
        self.assertEqual(stored['advice'], advice)
        self.assertEqual(loads_user_match(json.dumps(stored['input'])), match)
        self.assertEqual(stored['provenance'], 'original_analysis')
        self.assertNotIn('"hands"', json.dumps(stored))

    def test_cli_streams_advice_before_a_match_result_is_returned(self):
        entry = {'advice': {'moves': [{'card': 'H_7', 'success_probability': .5}]}}
        def fake_run(config, index, **kwargs):
            kwargs['on_analysis'](entry)
            self.assertTrue((target/'analyses.jsonl').exists())
            return MatchRun(result(index), None)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'batch'
            with patch('bela.interfaces.batch_cli.run_match', side_effect=fake_run), redirect_stdout(StringIO()):
                self.assertEqual(main(['--mode','monte-carlo','--matches','1','--output',str(target)]), 0)
            self.assertEqual(json.loads((target/'analyses.jsonl').read_text()), entry)

    def test_logging_failure_preserves_checkpoint_and_stops_before_our_move(self):
        def fake_advice(match, config, **kwargs):
            legal = match.state.legal_actions
            return {'elapsed_seconds': 0, 'status': 'complete', 'completed_samples': 1,
                    'moves': [{'card': str(c), 'bela': False, 'rank': i+1}
                              for i,c in enumerate(legal)]}
        def failed_write(entry):
            raise OSError('disk full')
        with patch('bela.gameplay.batch.analyze_moves', side_effect=fake_advice):
            run = run_match(BatchConfig('monte-carlo'), 0, on_analysis=failed_write)
        self.assertEqual(run.record['status'], 'diagnostic_write_error')
        self.assertEqual(run.record['decisions'], 0)
        self.assertEqual(len(run.record['decision_estimates']), 1)
        self.assertIsNotNone(run.session)
        self.assertEqual(int(run.session.current.next_player), run.record['player'])


if __name__ == '__main__':
    unittest.main()
