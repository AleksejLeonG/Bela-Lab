"""Exhaustively evaluate small public-information endgames under fixed policies."""

from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from time import monotonic

from bela.analysis.endgame_reference import opponent_distribution, policy_distribution
from bela.analysis.learned_policy import COMPETENT_FALLBACK_PROFILES
from bela.analysis.policies import MIXED_POLICY, POLICIES, announce_bela
from bela.gameplay.simulation import observe, play_card
from bela.rules.play import legal_cards


MAX_CARDS = 12
MAX_LAYOUTS = 64
MAX_NODES = 4096
MAX_SECONDS = 0.4


class _ExactLimit(Exception):
    pass


def evaluate_endgame(bridge, sampler, legal, own, policy, score, *, seconds, check, auction=None):
    """Return exact model values, and certify outcome ties independent of card choices.

    Layouts satisfy the recorded evidence, with optional auction weighting. Each
    actor's unknown profile is held fixed through the continuation; policies
    receive only their own observations. The optional proof checks every card
    choice in a layout using the same automatic Bela convention as advice.
    A bounded-out calculation contributes no partial results.
    """
    if sampler.proposal_count > MAX_LAYOUTS:
        return None
    deadline = monotonic() + seconds
    nodes = 0
    styles = tuple(
        (COMPETENT_FALLBACK_PROFILES if seat == own else POLICIES)
        if policy == MIXED_POLICY else (policy,)
        for seat in range(4)
    )
    prior = tuple((Fraction(1, len(group)),) * len(group) for group in styles)

    def tick():
        nonlocal nodes
        check()
        nodes += 1
        if nodes > MAX_NODES or monotonic() >= deadline:
            raise _ExactLimit

    @lru_cache(maxsize=MAX_NODES)
    def invariant(state):
        tick()
        if state.finished:
            return score(state)
        actor = state.next_player
        view = observe(state, actor)
        common = None
        for card in legal_cards(view.hand, view.current_trick, view.trump):
            branch = invariant(play_card(state, actor, card, announce_bela=announce_bela(view, card)))
            if branch is None or (common is not None and branch != common):
                return None
            common = branch
        return common

    @lru_cache(maxsize=MAX_NODES)
    def expected(state, beliefs):
        constant = invariant(state)
        if constant is not None:
            return constant
        tick()
        actor = state.next_player
        view = observe(state, actor)
        actions = opponent_distribution(
            tuple(policy_distribution(view, name) for name in styles[actor]), beliefs[actor])
        total = [0] * 9
        for move, probability, posterior in actions:
            updated = beliefs[:actor] + (posterior,) + beliefs[actor + 1:]
            child = play_card(state, actor, move.card, announce_bela=move.bela)
            for index, value in enumerate(expected(child, updated)):
                total[index] += probability * value
        return tuple(total)

    totals = {str(card): [0] * 9 for card in legal}
    proven = {frozenset(map(str, pair)) for pair in combinations(legal, 2)}
    layouts = 0
    total_weight = 0
    try:
        for deal in sampler.enumerate_deals(tick):
            weight = auction.exact_weight(deal, tick) if auction is not None else 1
            state = bridge.resume(deal)
            view = observe(state, own)
            constants = {}
            for card in legal:
                child = play_card(state, own, card, announce_bela=announce_bela(view, card))
                key = str(card)
                constants[key] = invariant(child)
                for index, value in enumerate(expected(child, prior)):
                    totals[key][index] += weight * value
            proven = {pair for pair in proven
                      if all(constants[card] is not None for card in pair)
                      and len({constants[card] for card in pair}) == 1}
            layouts += 1
            total_weight += weight
    except _ExactLimit:
        return None
    if not layouts:
        return None
    return layouts, total_weight, totals, proven
