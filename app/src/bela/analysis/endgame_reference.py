"""Bounded exact reference for known-card endgames; not a live advice path.

Opponents have independent, uniformly drawn fixed profiles at this root. Future
observed actions update that profile mixture exactly. Self maximizes expected
deal value without seeing the latent profiles, or uses an explicit fixed policy
for Monte Carlo estimator checks. All arithmetic for values is rational.
"""
from fractions import Fraction
from functools import lru_cache
from math import isfinite
from time import monotonic, perf_counter

from bela.analysis.policies import POLICIES, _public_context, announce_bela, choose_move
from bela.domain.game import Phase, PlayState, Seat
from bela.gameplay.simulation import observe, play_card, settle_play
from bela.rules.play import legal_cards


class ReferenceLimit(RuntimeError):
    """No exact result was certified within the requested resource limits."""


class _ChoiceIndex:
    def __init__(self, index):
        self.index = index
        self.stop = None

    def randrange(self, stop):
        if self.stop is not None or not 0 <= self.index < stop:
            raise ValueError("Reference policies must use one uniform tie-break draw.")
        self.stop = stop
        return self.index


def policy_distribution(view, policy):
    """Enumerate the actual policy's tie-break choices with rational weights."""
    first = _ChoiceIndex(0)
    move = choose_move(view, first, policy)
    if first.stop is None:
        raise ValueError("Reference policy did not expose its uniform tie break.")
    moves = [move]
    for index in range(1, first.stop):
        draw = _ChoiceIndex(index)
        moves.append(choose_move(view, draw, policy))
        if draw.stop != first.stop:
            raise ValueError("Reference policy changed its choice set during enumeration.")
    if len(set(moves)) != len(moves):
        raise ValueError("Reference policy returned duplicate tie-break actions.")
    return tuple((move, Fraction(1, len(moves))) for move in moves)


def opponent_distribution(distributions, weights):
    """Chance actions and posteriors for one seat's fixed latent profile.

    Weights are conditioned on earlier future actions, not redrawn each turn.
    No profile identity is supplied to the optimizing self decision.
    """
    if (not weights or len(distributions) != len(weights) or
            any(w < 0 for w in weights) or sum(weights) != 1):
        raise ValueError("Expected a normalized posterior over opponent profiles.")
    likelihoods = {}
    for index, distribution in enumerate(distributions):
        for move, probability in distribution:
            likelihoods.setdefault(move, [Fraction(0)] * len(weights))[index] += probability
    result = []
    for move, chances in likelihoods.items():
        joint = tuple(w * p for w, p in zip(weights, chances))
        probability = sum(joint)
        if probability:
            result.append((move, probability, tuple(p / probability for p in joint)))
    if sum(p for _, p, _ in result) != 1:
        raise ValueError("Opponent action probabilities do not sum to one.")
    return tuple(result)


def solve_known_endgame(state, *, objective="point_difference", self_policy=None,
                        opponent_policies=POLICIES, max_nodes=100_000,
                        seconds=30, cancelled=None):
    """Exact root action values with at most twelve cards still in hands.

    Other players' remaining cards must have been publicly revealed. This
    deliberately rejects ordinary hidden-hand positions rather than silently
    using simulator knowledge. The root actor is the optimizing seat; partner
    and opponents all follow the stated fixed-profile mixture. The prior starts
    uniformly at this analysis root, matching current Monte Carlo advice.

    self_policy=None means optimal future self actions for this model. A named
    fixed self policy produces a like-for-like reference for rollout estimates.
    Equal optimal future values use the lowest legal card ID as a deterministic
    tie break. Root output includes every exactly tied optimal card.
    Limits/cancellation raise ReferenceLimit; partial work is never called exact.
    """
    if not isinstance(state, PlayState) or state.phase != Phase.PLAYING:
        raise ValueError("An exact reference requires an unfinished playing state.")
    if objective not in ("point_difference", "contract_success"):
        raise ValueError("Unknown exact-reference objective.")
    if self_policy is not None and self_policy not in POLICIES:
        raise ValueError("Self must optimize or use a named fixed policy.")
    if (not isinstance(opponent_policies, tuple) or not opponent_policies or
            any(type(p) is not str or p not in POLICIES for p in opponent_policies) or
            len(set(opponent_policies)) != len(opponent_policies)):
        raise ValueError("Expected distinct known opponent profiles.")
    if type(max_nodes) is not int or not 1 <= max_nodes <= 1_000_000:
        raise ValueError("Reference node budget must be between one and one million.")
    if type(seconds) not in (int, float) or not isfinite(seconds) or not 0 <= seconds <= 60:
        raise ValueError("Reference seconds must be between zero and sixty.")
    remaining = sum(map(len, state.hands))
    if not 1 <= remaining <= 12:
        raise ValueError("Exact reference is limited to twelve remaining cards.")
    own = state.next_player
    team = own.team
    known = _public_context(observe(state, own))[1]
    if any(known.get(card) != seat for seat in Seat if seat != own for card in state.hands[seat]):
        raise ValueError("Every other remaining card must be publicly revealed for this reference.")
    started = perf_counter()
    deadline = monotonic() + seconds
    cancelled = cancelled or (lambda: False)
    nodes = 0
    uniform = (Fraction(1, len(opponent_policies)),) * len(opponent_policies)
    prior = tuple(() if seat == own else uniform for seat in Seat)

    def check():
        if cancelled():
            raise ReferenceLimit("Exact endgame cancelled; no certified result.")
        if monotonic() >= deadline:
            raise ReferenceLimit("Exact endgame time limit; no certified result.")

    def score(value):
        return value[team] - value[1-team] if objective == "point_difference" else value[2]

    def average(branches):
        return tuple(sum(probability * value[i] for probability, value in branches) for i in range(4))

    @lru_cache(maxsize=max_nodes)
    def distribution(view, policy):
        return policy_distribution(view, policy)

    @lru_cache(maxsize=max_nodes)
    def visit(current, beliefs):
        nonlocal nodes
        check()
        nodes += 1
        if nodes > max_nodes:
            raise ReferenceLimit("Exact endgame node limit; no certified result.")
        if current.finished:
            result = settle_play(current)
            success = int(result.caller_passed if team == result.caller_team else not result.caller_passed)
            value = (Fraction(result.recorded[0]), Fraction(result.recorded[1]), Fraction(success))
            measured = value[team] - value[1-team] if objective == "point_difference" else value[2]
            return (*value, measured ** 2)
        actor = current.next_player
        view = observe(current, actor)
        if actor == own and self_policy is None:
            choices = []
            for card in legal_cards(view.hand, view.current_trick, view.trump):
                child = play_card(current, actor, card, announce_bela=announce_bela(view, card))
                choices.append(visit(child, beliefs))
            return max(choices, key=score)
        if actor == own:
            branches = []
            for move, probability in distribution(view, self_policy):
                child = play_card(current, actor, move.card, announce_bela=move.bela)
                branches.append((probability, visit(child, beliefs)))
            return average(branches)
        chances = opponent_distribution(
            tuple(distribution(view, policy) for policy in opponent_policies), beliefs[actor])
        branches = []
        for move, probability, posterior in chances:
            updated = tuple(posterior if seat == actor else weights for seat, weights in enumerate(beliefs))
            child = play_card(current, actor, move.card, announce_bela=move.bela)
            branches.append((probability, visit(child, updated)))
        return average(branches)

    check()
    root_view = observe(state, own)
    rows = []
    for card in legal_cards(root_view.hand, root_view.current_trick, root_view.trump):
        bela = announce_bela(root_view, card)
        child = play_card(state, own, card, announce_bela=bela)
        value = visit(child, prior)
        difference = value[team] - value[1-team]
        measured = score(value)
        variance = value[3] - measured ** 2
        assert variance >= 0
        rows.append({"card": str(card), "bela": bela,
            "expected_recorded": [float(value[0]), float(value[1])],
            "expected_point_difference": float(difference), "point_difference_fraction": str(difference),
            "success_probability": float(value[2]), "success_fraction": str(value[2]),
            "objective_value": float(measured), "objective_fraction": str(measured),
            "objective_variance": float(variance), "objective_variance_fraction": str(variance)})
    check()
    best = max(Fraction(row['objective_fraction']) for row in rows)
    return {"method": "exact_known_card_endgame_v1", "status": "complete",
            "scope": "known_remaining_cards_only", "remaining_cards": remaining,
            "objective": objective, "self_continuation": self_policy or "optimal_for_stated_model",
            "opponent_profiles": list(opponent_policies), "profile_prior": "independent_uniform_at_root",
            "profile_persistence": "fixed_per_seat_with_future_action_conditioning",
            "best_cards": [r['card'] for r in rows if Fraction(r['objective_fraction']) == best],
            "best_objective_fraction": str(best), "moves": rows, "nodes": nodes,
            "cache_hits": visit.cache_info().hits, "elapsed_seconds": perf_counter() - started}
