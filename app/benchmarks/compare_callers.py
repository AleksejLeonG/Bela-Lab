"""Fresh paired full matches isolating six-card Monte Carlo trump calling."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from random import Random
import shutil
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from compare_search import keep_awake, write_issue
from bela.analysis.trump import POLICY, advise_trump
from bela.analysis.trump_monte_carlo import MONTE_CARLO_CALL_POLICY, calling_input
from bela.domain.cards import Suit
from bela.domain.game import Seat
from bela.gameplay.batch import BatchConfig, dealt_hands, derived_seed, run_match, trick_point_history
from bela.gameplay.calling import CallingObservation, CallingState
from bela.gameplay.session import initial_hands
from bela.gameplay.simulation import settle_play
from bela.storage.analysis_log import append_analysis
from bela.storage.persistence import load_match, save_match


MODELS = {'heuristic':POLICY, 'monte_carlo':MONTE_CARLO_CALL_POLICY}


def source_hash():
    src = Path(__file__).resolve().parents[1]/'src'/'bela'
    h = hashlib.sha256()
    for p in sorted(src.rglob('*.py')):
        h.update(p.relative_to(src).as_posix().encode()); h.update(p.read_bytes())
    return h.hexdigest()


def run(root, sets):
    root.mkdir(parents=True, exist_ok=False)
    config = {'sets':sets, 'seed':2026102511, 'models':MODELS, 'mode':'fast',
        'calling_samples':128, 'calling_seconds':2.0, 'condition_on_passes':False,
        'source_sha256':source_hash(), 'workers':1, 'model_order':'alternate_by_pair',
        'primary_metric':'paired_net_recorded_points_per_shared_deal',
        'bootstrap_resamples':12000, 'bootstrap_seed':2026102512,
        'interval':'exploratory_95_percent_match_pair_cluster_bootstrap',
        'fallback_rule':'Retain explicit baseline fallbacks and report their frequency.',
        'default_rule':'No automatic promotion; this is a small initial comparison.',
        'limits':['Shared prefixes end when either match ends; not an uncensored deal sample.',
                  'One seed schedule and simulated player model, not human-game calibration.']}
    (root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    shutil.copytree(Path(__file__).resolve().parents[1]/'src'/'bela',root/'source'/'bela',
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__),root/'benchmark.py')
    completed, started = 0, perf_counter()
    try:
        for index in range(sets):
            order = tuple(MODELS) if index % 2 == 0 else tuple(reversed(MODELS))
            for model in order:
                assert source_hash() == config['source_sha256'], 'Engine source changed during experiment'
                folder = root/model/f'match-{index}'
                folder.mkdir(parents=True,exist_ok=False)
                def journal(record):
                    append_analysis(folder/'analyses.jsonl',record)
                    a = record['advice']
                    if (a['status'] not in ('complete','time_limit','sampling_limit') or
                            a['elapsed_seconds'] > config['calling_seconds']+.25):
                        raise RuntimeError(f'Invalid calling analysis: {a["status"]}, {a["elapsed_seconds"]}')
                    assert a['completed_samples'] > 0 or a['recommendation_source']=='heuristic_fallback'
                settings = BatchConfig('fast',matches=1,seed=config['seed'],calling_policy=MODELS[model],
                    calling_samples=config['calling_samples'],calling_seconds=config['calling_seconds'])
                result = run_match(settings,index,on_analysis=journal)
                (folder/'matches.jsonl').write_text(json.dumps(result.record,allow_nan=False)+'\n')
                if result.session is not None:
                    (folder/'games').mkdir()
                    save_match(result.session,folder/'games'/f'match-{index:06d}.sim.json')
                if result.record['status'] != 'complete':
                    raise RuntimeError(f'Incomplete {model} match {index}: {result.record["status"]}')
                completed += 1
                print(f'Pair {index+1}/{sets}, {model}: score={result.record["score"]}, '
                      f'win={result.record["our_win"]}, deals={len(result.record["deals"])}, '
                      f'{result.record["elapsed_seconds"]:.2f}s',flush=True)
        assert source_hash() == config['source_sha256']
    except BaseException as error:
        write_issue(root,{'problem':repr(error),'completed_games':completed})
        raise
    finally:
        (root/'run-summary.json').write_text(json.dumps({'status':'complete' if completed==sets*2 else 'stopped',
            'completed_games':completed,'requested_games':sets*2,'elapsed_seconds':perf_counter()-started},indent=2)+'\n')
    audit(root)


def audit(root):
    config = json.loads((root/'config.json').read_text())
    assert json.loads((root/'run-summary.json').read_text())['status']=='complete'
    clusters, details, analysis = [], [], []
    positions = {m:{str(p):Counter() for p in range(1,5)} for m in MODELS}
    agreement = Counter()
    changes = {k:Counter() for k in ('same','different_suit','extra_mc_call','extra_mc_pass')}
    position_effects = {str(p):Counter() for p in range(1,5)}
    for index in range(config['sets']):
        rows = {}
        for model,policy in MODELS.items():
            folder = root/model/f'match-{index}'
            row = json.loads((folder/'matches.jsonl').read_text())
            session = load_match(folder/'games'/f'match-{index:06d}.sim.json')
            assert row['status']=='complete' and session.winner==row['winner']
            assert list(session.score)==row['score']
            assert row['mode']=='fast' and row['calling_policy']==policy
            assert row['decision_estimates']==[] and row['mc_decisions']==0
            journal_path = folder/'analyses.jsonl'
            journal = [json.loads(l) for l in journal_path.read_text().splitlines()] if journal_path.exists() else []
            assert journal==row['calling_estimates']
            used = []
            for di,(state,deal) in enumerate(zip(session.deals,row['deals'])):
                hands = dealt_hands(row['match_seed'],di)
                assert initial_hands(state)==tuple(tuple(sorted(h,key=lambda c:c.id)) for h in hands)
                assert state.finished and int(state.dealer)==deal['dealer']
                assert int(state.caller)==deal['caller'] and state.trump.value==deal['trump']
                assert deal['tricks']==trick_point_history(state)
                settled = settle_play(state)
                if not deal['belot']:
                    assert list(settled.recorded)==deal['recorded']
                    assert settled.caller_passed==deal['caller_passed']
                    assert len(state.completed_tricks)==8
                calling = CallingState(Seat(deal['dealer']))
                for bid in deal['calling']:
                    seat = calling.next_player
                    assert bid['player']==int(seat) and bid['position']==len(calling.passes)+1
                    assert bid['forced']==calling.forced
                    v = CallingObservation(seat,tuple(hands[seat][:6]),calling)
                    if model=='monte_carlo' and int(seat)==row['player']:
                        a = bid['analysis']
                        entry = next(e for e in journal if e['context']['deal_index']==di)
                        assert entry['format']=='bela-trump-analysis-record' and entry['provenance']=='original_analysis'
                        assert entry['input']==a['input']==calling_input(v) and entry['advice']==a
                        assert entry['context']['match_index']==index and entry['context']['phase']=='calling'
                        assert a['config']['samples']==config['calling_samples']
                        assert a['config']['seconds']==config['calling_seconds']
                        assert a['config']['seed']==derived_seed(row['match_seed'],'calling',di)
                        assert a['config']['condition_on_passes'] is False
                        assert a['status'] in ('complete','time_limit','sampling_limit')
                        assert a['elapsed_seconds']<=config['calling_seconds']+.25
                        assert len(a['rankings'])==(4 if calling.forced else 5)
                        assert {r['suit'] for r in a['rankings']}==({s.value for s in Suit} | (set() if calling.forced else {None}))
                        assert all(r['samples']==a['completed_samples'] for r in a['rankings'])
                        rec = a['recommendation']
                        assert rec['suit']==bid['trump'] and (rec['action']=='pass')==(bid['trump'] is None)
                        if a['completed_samples']:
                            assert a['recommendation_source']=='monte_carlo'
                            best = min(a['rankings'],key=lambda r:r['rank'])
                            assert best['suit']==rec['suit'] and best['action']==rec['action']
                            assert best['expected_point_difference']==max(r['expected_point_difference'] for r in a['rankings'])
                            assert all(0 <= r['success_probability'] <= 1 for r in a['rankings'])
                        else:
                            assert a['recommendation_source']=='heuristic_fallback'
                            base = advise_trump(v)
                            assert rec['suit']==(None if base.action is None else base.action.value)
                            assert all(r['rank'] is None and r['success_probability'] is None for r in a['rankings'])
                        used.append(entry)
                        analysis.append({'index':index,'deal':di,'position':bid['position'],
                            'seconds':a['elapsed_seconds'],'samples':a['completed_samples'],
                            'fallback':a['recommendation_source']=='heuristic_fallback','status':a['status']})
                    else:
                        base = advise_trump(v)
                        assert bid['trump']==(None if base.action is None else base.action.value)
                    calling = calling.pass_turn(seat) if bid['trump'] is None else calling.call_trump(seat,Suit(bid['trump']))
                assert int(calling.caller)==deal['caller'] and calling.trump.value==deal['trump']
            assert used==journal and len(session.deals)==len(row['deals'])
            rows[model] = row
            details.append({'index':index,'model':model,'win':row['our_win'],'score':row['score'],
                            'deals':len(row['deals']),'seconds':row['elapsed_seconds']})
        h,mc = rows['heuristic'],rows['monte_carlo']
        for field in ('match_seed','match_id','player','team','initial_dealer','profiles','evaluated_policy'):
            assert h[field]==mc[field]
        n = min(len(h['deals']),len(mc['deals']))
        nets = {m:[] for m in MODELS}
        contracts = {m:Counter() for m in MODELS}
        for di in range(n):
            assert h['deals'][di]['dealer']==mc['deals'][di]['dealer']
            own_bids = {}
            for model,row in rows.items():
                deal, team = row['deals'][di],row['team']
                nets[model].append(0 if deal['belot'] else deal['recorded'][team]-deal['recorded'][1-team])
                bid = next((b for b in deal['calling'] if b['player']==row['player']),None)
                own_bids[model] = bid
                if bid is not None:
                    p = positions[model][str(bid['position'])]
                    p['turns'] += 1; p['calls' if bid['trump'] is not None else 'passes'] += 1
                    if bid['trump'] is not None and not deal['belot']:
                        p['contracts_called'] += 1; p['contracts_made'] += int(deal['caller_passed'])
                if not deal['belot'] and deal['caller']%2==team:
                    contracts[model]['team_called'] += 1
                    contracts[model]['team_made'] += int(deal['caller_passed'])
            a,b = own_bids['heuristic'],own_bids['monte_carlo']
            delta = nets['monte_carlo'][-1]-nets['heuristic'][-1]
            assert (a is None)==(b is None)
            if a is not None:
                assert a['position']==b['position']
                agreement['decisions'] += 1
                if a['trump']==b['trump']:
                    agreement['same'] += 1; kind = 'same'
                    assert delta==0, 'Identical calling decisions changed fast-play outcomes'
                elif a['trump'] is None:
                    agreement['heuristic_pass_mc_call'] += 1; kind = 'extra_mc_call'
                elif b['trump'] is None:
                    agreement['heuristic_call_mc_pass'] += 1; kind = 'extra_mc_pass'
                else:
                    agreement['different_suit'] += 1; kind = 'different_suit'
                for group in (changes[kind],position_effects[str(a['position'])]):
                    group['decisions'] += 1; group['net_point_change'] += delta
                    group['changed'] += int(kind!='same')
                    group['mc_better'] += int(delta>0); group['heuristic_better'] += int(delta<0)
            else:
                assert delta==0, 'Outcomes changed before the evaluated player could call'
        clusters.append({'index':index,'shared_deals':n,'nets':nets,
                         'contracts':{m:dict(c) for m,c in contracts.items()}})
        print(f'Audited pair {index+1}/{config["sets"]}: {n} shared deals',flush=True)
    total = sum(c['shared_deals'] for c in clusters)
    difference = lambda cc: sum(sum(c['nets']['monte_carlo'])-sum(c['nets']['heuristic']) for c in cc)/sum(c['shared_deals'] for c in cc)
    rng = Random(config['bootstrap_seed'])
    boot = sorted(difference(rng.choices(clusters,k=len(clusters))) for _ in range(config['bootstrap_resamples']))
    models = {}
    for m in MODELS:
        pp = positions[m]
        models[m] = {'wins':sum(d['win'] for d in details if d['model']==m),'matches':config['sets'],
            'net_points_per_shared_deal':sum(sum(c['nets'][m]) for c in clusters)/total,
            'advisor_calls':sum(p['calls'] for p in pp.values()),
            'advisor_turns':sum(p['turns'] for p in pp.values()),
            'advisor_contracts_made':sum(p['contracts_made'] for p in pp.values()),
            'team_contracts_called':sum(c['contracts'][m].get('team_called',0) for c in clusters),
            'team_contracts_made':sum(c['contracts'][m].get('team_made',0) for c in clusters),
            'by_position':{p:dict(c) for p,c in pp.items()}}
    report = {'sets':config['sets'],'shared_deals':total,'models':models,
        'monte_carlo_minus_heuristic_net_points_per_shared_deal':difference(clusters),
        'exploratory_95_percent_cluster_interval':[boot[int(len(boot)*.025)],boot[int(len(boot)*.975)]],
        'calling_agreement':dict(agreement),
        'decision_breakdown':{'by_position':{p:dict(c) for p,c in position_effects.items()},
            'by_change_type':{k:dict(c) for k,c in changes.items()},
            'scope':'Descriptive breakdown, not independent significance tests.'},
        'calling_analysis':{'records_audited':len(analysis),'fallbacks':sum(a['fallback'] for a in analysis),
            'statuses':dict(Counter(a['status'] for a in analysis)),
            'mean_seconds':statistics.mean(a['seconds'] for a in analysis) if analysis else None,
            'max_seconds':max((a['seconds'] for a in analysis),default=0),
            'mean_completed_trials':statistics.mean(a['samples'] for a in analysis) if analysis else None},
        'all_game_archives_tricks_and_original_estimates_verified':True,
        'default_changed':False,'limits':config['limits'],
        'details':details,'clusters':clusters,'analysis_details':analysis}
    (root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('details','clusters','analysis_details')},indent=2))


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sets',type=int,default=20)
    p.add_argument('--audit',action='store_true')
    a = p.parse_args()
    if a.audit:
        audit(a.output)
    else:
        if not 1 <= a.sets <= 100: p.error('Sets must be between 1 and 100')
        with keep_awake(): run(a.output,a.sets)
