"""Paired Monte Carlo deal evaluation with bounded, time-uniform uncertainty.

This estimates results under explicit rollout policies, not optimal play. All
candidates share each sampled deal and per-ply random seeds. Only completed
paired trials enter the statistics; no hidden hands leave this module.
"""

from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
from math import isfinite, log, sqrt
from random import Random
from time import monotonic, perf_counter

from bela import RULESET_VERSION
from bela.analysis import exact_endgame
from bela.analysis.auction import AuctionEvidence
from bela.analysis.policies import (ANALYSIS_POLICIES, MIXED_POLICY, POLICIES,
                                    PROFILE_NAMES, announce_bela, _choose_from_legal)
from bela.analysis.lineups import StrategyLineup
from bela.analysis.self_search import (SELF_POLICIES, SELF_SEARCH, SHARED_SELF_SEARCH,
                                       BELA_CREDIT_SELF_SEARCH, LEARN_EVALUATE_SELF_SEARCH,
                                       LEARN_EVALUATE_POLICIES, COMPETENT_LEARN_EVALUATE_SELF_SEARCH,
                                       DIRECT_COMPETENT_SELF_POLICY,
                                       SelfSearch, SharedSelfSearch,
                                       BelaCreditSelfSearch)
from bela.analysis.learned_policy import (COMPETENT_FALLBACK_PROFILES,
                                         FrozenSelfPolicy, learning_seed, fallback_profile)
from bela.analysis.rollout_random import TrialRandomness
from bela.analysis.sampling import HandSampler, SamplingLimit
from bela.analysis.simulation_bridge import SimulationBridge
from bela.domain.game import Phase
from bela.gameplay.simulation import _prepare_turn, _play_prepared, settle_play
from bela.gameplay.tracking import Presence
from bela.rules.play import trick_winner
from bela.rules.scoring import match_winner


OBJECTIVES = ("point_difference", "contract_success", "match_outcome")


def settled_match_outcome(score, recorded, team):
    """Immediate match result after this deal; future deals are not rolled out."""
    winner=match_winner(tuple(score[t]+recorded[t] for t in (0,1)))
    return int(winner==team),int(winner==1-team),int(winner is None)


@dataclass(frozen=True)
class MonteCarloConfig:
    samples: int = 128
    seconds: float = 8.0
    seed: int = 42
    policy: str = MIXED_POLICY
    objective: str = "point_difference"
    self_policy: str = SELF_SEARCH
    learning_samples: int | None = None
    exact_endgame: bool = False
    auction_weighting: bool = False

    def __post_init__(self):
        if type(self.exact_endgame) is not bool:
            raise ValueError("The exact endgame setting must be a boolean.")
        if type(self.auction_weighting) is not bool:
            raise ValueError("The auction weighting setting must be a boolean.")
        if self.auction_weighting and self.policy == MIXED_POLICY and self.self_policy != DIRECT_COMPETENT_SELF_POLICY:
            raise ValueError("Auction weighting requires fixed continuation policies.")
        if type(self.samples) is not int or not 1 <= self.samples <= 10_000:
            raise ValueError("Samples must be an integer between 1 and 10000.")
        if type(self.seconds) not in (int, float) or not isfinite(self.seconds) or not 0 <= self.seconds <= 60:
            raise ValueError("Analysis seconds must be between 0 and 60.")
        if type(self.seed) is not int or not 0 <= self.seed < 2 ** 64:
            raise ValueError("Seed must be a nonnegative 64-bit integer.")
        if self.policy not in ANALYSIS_POLICIES or self.objective not in OBJECTIVES:
            raise ValueError("Unknown analysis policy or objective.")
        if self.self_policy not in SELF_POLICIES:
            raise ValueError("Unknown self continuation policy.")
        if self.learning_samples is not None:
            if type(self.learning_samples) is not int or not 1 <= self.learning_samples <= 10_000:
                raise ValueError("Learning samples must be an integer between 1 and 10000.")
            if self.policy != MIXED_POLICY or self.self_policy not in LEARN_EVALUATE_POLICIES:
                raise ValueError("Learning samples require the learn-then-evaluate mixed model.")


def confidence_interval(mean, low, high, count, family, *, weight_sum=None):
    """Hoeffding + union over every reported metric/pair and every n >= 1.

    delta_n = .05 / (family * n * (n+1)); sum 1/(n*(n+1)) = 1.
    Thus selecting a leader or stopping on a time budget does not turn these
    into unadjusted per-move, fixed-sample intervals. They can be quite wide.
    """
    radius = (high - low) * sqrt(log(2 * family * count * (count + 1) / .05) / (2 * count))
    if weight_sum is not None:
        # For true mean m, W*(X-m) is centered and its range is no wider
        # than that of X because 0 < W <= 1. Divide the sum bound by sum(W).
        radius *= count / weight_sum
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
    low, high = (-bound, bound) if config.objective == "point_difference" else (-1,1) if config.objective == "match_outcome" else (0, 1)
    family = 8 * len(legal) + len(legal) * (len(legal) - 1) // 2
    root_view = _root_view(tracked)
    rows = {str(c): {"card": str(c), "bela": announce_bela(root_view, c), "rank": None, "samples": 0,
        "expected_recorded": None, "expected_point_difference": None,
        "success_probability": None, "success_interval": None,
        "sample_best_share": None, "sample_best_interval": None,
        "our_sweep_probability": None, "opponent_sweep_probability": None,
        "our_sweep_interval": None, "opponent_sweep_interval": None,
        "our_match_win_probability": None, "opponent_match_win_probability": None, "match_continue_probability": None,
        "our_match_win_interval": None, "opponent_match_win_interval": None, "match_continue_interval": None,
        "objective_mean": None, "objective_interval": None,
        "not_separated_from_leader": None} for c in legal}
    opening_lead = not tracked.completed_tricks and not tracked.current_trick.cards
    # Team scores, contract, objective, sweeps, match outcomes, opening trick.
    totals = {str(c): [0.0] * (12 if opening_lead else 9) for c in legal}
    best_counts = {str(c): 0.0 for c in legal}
    paired = {(str(a), str(b)): 0.0 for a, b in combinations(legal, 2)}
    completed = attempts = sampled = discarded = 0
    exact_layouts = 0
    total_weight = sum_squared_weights = 0.0
    exact_weight = 0
    proven_ties = set()
    learned = 0
    split = config.policy == MIXED_POLICY and config.self_policy in LEARN_EVALUATE_POLICIES
    direct = config.policy == MIXED_POLICY and config.self_policy == DIRECT_COMPETENT_SELF_POLICY
    competent_fallback = split and config.self_policy == COMPETENT_LEARN_EVALUATE_SELF_SEARCH
    requested_learning = (config.learning_samples or config.samples) if split else 0
    evaluator = None
    phase = "preparation"
    reason = "complete"
    search = None
    if config.policy == MIXED_POLICY:
        if config.self_policy == SELF_SEARCH:
            search = SelfSearch()
        elif config.self_policy == SHARED_SELF_SEARCH:
            search = SharedSelfSearch()
        elif config.self_policy == BELA_CREDIT_SELF_SEARCH:
            search = BelaCreditSelfSearch()
        elif split:
            search = SelfSearch()
    cancelled = cancelled or (lambda: False)
    auction = AuctionEvidence(tracked.setup) if config.auction_weighting else None
    auction_rng = Random(config.seed ^ 0xACE5C0DE) if auction is not None else None

    def check():
        if cancelled():
            raise _Stopped("cancelled")
        if monotonic() >= deadline:
            raise _Stopped("time_limit")

    def outcome(state):
        result = settle_play(state)
        success = int(result.caller_passed if team == caller_team else not result.caller_passed)
        difference = result.recorded[team] - result.recorded[1 - team]
        win_now, lose_now, carry_on = settled_match_outcome(tracked.setup.match_score, result.recorded, team)
        value = (difference if config.objective == "point_difference" else
                 win_now - lose_now if config.objective == "match_outcome" else success)
        our_sweep = int(not tracked.trick_counts[1-team] and all(
            trick_winner(trick, state.trump).team == team for trick in state.completed_tricks))
        their_sweep = int(not tracked.trick_counts[team] and all(
            trick_winner(trick, state.trump).team == 1-team for trick in state.completed_tricks))
        outcomes = (*result.recorded, success, value, our_sweep, their_sweep, win_now, lose_now, carry_on)
        if opening_lead:
            winner = trick_winner(state.completed_tricks[0], state.trump)
            outcomes += (int(winner == own), int(winner != own and winner.team == team), int(winner.team != team))
        return outcomes

    try:
        check()
        if len(legal) == 1:
            reason = "forced_move"
        else:
            try:
                sampler = HandSampler(tracked.evidence, seconds=min(1.0, max(0, deadline - monotonic())))
            except SamplingLimit:
                raise _Stopped("preparation_limit")
            remaining = sum(tracked.remaining_counts)
            if config.exact_endgame and (direct or config.policy != MIXED_POLICY) and remaining <= exact_endgame.MAX_CARDS:
                exact = exact_endgame.evaluate_endgame(
                    bridge, sampler, legal, own, config.policy, outcome, check=check,
                    auction=auction,
                    seconds=min(exact_endgame.MAX_SECONDS, max(0, deadline - monotonic()) / 4))
                if exact is not None:
                    exact_layouts, exact_weight, totals, proven_ties = exact
                    reason = "exact_endgame"
            train_seed = learning_seed(config.seed, match.id) if split else None
            learning_deadline = (monotonic() + max(0, deadline - monotonic()) / 2) if split else None
            phase = "exact_endgame" if exact_layouts else "learning" if split else "evaluation"
            rng = Random(train_seed if split else config.seed)
            while not exact_layouts and completed < config.samples:
                check()
                if split and evaluator is None and (learned == requested_learning or monotonic() >= learning_deadline):
                    evaluator = (FrozenSelfPolicy(search.nodes, fallback_mode='competent_mix_v1')
                                 if competent_fallback else FrozenSelfPolicy(search.nodes))
                    phase = "evaluation"
                    # Start independent held-out worlds; preserve the original
                    # evaluation stream for paired comparison with old advice.
                    rng = Random(config.seed)
                    check()
                # The latent lineup belongs to this whole hypothetical match,
                # not to a move, trick or deal. Keep trial i's assignment stable
                # even when later deals need different numbers of rejections.
                trial_index = learned if phase == "learning" else completed
                lineup_seed = train_seed if phase == "learning" else config.seed
                lineup = StrategyLineup.for_trial(match.id, lineup_seed, trial_index, own) if (
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
                weight = auction.trial_weight(batch.deals[0], auction_rng) if auction is not None else 1.0
                base = bridge.resume(batch.deals[0])
                root_turn = _prepare_turn(base)
                seed = rng.getrandbits(128)
                trial_randomness = TrialRandomness(seed)
                outcomes = {}
                traces = {}
                # One self fallback style for this whole evaluation trial and
                # all root candidates, independent of the other three profiles.
                fallback = fallback_profile(match.id, config.seed, completed) if (
                    direct or (competent_fallback and evaluator is not None)) else None
                for card in legal:
                    check()
                    trace = []
                    state = _play_prepared(base, root_turn, card, announce_bela=rows[str(card)]["bela"])
                    while not state.finished:
                        check()
                        turn = _prepare_turn(state)
                        view = turn.view
                        # Key randomness by the absolute next card position so
                        # one branch's tie-breaking cannot shift another's RNG.
                        ply = len(state.completed_tricks) * 4 + len(state.current_trick.cards)
                        move_rng = trial_randomness.at(ply)
                        if search is not None and view.player == own:
                            if evaluator is None:
                                selected, edge = search.select(view, turn.legal, move_rng)
                                trace.append(edge)
                            else:
                                selected = (evaluator.select(view, turn.legal, move_rng, fallback_policy=fallback)
                                            if competent_fallback else evaluator.select(view, turn.legal, move_rng))
                            bela = announce_bela(view, selected)
                        else:
                            policy = ((fallback if direct else config.self_policy) if view.player == own
                                      else lineup.for_player(view.player)) if lineup else config.policy
                            move = _choose_from_legal(view, move_rng, policy, turn.legal)
                            selected, bela = move.card, move.bela
                        state = _play_prepared(state, turn, selected, announce_bela=bela)
                    outcomes[str(card)] = outcome(state)
                    traces[str(card)] = trace
                # Commit only after every candidate in this trial has finished.
                if phase == "evaluation":
                    total_weight += weight
                    sum_squared_weights += weight * weight
                    best_value = max(values[3] for values in outcomes.values())
                    winners = [card for card, values in outcomes.items() if values[3] == best_value]
                    for card in winners:
                        best_counts[card] += weight / len(winners)
                    for card, values in outcomes.items():
                        for index, value in enumerate(values):
                            totals[card][index] += weight * value
                    for pair in paired:
                        paired[pair] += weight * (outcomes[pair[0]][3] - outcomes[pair[1]][3])
                if search is not None and evaluator is None:
                    for card, values in outcomes.items():
                        reward = (values[3] - low) / (high - low)
                        search.commit(traces[card], reward)
                if phase == "learning":
                    learned += 1
                else:
                    completed += 1
    except _Stopped as stopped:
        reason = stopped.reason
        discarded = sampled - completed - learned

    pairs = []
    if exact_layouts:
        tiebreak = 2 if config.objective == "point_difference" else None

        def ranking(card):
            total = totals[card]
            return total[3], total[tiebreak] if tiebreak is not None else total[team] - total[1-team]

        def mean(value):
            return float(Fraction(value, exact_weight))

        ordered = sorted(rows.values(), key=lambda row: (*(-v for v in ranking(row["card"])), row["card"]))
        leader = ordered[0]["card"]
        rank = 1
        for index, row in enumerate(ordered, 1):
            card = row["card"]
            if index > 1 and ranking(card) != ranking(ordered[index - 2]["card"]):
                rank = index
            total = totals[card]
            row.update(rank=rank, expected_recorded=tuple(map(mean, total[:2])),
                       expected_point_difference=mean(total[team] - total[1-team]),
                       proven_tie_with_leader=frozenset((leader, card)) in proven_ties,
                       not_separated_from_leader=False)
            for metric, offset in (("success", 2), ("our_sweep", 4), ("opponent_sweep", 5),
                                   ("our_match_win", 6), ("opponent_match_win", 7), ("match_continue", 8)):
                row[f"{metric}_probability"] = mean(total[offset])
            row["objective_mean"] = mean(total[3])
        for first, second in paired:
            gap = mean(totals[first][3] - totals[second][3])
            pairs.append({"first": first, "second": second, "mean_difference": gap, "interval": (gap, gap)})
    elif completed:
        interval_options = {"weight_sum": total_weight} if auction is not None else {}
        for card, total in totals.items():
            row = rows[card]
            row.update(samples=completed, expected_recorded=(total[0] / total_weight, total[1] / total_weight),
                       sample_best_share=best_counts[card] / total_weight,
                       sample_best_interval=confidence_interval(best_counts[card] / total_weight, 0, 1, completed, family, **interval_options),
                       our_sweep_probability=total[4] / total_weight,
                       opponent_sweep_probability=total[5] / total_weight,
                       our_sweep_interval=confidence_interval(total[4] / total_weight, 0, 1, completed, family, **interval_options) if not tracked.trick_counts[1-team] else (0,0),
                       opponent_sweep_interval=confidence_interval(total[5] / total_weight, 0, 1, completed, family, **interval_options) if not tracked.trick_counts[team] else (0,0),
                       our_match_win_probability=total[6]/total_weight,
                       opponent_match_win_probability=total[7]/total_weight,
                       match_continue_probability=total[8]/total_weight,
                       our_match_win_interval=confidence_interval(total[6]/total_weight,0,1,completed,family),
                       opponent_match_win_interval=confidence_interval(total[7]/total_weight,0,1,completed,family),
                       match_continue_interval=confidence_interval(total[8]/total_weight,0,1,completed,family),
                       expected_point_difference=(total[team] - total[1 - team]) / total_weight,
                       success_probability=total[2] / total_weight, objective_mean=total[3] / total_weight,
                       success_interval=confidence_interval(total[2] / total_weight, 0, 1, completed, family, **interval_options),
                       objective_interval=confidence_interval(total[3] / total_weight, low, high, completed, family, **interval_options))
            if opening_lead:
                row["first_trick_winner_probability"] = {
                    side: wins / total_weight for side, wins in zip(("self", "partner", "opponents"), total[9:])
                }
        # Keep the requested objective first. Use the other meaningful estimate
        # for exact ties rather than letting card codes decide the order.
        tiebreak = ("success_probability" if config.objective == "point_difference"
                    else "expected_point_difference")
        ordered = sorted(rows.values(), key=lambda row: (
            -row["objective_mean"], -row[tiebreak], row["card"]))
        for pair, total in paired.items():
            mean = total / total_weight
            interval = confidence_interval(mean, low - high, high - low, completed, family, **interval_options)
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

    statistics = search.statistics() if search is not None else None
    if split:
        statistics = statistics | {"statistics_scope": "learning", "evaluation":
                                   evaluator.statistics() if evaluator is not None else None}
    return {"match_id": bridge.match_id, "revision": bridge.revision, "deal_number": bridge.deal_number,
            "ruleset": RULESET_VERSION, "method": "public_exact_endgame_v1" if exact_layouts else "direct_competent_monte_carlo_v1" if direct else "learned_policy_monte_carlo_v1" if split else (
                "information_set_monte_carlo_v1" if search is not None else "paired_monte_carlo_v2"),
            "model": "soft_auction_v1" if auction is not None else "uniform_consistent_initial_deals",
            "auction_effective_samples": (total_weight ** 2 / sum_squared_weights
                                          if auction is not None and completed else None),
            "config": asdict(config),
            "strategy_model": {"mode": "hidden_match_lineups_v1" if config.policy == MIXED_POLICY else "uniform_policy_v1",
                               "assignment_scope": "hypothetical_match",
                               "profiles": [{"id": profile, "name": name, "intended_level": level}
                                            for level, (profile, name) in enumerate(zip(POLICIES, PROFILE_NAMES), 1)],
                               "other_player_weights": {p: 1 / len(POLICIES) for p in POLICIES} if (
                                   config.policy == MIXED_POLICY) else {config.policy: 1.0},
                               "self_policy": config.self_policy if config.policy == MIXED_POLICY else config.policy,
                               "self_search": statistics,
                               "self_profile_weights": ({p: 1/len(COMPETENT_FALLBACK_PROFILES) for p in COMPETENT_FALLBACK_PROFILES}
                                                         if direct else None),
                               "self_profile_assignment_scope": "hypothetical_match" if direct else None,
                               "future_replanning": ("fixed_competent_profile_mixture" if direct else
                                                     "frozen_learned_information_set_policy" if split else
                                                     "approximate_shared_information_set_tree" if isinstance(search, SharedSelfSearch)
                                                     else "finite_information_set_tree" if search is not None else "fixed_policy"),
                               "real_player_profiles_known": False,
                               "value_scope": "current_deal"},
            "our_team": team, "caller_team": caller_team, "match_score": tracked.setup.match_score,
            "recorded_presence_players": sorted(int(event.player) for event in match.deals[-1].events
                                                 if isinstance(event, Presence)),
            "recorded_event_count": len(match.deals[-1].events),
            "history_assumption": "complete_play_history_from_initial_eight_cards",
            "success_definition": "make_contract" if team == caller_team else "defeat_contract",
            "match_probability_scope":"end_of_current_deal",
            "match_objective_definition":"win_now_minus_lose_now; continuation_neutral; point_difference_tiebreak",
            "completed_samples": completed, "exact_layouts": exact_layouts, "sampling_attempts": attempts,
            "requested_learning_samples": requested_learning, "completed_learning_samples": learned,
            "learning_stop_reason": ("not_needed" if reason == "forced_move" else
                                     "sample_limit" if learned == requested_learning else
                                     "time_budget" if evaluator is not None else "interrupted") if split else None,
            "total_completed_trials": completed + learned, "stopped_phase": phase,
            "learning_stream": "independent_domain_seed" if split else None,
            "sampled_deals": sampled, "discarded_trials": discarded,
            "status": reason, "elapsed_seconds": perf_counter() - start,
            "uncertainty": "no_sampling_uncertainty" if exact_layouts else "95_percent_simultaneous_time_uniform_hoeffding",
            "interval_target": "enumerated_fixed_policy_model" if exact_layouts else "fixed_learned_policy_conditional_on_training" if split else (
                "average_conditional_rollout_value_under_evolving_tree" if search is not None else "fixed_policy_rollout_value"),
            "moves": ordered, "comparisons": pairs}


def _root_view(tracked):
    """Build the same restricted observation shape for the known root player."""
    from bela.domain.game import PlayerObservation
    return PlayerObservation(tracked.setup.player, tracked.hand, tracked.setup.trump,
                             tracked.setup.dealer, tracked.setup.caller, tracked.setup.match_score,
                             tracked.current_trick, tracked.completed_tricks, tracked.remaining_counts,
                             tracked.next_player, tracked.phase, None, (), tracked.bela_announcements, None)
