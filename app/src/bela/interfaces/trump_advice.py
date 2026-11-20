"""Strict, six-card adapter for the independent pre-deal dashboard tool."""
from bela.analysis.trump_monte_carlo import TrumpMonteCarloConfig, analyze_trumps
from bela.analysis.trump_monte_carlo import MONTE_CARLO_CALL_POLICY, calling_input
from bela.analysis.trump import POLICY, advise_trump
from bela.domain.cards import Card
from bela.domain.game import Seat
from bela.gameplay.calling import CallingObservation, CallingState


def trump_request(data):
    if (not isinstance(data, dict) or set(data) - {'player','dealer','hand','passes','config','method'}
            or not {'player','dealer','hand','passes','config'} <= set(data)):
        raise ValueError('Expected player, dealer, six cards, passes and config.')
    if any(type(data[k]) is not int or not 0 <= data[k] <= 3 for k in ('player','dealer')):
        raise ValueError('Player and dealer must be seats 0 to 3.')
    if (not isinstance(data['hand'], list) or len(data['hand']) != 6
            or any(not isinstance(c,str) for c in data['hand'])):
        raise ValueError('Select exactly six visible cards before the talon.')
    if (not isinstance(data['passes'], list) or len(data['passes']) > 3
            or any(type(s) is not int or not 0 <= s <= 3 for s in data['passes'])):
        raise ValueError('Passes must list the earlier seats in calling order.')
    cfg = data['config']
    if not isinstance(cfg, dict) or set(cfg) - {'samples','seconds','seed','condition_on_passes'}:
        raise ValueError('Unknown trump analysis setting.')
    method = data.get('method', MONTE_CARLO_CALL_POLICY)  # Existing API clients retain their explicit MC behavior.
    if method not in (POLICY, MONTE_CARLO_CALL_POLICY):
        raise ValueError('Unknown trump advice method.')
    config = TrumpMonteCarloConfig(**cfg)
    if config.samples > 1000 or config.seconds > 15:
        raise ValueError('Dashboard trump advice is limited to 1000 trials and 15 seconds.')
    state = CallingState(Seat(data['dealer']), tuple(Seat(s) for s in data['passes']))
    view = CallingObservation(Seat(data['player']), tuple(Card.parse(c) for c in data['hand']), state)
    if method == POLICY:
        advice = advise_trump(view)
        return {'method':POLICY, 'input':calling_input(view), 'config':{}, 'status':'heuristic',
            'recommendation_source':'heuristic', 'forced':advice.forced,
            'calling_position':advice.position, 'first_leader':advice.first_leader,
            'recommendation':{'action':'pass' if advice.action is None else 'call',
                              'suit':None if advice.action is None else advice.action.value},
            'rankings':[{'action':'call','suit':r.suit.value,'rank':i,'score':r.score,
                'trump_count':r.trump_count,'qualifies':r.qualifies,'components':dict(r.components)}
                for i,r in enumerate(advice.rankings,1)]}
    return analyze_trumps(view, config)
