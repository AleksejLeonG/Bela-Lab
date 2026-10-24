"""Paired Monte Carlo deal evaluation with bounded, time-uniform uncertainty.

This estimates results under explicit rollout policies, not optimal play. All
candidates share each sampled deal and per-ply random seeds. Only completed
paired trials enter the statistics; no hidden hands leave this module.
"""

from dataclasses import asdict, dataclass
from itertools import combinations
from math import isfinite, log, sqrt
from random import Random
from time import monotonic, perf_counter

from bela import RULESET_VERSION
from bela.analysis.policies import (ANALYSIS_POLICIES, MIXED_POLICY, POLICIES,
                                    PROFILE_NAMES, announce_bela, choose_move)
from bela.analysis.lineups import StrategyLineup
from bela.analysis.sampling import HandSampler, SamplingLimit
from bela.analysis.simulation_bridge import SimulationBridge
from bela.domain.game import Phase
from bela.gameplay.simulation import observe, play_card, settle_play
from bela.gameplay.tracking import Presence


OBJECTIVES = ("point_difference", "contract_success")


@dataclass(frozen=True)
class MonteCarloConfig:
    samples: int = 128
    seconds: float = 8.0
    seed: int = 42
    policy: str = MIXED_POLICY
    objective: str = "point_difference"

    def __post_init__(self):
        if type(self.samples) is not int or not 1 <= self.samples <= 10_000:
            raise ValueError("Samples must be an integer between 1 and 10000.")
        if type(self.seconds) not in (int, float) or not isfinite(self.seconds) or not 0 <= self.seconds <= 60:
            raise ValueError("Analysis seconds must be between 0 and 60.")
        if type(self.seed) is not int or not 0 <= self.seed < 2 ** 64:
            raise ValueError("Seed must be a nonnegative 64-bit integer.")
        if self.policy not in ANALYSIS_POLICIES or self.objective not in OBJECTIVES:
            raise ValueError("Unknown analysis policy or objective.")


def confidence_interval(mean, low, high, count, family):
    """Hoeffding + union over every reported metric/pair and every n >= 1.

    delta_n = .05 / (family * n * (n+1)); sum 1/(n*(n+1)) = 1.
    Thus selecting a leader or stopping on a time budget does not turn these
    into unadjusted per-move, fixed-sample intervals. They can be quite wide.
    """
    radius = (high - low) * sqrt(log(2 * family * count * (count + 1) / .05) / (2 * count))
    return max(low, mean - radius), min(high, mean + radius)


class _Stopped(Exception):
    def __init__(self, reason):
        self.reason = reason


def analyze_moves(match, config=None, *, expected_revision=None, cancelled=None):
    """Evaluate the tracked player's legal cards without altering the match.

    Cancellation is a callable (e.g. threading.Event.is_set). Runtime includes
    preparation, sampling and rollouts. An interrupted trial is discarded for
    every candidate, keeping denominators identical and paired.
    """
    config = MonteCarloConfig() if config is None else config
    if not isinstance(config, MonteCarloConfig):
        raise ValueError("Expected MonteCarloConfig.")
    start = perf_counter()
    deadline = monotonic() + config.seconds
    bridge = SimulationBridge.from_match(match, expected_revision=expected_revision)
    tracked = match.state
    if tracked.phase != Phase.PLAYING or tracked.next_player != tracked.setup.player:
        raise ValueError("Move analysis requires your turn in an unfinished deal.")
    own = tracked.setup.player
    team = own.team
    caller_team = tracked.setup.caller.team
    legal = tracked.legal_actions
    # A future sweep adds at most 90, and at most one bela adds 20. Ordinary
    # scoring melds are already fixed by the recorded declaration contest.
    bound = 252 + sum(tracked.awarded_melds) + 20
    low, high = (-bound, bound) if config.objective == "point_difference" else (0, 1)
    family = 2 * len(legal) + len(legal) * (len(legal) - 1) // 2
    root_view = _root_view(tracked)
    rows = {str(c): {"card": str(c), "bela": announce_bela(root_view, c), "rank": None, "samples": 0,
        "expected_recorded": None, "expected_point_difference": None,
        "success_probability": None, "success_interval": None,
        "objective_mean": None, "objective_interval": None,
        "not_separated_from_leader": None} for c in legal}
    totals = {str(c): [0.0] * 4 for c in legal}  # team0, team1, success, objective
    paired = {(str(a), str(b)): 0.0 for a, b in combinations(legal, 2)}
    completed = attempts = sampled = discarded = 0
    reason = "complete"
    cancelled = cancelled or (lambda: False)

    def check():
        if cancelled():
            raise _Stopped("cancelled")
        if monotonic() >= deadline:
            raise _Stopped("time_limit")

    try:
        check()
        if len(legal) == 1:
            reason = "forced_move"
        else:
            try:
                sampler = HandSampler(tracked.evidence, seconds=min(1.0, max(0, deadline - monotonic())))
            except SamplingLimit:
                raise _Stopped("preparation_limit")
            rng = Random(config.seed)
            while completed < config.samples:
                check()
                # The latent lineup belongs to this whole hypothetical match,
                # not to a move, trick or deal. Keep trial i's assignment stable
                # even when later deals need different numbers of rejections.
                lineup = StrategyLineup.for_trial(match.id, config.seed, completed, own) if (
                    config.policy == MIXED_POLICY) else None
                if attempts >= 100_000:
                    raise _Stopped("sampling_limit")
                batch = sampler.sample(1, seed=rng.getrandbits(128),
                                       seconds=min(.1, max(0, deadline - monotonic())),
                                       max_attempts=min(1000, 100_000 - attempts))
                attempts += batch.attempts
                if not batch.deals:
                    continue
                sampled += 1
                base = bridge.resume(batch.deals[0])
                seed = rng.getrandbits(128)
                outcomes = {}
                for card in legal:
                    check()
                    state = play_card(base, own, card, announce_bela=rows[str(card)]["bela"])
                    while not state.finished:
                        check()
                        view = observe(state, state.next_player)
                        # Key randomness by the absolute next card position so
                        # one branch's tie-breaking cannot shift another's RNG.
                        ply = len(state.completed_tricks) * 4 + len(state.current_trick.cards)
                        policy = lineup.for_player(view.player) if lineup else config.policy
                        move = choose_move(view, Random((seed << 6) + ply), policy)
                        state = play_card(state, view.player, move.card, announce_bela=move.bela)
                    result = settle_play(state)
                    success = int(result.caller_passed if team == caller_team else not result.caller_passed)
                    difference = result.recorded[team] - result.recorded[1 - team]
                    value = difference if config.objective == "point_difference" else success
                    outcomes[str(card)] = (*result.recorded, success, value)
                # Commit only after every candidate in this trial has finished.
                for card, values in outcomes.items():
                    for index, value in enumerate(values):
                        totals[card][index] += value
                for pair in paired:
                    paired[pair] += outcomes[pair[0]][3] - outcomes[pair[1]][3]
                completed += 1
    except _Stopped as stopped:
        reason = stopped.reason
        discarded = sampled - completed

    pairs = []
    if completed:
        for card, total in totals.items():
            row = rows[card]
            row.update(samples=completed, expected_recorded=(total[0] / completed, total[1] / completed),
                       expected_point_difference=(total[team] - total[1 - team]) / completed,
                       success_probability=total[2] / completed, objective_mean=total[3] / completed,
                       success_interval=confidence_interval(total[2] / completed, 0, 1, completed, family),
                       objective_interval=confidence_interval(total[3] / completed, low, high, completed, family))
        ordered = sorted(rows.values(), key=lambda r: (-r["objective_mean"], r["card"]))
        for pair, total in paired.items():
            mean = total / completed
            interval = confidence_interval(mean, low - high, high - low, completed, family)
            pairs.append({"first": pair[0], "second": pair[1], "mean_difference": mean, "interval": interval})
        leader = ordered[0]["card"]
        for rank, row in enumerate(ordered, 1):
            row["rank"] = rank
            row["not_separated_from_leader"] = True
            if row["card"] != leader:
                pair = next(p for p in pairs if {p["first"], p["second"]} == {leader, row["card"]})
                lead_low = pair["interval"][0] if pair["first"] == leader else -pair["interval"][1]
                row["not_separated_from_leader"] = lead_low <= 0
    else:
        ordered = list(rows.values())
        if reason == "forced_move":
            ordered[0]["rank"] = 1

    return {"match_id": bridge.match_id, "revision": bridge.revision, "deal_number": bridge.deal_number,
            "ruleset": RULESET_VERSION, "method": "paired_monte_carlo_v2",
            "model": "uniform_consistent_initial_deals", "config": asdict(config),
            "strategy_model": {"mode": "hidden_match_lineups_v1" if config.policy == MIXED_POLICY else "uniform_policy_v1",
                               "assignment_scope": "hypothetical_match",
                               "profiles": [{"id": profile, "name": name, "intended_level": level}
                                            for level, (profile, name) in enumerate(zip(POLICIES, PROFILE_NAMES), 1)],
                               "other_player_weights": {p: 1 / len(POLICIES) for p in POLICIES} if (
                                   config.policy == MIXED_POLICY) else {config.policy: 1.0},
                               "self_policy": "tactical_v1" if config.policy == MIXED_POLICY else config.policy,
                               "real_player_profiles_known": False,
                               "value_scope": "current_deal"},
            "our_team": team, "caller_team": caller_team, "match_score": tracked.setup.match_score,
            "recorded_presence_players": sorted(int(event.player) for event in match.deals[-1].events
                                                 if isinstance(event, Presence)),
            "recorded_event_count": len(match.deals[-1].events),
            "history_assumption": "complete_play_history_from_initial_eight_cards",
            "success_definition": "make_contract" if team == caller_team else "defeat_contract",
            "completed_samples": completed, "sampling_attempts": attempts,
            "sampled_deals": sampled, "discarded_trials": discarded,
            "status": reason, "elapsed_seconds": perf_counter() - start,
            "uncertainty": "95_percent_simultaneous_time_uniform_hoeffding",
            "moves": ordered, "comparisons": pairs}


def _root_view(tracked):
    """Build the same restricted observation shape for the known root player."""
    from bela.domain.game import PlayerObservation
    return PlayerObservation(tracked.setup.player, tracked.hand, tracked.setup.trump,
                             tracked.setup.dealer, tracked.setup.caller, tracked.setup.match_score,
                             tracked.current_trick, tracked.completed_tricks, tracked.remaining_counts,
                             tracked.next_player, tracked.phase, None, (), tracked.bela_announcements, None)
