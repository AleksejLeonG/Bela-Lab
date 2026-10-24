"""Uniform synthetic initial deals conditioned on the player's hard evidence.

Count capacity-correct ownership assignments exactly, draw them with integer
weights, then reject deals that fail declarations. Validator witnesses never
enter this process. Samples are transient hypotheses, not observed game data.
"""

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from random import Random
from time import monotonic, perf_counter

from bela.domain.cards import deck
from bela.analysis.validation import MeldConstraint


CARDS = deck()


class SamplingLimit(ValueError):
    """Preparation exceeded its budget; consistency remains undecided."""


class NoConsistentDeals(ValueError):
    """The supplied evidence has been proved impossible."""


@dataclass(frozen=True)
class SampledDeal:
    """A hypothetical INITIAL allocation, including cards already played."""

    masks: tuple[int, int, int, int]

    @property
    def hands(self):
        return tuple(frozenset(card for card in CARDS if mask & (1 << card.id))
                     for mask in self.masks)

    def remaining_hands(self, played):
        """Remove public played cards before passing hypotheses to simulations."""
        played = frozenset(played)
        return tuple(hand - played for hand in self.hands)


@dataclass(frozen=True)
class SampleBatch:
    deals: tuple[SampledDeal, ...]
    requested: int
    attempts: int
    stop_reason: str
    elapsed_seconds: float
    model: str = "uniform_consistent_initial_deals"

    @property
    def complete(self):
        return len(self.deals) == self.requested

    @property
    def acceptance_rate(self):
        return len(self.deals) / self.attempts if self.attempts else None

    def ownership_counts(self):
        """32 rows of seat counts. Divide by len(deals), never by attempts.

        These concern initial ownership; callers must hide already played cards
        for remaining-hand displays. Empty batches provide no estimates.
        """
        counts = [[0] * 4 for _ in CARDS]
        for deal in self.deals:
            for seat, mask in enumerate(deal.masks):
                for card_id in range(32):
                    if mask & (1 << card_id):
                        counts[card_id][seat] += 1
        return tuple(tuple(row) for row in counts)


def _seconds(value):
    if not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
        raise ValueError("Seconds must be finite and nonnegative.")


class HandSampler:
    """Prepare once per evidence snapshot; request reproducible batches by seed.

    Dynamic programming counts completions of ownership domains with exactly
    eight cards per seat. Sound declaration propagation reduces those domains.
    The remaining declaration conditions are enforced by rejection sampling.
    Strong evidence can still have low acceptance: return fewer samples with an
    explicit stop reason rather than substituting biased feasibility witnesses.
    """

    def __init__(self, evidence, *, seconds=3.0, max_states=200_000):
        _seconds(seconds)
        if type(max_states) is not int or max_states < 1:
            raise ValueError("max_states must be a positive integer.")
        deadline = monotonic() + seconds
        domains = tuple(evidence.domains)
        if len(domains) != 32 or any(type(m) is not int or not 0 < m <= 15 for m in domains):
            raise ValueError("Expected 32 nonempty four-seat ownership domains.")
        checks = dict(evidence.constraints)
        if any(not isinstance(seat, int) or isinstance(seat, bool) or seat not in range(4) for seat in checks):
            raise ValueError("Constraint seats must be integers 0–3.")
        if any(not isinstance(check, MeldConstraint) for check in checks.values()):
            raise ValueError("Sampling requires structured meld constraints.")

        def tick():
            if monotonic() >= deadline:
                raise SamplingLimit("Sampler preparation reached its time limit; no probability estimate is available.")

        # Each elimination is a logical implication, preserving every valid deal.
        while True:
            tick()
            previous = domains
            narrowed = list(domains)
            for seat in range(4):
                bit = 1 << seat
                fixed = sum(1 << i for i, mask in enumerate(narrowed) if mask == bit)
                available = sum(1 << i for i, mask in enumerate(narrowed) if mask & bit)
                if fixed.bit_count() > 8 or available.bit_count() < 8:
                    raise NoConsistentDeals("No allocation fits the hand sizes.")
                forced = available if available.bit_count() == 8 else 0
                excluded = available & ~fixed if fixed.bit_count() == 8 else 0
                if seat in checks:
                    possible, extra, blocked = checks[seat].narrow(fixed, available)
                    if not possible:
                        raise NoConsistentDeals("No allocation fits the declarations.")
                    forced |= extra
                    excluded |= blocked
                for i in range(32):
                    if forced & (1 << i):
                        if not narrowed[i] & bit:
                            raise NoConsistentDeals("Conflicting card ownership.")
                        narrowed[i] = bit
                    if excluded & (1 << i):
                        narrowed[i] &= ~bit
                    if not narrowed[i]:
                        raise NoConsistentDeals("Conflicting card ownership.")
            domains = tuple(narrowed)
            if domains == previous:
                break

        self._checks = tuple(sorted(checks.items()))
        self._order = tuple(sorted(range(32), key=lambda i: (domains[i].bit_count(), domains[i], i)))
        self._options = tuple(tuple(seat for seat in range(4) if domains[i] & (1 << seat))
                              for i in self._order)
        suffix = [None] * 33
        suffix[32] = (0, 0, 0, 0)
        for index in range(31, -1, -1):
            suffix[index] = tuple(suffix[index + 1][seat] + (seat in self._options[index])
                                  for seat in range(4))
        states = 0

        @lru_cache(maxsize=None)
        def count(index, capacities):
            nonlocal states
            tick()
            states += 1
            if states > max_states:
                raise SamplingLimit("Sampler preparation reached its state limit; no probability estimate is available.")
            if any(n < 0 or n > suffix[index][seat] for seat, n in enumerate(capacities)):
                return 0
            if index == 32:
                return int(capacities == (0, 0, 0, 0))
            total = 0
            for seat in self._options[index]:
                if capacities[seat]:
                    remaining = list(capacities)
                    remaining[seat] -= 1
                    total += count(index + 1, tuple(remaining))
            return total

        self.proposal_count = count(0, (8, 8, 8, 8))
        self.preparation_states = states
        if not self.proposal_count:
            raise NoConsistentDeals("No allocation fits the ownership restrictions.")
        # Freeze the completed table: draws must never grow a cache or consult
        # the expired preparation deadline.
        self._weights = {}
        def weights(index, capacities):
            key = (index, capacities)
            if key in self._weights or index == 32:
                return
            tick()
            choices = []
            for seat in self._options[index]:
                if not capacities[seat]:
                    continue
                remaining = list(capacities)
                remaining[seat] -= 1
                remaining = tuple(remaining)
                weight = count(index + 1, remaining)
                if weight:
                    choices.append((seat, remaining, weight))
            self._weights[key] = tuple(choices)
            for _, remaining, _ in choices:
                weights(index + 1, remaining)
        weights(0, (8, 8, 8, 8))
        count.cache_clear()

    def sample(self, count, *, seed=None, seconds=1.0, max_attempts=100_000):
        """Draw with replacement; duplicate deals are intentional and valid.

        A fixed seed and sufficient time reproduce results. Time/attempt limits
        return a partial batch, never a claim that no consistent deal exists.
        """
        _seconds(seconds)
        if type(count) is not int or count < 0:
            raise ValueError("Sample count must be a nonnegative integer.")
        if type(max_attempts) is not int or max_attempts < 0:
            raise ValueError("max_attempts must be a nonnegative integer.")
        rng = Random(seed)
        start = perf_counter()
        deadline = monotonic() + seconds
        accepted = []
        attempts = 0
        reason = "requested_count"
        while len(accepted) < count:
            if attempts >= max_attempts:
                reason = "attempt_limit"
                break
            if monotonic() >= deadline:
                reason = "time_limit"
                break
            capacities = (8, 8, 8, 8)
            hands = [0] * 4
            for index, card_id in enumerate(self._order):
                choices = self._weights[index, capacities]
                ticket = rng.randrange(sum(weight for _, _, weight in choices))
                for seat, remaining, weight in choices:
                    if ticket < weight:
                        capacities = remaining
                        hands[seat] |= 1 << card_id
                        break
                    ticket -= weight
            attempts += 1
            if all(check.accepts(hands[seat]) for seat, check in self._checks):
                accepted.append(SampledDeal(tuple(hands)))
        return SampleBatch(tuple(accepted), count, attempts, reason, perf_counter() - start)
