"""Paired pre-talon calling estimates under explicit, inexpensive play policies."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import combinations
from math import isfinite
from random import Random
from time import monotonic, perf_counter

from bela import RULESET_VERSION
from bela.analysis.learned_policy import COMPETENT_FALLBACK_PROFILES, fallback_profile
from bela.analysis.lineups import StrategyLineup
from bela.analysis.monte_carlo import confidence_interval
from bela.analysis.policies import POLICIES, _choose_from_legal
from bela.analysis.rollout_random import TrialRandomness
from bela.analysis.trump import CALLING_POLICIES, POLICY, advise_trump
from bela.domain.cards import Suit, deck
from bela.domain.game import Seat
from bela.domain.melds import QUAD_POINTS
from bela.gameplay.calling import CallingObservation, CallingState
from bela.gameplay.simulation import (_prepare_turn, _play_prepared, declare_belot,
    resolve_declarations, settle_play, start_play)
from bela.rules.melds import has_belot


MONTE_CARLO_CALL_POLICY = 'monte_carlo_call_v1'
LOCAL_CALLING_POLICIES = (*CALLING_POLICIES, MONTE_CARLO_CALL_POLICY)
# At most six scoring quads globally and two maximal runs per eight-card hand.
# Each run is worth at most 100; include sweep and Bela. Deliberately loose.
POINT_BOUND = 252 + sum(QUAD_POINTS.values()) + 4 * 2 * 100 + 20


@dataclass(frozen=True)
class TrumpMonteCarloConfig:
    samples: int = 128
    seconds: float = 8.0
    seed: int = 42
    condition_on_passes: bool = False
    max_sampling_attempts: int = 100_000

    def __post_init__(self):
        if type(self.samples) is not int or not 1 <= self.samples <= 10_000:
            raise ValueError('Samples must be an integer between 1 and 10000.')
        if type(self.seconds) not in (int, float) or not isfinite(self.seconds) or not 0 <= self.seconds <= 60:
            raise ValueError('Analysis seconds must be between 0 and 60.')
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise ValueError('Seed must be a nonnegative 64-bit integer.')
        if type(self.condition_on_passes) is not bool:
            raise ValueError('Pass conditioning must be a boolean.')
        if type(self.max_sampling_attempts) is not int or not 1 <= self.max_sampling_attempts <= 1_000_000:
            raise ValueError('Sampling attempts must be between 1 and 1000000.')


def calling_input(view):
    return {'player': int(view.player), 'hand': [str(c) for c in sorted(view.hand, key=lambda c:c.id)],
            'dealer': int(view.state.dealer), 'passes': [int(s) for s in view.state.passes]}


def _sample_hands(view, rng):
    """Uniform allocation of the 26 unknown cards to 18 initial and 8 talon slots."""
    unknown = [c for c in deck() if c not in view.hand]
    rng.shuffle(unknown)
    sixes, offset = [], 0
    for seat in Seat:
        if seat == view.player:
            sixes.append(tuple(sorted(view.hand, key=lambda c:c.id)))
        else:
            sixes.append(tuple(unknown[offset:offset+6]))
            offset += 6
    return tuple(sixes[s] + tuple(unknown[18+2*s:20+2*s]) for s in range(4))


def _matches_passes(view, hands):
    state = CallingState(view.state.dealer)
    for seat in view.state.passes:
        if advise_trump(CallingObservation(seat, hands[seat][:6], state)).action is not None:
            return False
        state = state.pass_turn(seat)
    return True


def _finish_calling(view, hands, suit):
    if suit is not None:
        return view.state.call_trump(view.player, suit)
    state = view.state.pass_turn(view.player)
    while state.next_player is not None:
        seat = state.next_player
        advice = advise_trump(CallingObservation(seat, hands[seat][:6], state))
        state = state.pass_turn(seat) if advice.action is None else state.call_trump(seat, advice.action)
    return state


def _rollout(hands, calling, own, lineup, self_policy, randomness, check):
    check()
    state = start_play(hands, trump=calling.trump, dealer=calling.dealer, caller=calling.caller)
    belot = next((Seat((int(calling.dealer)+i) % 4) for i in range(1,5)
                  if has_belot(hands[(int(calling.dealer)+i) % 4])), None)
    state = declare_belot(state, belot) if belot is not None else resolve_declarations(state)
    while not state.finished:
        check()
        turn = _prepare_turn(state)
        actor = turn.view.player
        policy = self_policy if actor == own else lineup.for_player(actor)
        ply = len(state.completed_tricks)*4 + len(state.current_trick.cards)
        move = _choose_from_legal(turn.view, randomness.at(ply), policy, turn.legal)
        state = _play_prepared(state, turn, move.card, announce_bela=move.bela)
    check()
    if belot is not None:
        # Belot ends the match without a point award. Same event for all actions
        # in this paired world; do not fabricate a 1000-point deal reward.
        return ((0, 0), int(belot.team == own.team), None, int(belot.team == own.team))
    result = settle_play(state)
    success = result.caller_passed if result.caller_team == own.team else not result.caller_passed
    return result.recorded, int(success), int(result.caller_passed), None


class _Stopped(Exception):
    pass


def analyze_trumps(view, config=None, *, cancelled=None):
    """Rank four calls and, unless forced, pass. Never accepts an eight-card hand.

    Every completed trial shares cards, styles and per-ply draws across actions.
    Partial trials update nothing. Earlier passes are uninformative by default;
    optional rejection conditioning explicitly assumes position_control_v2.
    Later calls after our pass always use that baseline, never recursive MC.
    """
    if not isinstance(view, CallingObservation):
        raise ValueError('Trump analysis requires a six-card CallingObservation.')
    config = TrumpMonteCarloConfig() if config is None else config
    if not isinstance(config, TrumpMonteCarloConfig):
        raise ValueError('Expected TrumpMonteCarloConfig.')
    started, deadline = perf_counter(), monotonic() + config.seconds
    cancelled = cancelled or (lambda: False)
    baseline = advise_trump(view)
    inp = calling_input(view)
    identity = repr((inp['player'], tuple(inp['hand']), inp['dealer'], tuple(inp['passes'])))
    card_seed = int.from_bytes(sha256(f'trump-cards-v1:{config.seed}:{identity}'.encode()).digest()[:8], 'big')
    cards_rng = Random(card_seed)
    actions = tuple(Suit) + (() if view.state.forced else (None,))
    label = lambda s: s.value if s is not None else 'pass'
    totals = {s: [0]*9 for s in actions}
    pairs = {p: 0 for p in combinations(actions, 2)}
    completed = attempts = accepted = 0
    reason = 'complete'

    def check():
        if cancelled():
            raise _Stopped('cancelled')
        if monotonic() >= deadline:
            raise _Stopped('time_limit')

    try:
        while completed < config.samples:
            check()
            if attempts >= config.max_sampling_attempts:
                raise _Stopped('sampling_limit')
            attempts += 1
            hands = _sample_hands(view, cards_rng)
            if config.condition_on_passes and not _matches_passes(view, hands):
                continue
            accepted += 1
            lineup = StrategyLineup.for_trial('trump-v1:'+identity, config.seed, completed, view.player)
            own_style = fallback_profile('trump-v1:'+identity, config.seed, completed)
            random_seed = int.from_bytes(sha256(f'trump-rollout-v1:{config.seed}:{identity}:{completed}'.encode()).digest()[:8], 'big')
            randomness = TrialRandomness(random_seed)
            outcomes = {}
            for suit in actions:
                check()
                calling = _finish_calling(view, hands, suit)
                recorded, success, made, belot_win = _rollout(
                    hands, calling, view.player, lineup, own_style, randomness, check)
                difference = recorded[view.player.team] - recorded[1-view.player.team]
                outcomes[suit] = (recorded, success, made, belot_win, difference, calling.caller)
            check()
            # Only a complete paired set enters any denominator or comparison.
            for suit, (recorded, success, made, belot_win, difference, caller) in outcomes.items():
                t = totals[suit]
                t[0] += recorded[0]; t[1] += recorded[1]; t[2] += success; t[3] += difference
                t[4] += int(made is not None); t[5] += made or 0
                t[6] += int(belot_win is not None); t[7] += belot_win or 0
                t[8] += int(caller.team == view.player.team)
            for a,b in pairs:
                pairs[a,b] += outcomes[a][4] - outcomes[b][4]
            completed += 1
    except _Stopped as error:
        reason = str(error)

    family = 2*len(actions) + len(pairs)
    rows = []
    for suit in actions:
        t = totals[suit]
        rows.append({'action': 'pass' if suit is None else 'call', 'suit': None if suit is None else suit.value,
            'rank': None, 'samples': completed,
            'expected_recorded': [t[0]/completed,t[1]/completed] if completed else None,
            'expected_point_difference': t[3]/completed if completed else None,
            'success_probability': t[2]/completed if completed else None,
            'success_interval': confidence_interval(t[2]/completed,0,1,completed,family) if completed else None,
            'objective_interval': confidence_interval(t[3]/completed,-POINT_BOUND,POINT_BOUND,completed,family) if completed else None,
            'calling_team_make_probability': t[5]/t[4] if t[4] else None,
            'our_team_calls_probability': t[8]/completed if completed else None,
            'belot_probability': t[6]/completed if completed else None,
            'our_belot_win_probability': t[7]/completed if completed else None,
            'not_separated_from_leader': None})
    comparisons = []
    if completed:
        rows.sort(key=lambda r: (-r['expected_point_difference'], r['suit'] or 'pass'))
        for pair,total in pairs.items():
            mean = total/completed
            comparisons.append({'first':label(pair[0]), 'second':label(pair[1]), 'mean_difference':mean,
                'interval':confidence_interval(mean,-2*POINT_BOUND,2*POINT_BOUND,completed,family)})
        leader = rows[0]['suit'] or 'pass'
        for rank,row in enumerate(rows,1):
            row['rank'] = rank
            row['not_separated_from_leader'] = True
            key = row['suit'] or 'pass'
            if key != leader:
                pair = next(p for p in comparisons if {p['first'],p['second']} == {leader,key})
                lower = pair['interval'][0] if pair['first']==leader else -pair['interval'][1]
                row['not_separated_from_leader'] = lower <= 0
        chosen = rows[0]
        recommendation = {'action': chosen['action'], 'suit': chosen['suit']}
    else:
        recommendation = {'action':'pass' if baseline.action is None else 'call',
                          'suit':None if baseline.action is None else baseline.action.value}
    return {'method':MONTE_CARLO_CALL_POLICY, 'ruleset':RULESET_VERSION,
        'config':asdict(config), 'input':inp, 'forced':view.state.forced,
        'calling_position':len(view.state.passes)+1, 'first_leader':baseline.first_leader,
        'status':reason, 'completed_samples':completed, 'sampling_attempts':attempts,
        'accepted_deals':accepted, 'discarded_trials':accepted-completed,
        'elapsed_seconds':perf_counter()-started, 'rankings':rows, 'comparisons':comparisons,
        'recommendation':recommendation, 'recommendation_source':'monte_carlo' if completed else 'heuristic_fallback',
        'baseline_recommendation':{'action':'pass' if baseline.action is None else 'call',
                                   'suit':None if baseline.action is None else baseline.action.value},
        'objective':'point_difference', 'value_scope':'current_deal',
        'success_definition':'our_side_makes_or_defeats_contract_or_wins_terminal_belot',
        'uncertainty':'95_percent_simultaneous_time_uniform_hoeffding',
        'point_bound':POINT_BOUND,
        'model':{'hands':'uniform_initial_sixes_and_unseen_talons',
            'past_pass_inference':POLICY if config.condition_on_passes else 'none',
            'future_calling_policy':POLICY, 'other_player_weights':{p:1/len(POLICIES) for p in POLICIES},
            'self_profile_weights':{p:1/len(COMPETENT_FALLBACK_PROFILES) for p in COMPETENT_FALLBACK_PROFILES},
            'profile_assignment':'fixed_per_trial_shared_across_actions', 'nested_monte_carlo':False,
            'declarations':'truthful_simulated_winning_team_reveals',
            'belot_points':'zero_no_invented_deal_award'}}
