"""Soft likelihood of a recorded auction under a fallible six-card caller."""

from itertools import combinations
from math import prod

from bela.analysis.trump import advise_trump
from bela.gameplay.calling import CallingObservation, CallingState


class AuctionEvidence:
    def __init__(self, setup):
        state = CallingState(setup.dealer)
        observations = []
        # Croatian Bela has one calling round; each seat before the caller passed.
        while state.next_player != setup.caller:
            if state.next_player != setup.player:
                observations.append((state, None))
            state = state.pass_turn(state.next_player)
        if setup.caller != setup.player:
            observations.append((state, setup.trump))
        self._observations = tuple(observations)
        self._exact = {}

    @staticmethod
    def _mass(state, observed, sixes):
        # An observed action gets one vote above a positive floor if the
        # heuristic agrees. Ratios are 2:1 for voluntary actions and 3:2
        # for a forced suit choice (there is no pass option for the dealer).
        floor = 2 if state.forced else 1
        count = len(sixes)
        agreements = sum(advise_trump(CallingObservation(state.next_player, six, state)).action == observed
                         for six in sixes)
        return floor * count + agreements, (floor + 1) * count

    def trial_weight(self, deal, rng):
        """Estimate the marginalized likelihood with four talon splits per seat."""
        hands = deal.hands
        weight = 1.0
        for state, observed in self._observations:
            hand = sorted(hands[state.next_player], key=lambda card: card.id)
            sixes = [tuple(rng.sample(hand, 6)) for _ in range(4)]
            mass, maximum = self._mass(state, observed, sixes)
            weight *= mass / maximum
        return weight

    def exact_weight(self, deal, check):
        """Integrate all 28 possible six-card hands in every observed seat."""
        hands = deal.hands
        factors = []
        for state, observed in self._observations:
            seat = state.next_player
            key = seat, deal.masks[seat]
            if key not in self._exact:
                check()
                sixes = list(combinations(hands[seat], 6))
                mass, _ = self._mass(state, observed, sixes)
                self._exact[key] = mass
            factors.append(self._exact[key])
        # Maximum masses depend only on calling position, so their product
        # cancels when normalizing all enumerated layouts.
        return prod(factors)
