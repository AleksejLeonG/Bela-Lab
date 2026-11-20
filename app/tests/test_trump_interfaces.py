"""Trump tool privacy and original-estimate persistence across entry points."""
from contextlib import redirect_stdout
from io import StringIO
import http.client
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from bela.analysis.trump_monte_carlo import (MONTE_CARLO_CALL_POLICY, TrumpMonteCarloConfig,
    _sample_hands)
from bela.domain.game import Seat
from bela.gameplay.batch import BatchConfig, CallingCancelled, call_deal, run_match
from bela.interfaces.analysis_jobs import AnalysisBusy
from bela.interfaces.dashboard import Dashboard, make_server
from bela.interfaces.trump_advice import trump_request
from bela.interfaces.trump_cli import main
from bela.paths import EXAMPLES_ROOT
from test_calling import observation


HAND='C_9 C_J C_K H_A S_Q D_A'
def payload():
    return {'player':0,'dealer':3,'hand':HAND.split(),'passes':[],
            'config':{'samples':4,'seconds':5,'seed':42,'condition_on_passes':False}}


class TrumpInterfaceTests(unittest.TestCase):
    def test_recommended_trump_method_is_heuristic_without_simulation(self):
        with patch('bela.interfaces.trump_advice.analyze_trumps',side_effect=AssertionError('Unexpected simulation')):
            data=trump_request(payload()|{'method':'position_control_v2','config':{}})
        self.assertEqual(data['recommendation'],{'action':'call','suit':'C'})
        self.assertEqual(data['recommendation_source'],'heuristic')
        self.assertEqual(data['method'],'position_control_v2')
        self.assertTrue(all('score' in r and 'success_probability' not in r for r in data['rankings']))

    def test_strict_adapter_rejects_extra_knowledge_and_wrong_calling_history(self):
        for data in (payload()|{'talon':['H_7','H_8']}, payload()|{'hand':HAND.split()+['H_7','H_8']},
                     payload()|{'passes':[1]},payload()|{'player':True},
                     payload()|{'config':{'seconds':16}},payload()|{'config':{'samples':1001}},
                     payload()|{'config':{'actual_opponent_profiles':[]}}):
            with self.assertRaises(ValueError):
                trump_request(data)

    def test_dashboard_http_runs_without_match_and_saves_original_input(self):
        with TemporaryDirectory() as tmp:
            dashboard=Dashboard(Path(tmp),EXAMPLES_ROOT/'player_match.json')
            server=make_server(dashboard,0)
            thread=Thread(target=server.serve_forever,daemon=True); thread.start()
            connection=http.client.HTTPConnection('127.0.0.1',server.server_address[1],timeout=10)
            try:
                connection.request('POST','/api/trump',json.dumps(payload()),{'Content-Type':'application/json'})
                response=connection.getresponse(); data=json.loads(response.read())
                self.assertEqual(response.status,200)
                self.assertEqual(data['completed_samples'],4)
                self.assertIsNone(dashboard.match)
                logs=list((Path(tmp)/'trump-analysis').glob('*.jsonl'))
                self.assertEqual(len(logs),1)
                record=json.loads(logs[0].read_text())
                self.assertEqual(record['advice'],data)
                self.assertEqual(set(record['input']),{'player','hand','dealer','passes'})
                self.assertEqual(len(record['input']['hand']),6)
                connection.request('GET','/trump.js')
                response=connection.getresponse(); self.assertEqual(response.status,200); response.read()
                connection.request('POST','/api/trump',json.dumps(payload()|{'hand':HAND.split()+['H_7','H_8']}),
                                   {'Content-Type':'application/json'})
                response=connection.getresponse(); self.assertEqual(response.status,422); response.read()
            finally:
                connection.close(); server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_dashboard_busy_and_failed_journal_release_worker(self):
        with TemporaryDirectory() as tmp:
            dashboard=Dashboard(Path(tmp),EXAMPLES_ROOT/'player_match.json')
            dashboard.trump_lock.acquire()
            with self.assertRaises(AnalysisBusy):
                dashboard.trump_advice(payload())
            dashboard.trump_lock.release()
            with patch('bela.interfaces.dashboard.append_analysis',side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):
                    dashboard.trump_advice(payload())
            self.assertFalse(dashboard.trump_lock.locked())
            self.assertIsNone(dashboard.match)

    def test_cli_json_reports_mc_values_and_forced_dealer_cannot_pass(self):
        output=StringIO()
        with redirect_stdout(output):
            main(HAND.split()+['--policy',MONTE_CARLO_CALL_POLICY,'--dealer','0','--player','0',
                               '--samples','4','--seconds','5','--json'])
        data=json.loads(output.getvalue())
        self.assertEqual(data['score_kind'],'monte_carlo_estimate')
        self.assertEqual(data['recommendation']['action'],'call')
        self.assertEqual(len(data['rankings']),4)
        self.assertEqual(data['assumed_prior_passes'],[1,2,3])

    def test_actual_hidden_cards_do_not_enter_monte_carlo_call(self):
        v=observation(HAND)
        configs=TrumpMonteCarloConfig(samples=4,seconds=5,seed=99)
        results=[]
        for seed in (9,44):
            hands=_sample_hands(v,Random(seed))
            _,bids=call_deal(hands,Seat.THREE,MONTE_CARLO_CALL_POLICY,advisor_player=Seat.ZERO,
                             calling_config=configs)
            advice=dict(bids[0]['analysis']); advice.pop('elapsed_seconds')
            results.append(advice)
        self.assertEqual(results[0],results[1])

    def test_cancelled_call_is_preserved_but_never_applied(self):
        stopped=Event(); records=[]
        def preserve(result):
            records.append(result); stopped.set()
        with self.assertRaises(CallingCancelled):
            call_deal(_sample_hands(observation(HAND),Random(9)),Seat.THREE,MONTE_CARLO_CALL_POLICY,
                advisor_player=Seat.ZERO,calling_config=TrumpMonteCarloConfig(samples=1,seconds=5),
                cancelled=stopped.is_set,on_calling=preserve)
        self.assertEqual(len(records),1)

    def test_local_single_deal_preserves_call_before_play_and_uses_only_advisor_seat(self):
        hands=_sample_hands(observation(HAND),Random(9))
        records=[]
        with patch('bela.gameplay.batch.dealt_hands',return_value=hands):
            run=run_match(BatchConfig('fast',matches=1,calling_policy=MONTE_CARLO_CALL_POLICY,
                calling_samples=2,calling_seconds=5,max_deals=1),12,on_analysis=records.append)
        self.assertEqual(len(records),1)
        self.assertEqual(run.record['calling_estimates'],records)
        self.assertEqual(records[0]['context']['phase'],'calling')
        self.assertEqual(records[0]['input']['player'],0)
        self.assertEqual(len(run.record['deals']),1)
        bid=run.record['deals'][0]['calling'][0]
        self.assertEqual(bid['analysis'],records[0]['advice'])
        self.assertEqual(bid['trump'],records[0]['advice']['recommendation']['suit'])


if __name__=='__main__':
    unittest.main()
