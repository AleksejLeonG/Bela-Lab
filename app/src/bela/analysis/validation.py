"""Bounded, exact feasibility search for four hidden eight-card hands.

Bit masks and partial meld constraints prune impossible branches before whole
hands are built. Successful witnesses are private, bounded, rechecked hints;
they are neither game observations nor probability samples.
"""

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from random import Random
from threading import Lock
from time import monotonic

from bela.domain.cards import Rank, deck
from bela.domain.melds import QUAD_POINTS, QUAD_POWER


class ValidationLimit(ValueError):
    """Budget exhausted; no conclusion about consistency has been proved."""


CARDS = deck()
SUIT_MASKS = tuple(255 << (8 * suit) for suit in range(4))
QUADS = tuple((sum(1 << (8 * suit + rank) for suit in range(4)),
               (QUAD_POINTS[value], 1, QUAD_POWER[value]))
              for rank, value in enumerate(Rank) if value in QUAD_POINTS)
# Every scoring run, including subruns. Forbidden supersets are removed below.
PATTERNS = tuple((mask, key, "four_of_a_kind") for mask, key in QUADS) + tuple(
    (((1 << length) - 1) << (suit * 8 + start),
     (20 if length == 3 else 50 if length == 4 else 100, 0, start + length - 1), "sequence")
    for suit in range(4) for length in range(3, 8) for start in range(9 - length))


@lru_cache(maxsize=32768)
def meld_signature(hand):
    """Equivalent to detect_melds, using maximal runs and the same strength key."""
    if hand in SUIT_MASKS:
        return (), None
    found = [("four_of_a_kind", mask, key) for mask, key in QUADS if hand & mask == mask]
    for suit in range(4):
        bits = (hand >> (8 * suit)) & 255
        start = 0
        while start < 8:
            if not bits & (1 << start):
                start += 1
                continue
            end = start + 1
            while end < 8 and bits & (1 << end):
                end += 1
            length = end - start
            if length >= 3:
                mask = ((1 << length) - 1) << (8 * suit + start)
                key = (20 if length == 3 else 50 if length == 4 else 100, 0, end - 1)
                found.append(("sequence", mask, key))
            start = end
    return tuple(sorted((kind, mask) for kind, mask, _ in found)), max(
        (key for _, _, key in found), default=None)


@dataclass(frozen=True)
class MeldConstraint:
    presence: bool | None = None
    points: int | None = None
    high: int | None = None
    exact: tuple[tuple[str, int], ...] | None = None
    no_belot: bool = False
    ceiling: tuple[int, int, int] | None = None
    strict_ceiling: bool = False
    no_melds: bool = False

    def accepts(self, hand):
        signature, strongest = meld_signature(hand)
        if self.no_belot and hand in SUIT_MASKS:
            return False
        if self.presence is not None and bool(signature) != self.presence:
            return False
        if self.points is not None and (strongest is None or strongest[0] != self.points):
            return False
        if self.high is not None and (strongest is None or strongest[1:] != (0, self.high)):
            return False
        if self.exact is not None and signature != self.exact:
            return False
        if self.no_melds and signature:
            return False
        if self.ceiling is not None and strongest is not None:
            if strongest > self.ceiling or (self.strict_ceiling and strongest == self.ceiling):
                return False
        return True

    def __call__(self, cards):
        return self.accepts(sum(1 << card.id for card in cards))

    @lru_cache(maxsize=1024)
    def rules(self):
        forbidden = []
        for mask, key, kind in PATTERNS:
            disallowed = self.no_melds or self.presence is False
            disallowed |= self.points is not None and key[0] > self.points
            if self.high is not None and self.points is not None:
                disallowed |= key > (self.points, 0, self.high)
            if self.exact is not None:
                disallowed |= not any(kind == expected_kind and mask & expected == mask
                                      for expected_kind, expected in self.exact)
            if self.ceiling is not None:
                disallowed |= key > self.ceiling or (self.strict_ceiling and key == self.ceiling)
            if disallowed:
                forbidden.append(mask)
        forbidden.extend(mask for mask in SUIT_MASKS if not self.accepts(mask))
        minimal = []
        for mask in sorted(set(forbidden), key=lambda m: (m.bit_count(), m)):
            if not any(mask & smaller == smaller for smaller in minimal):
                minimal.append(mask)
        required = 0
        for _, mask in self.exact or ():
            required |= mask
        options = None
        if self.points is not None or self.high is not None or self.presence is True:
            options = tuple(mask for mask, key, kind in PATTERNS
                            if (self.points is None or key[0] == self.points)
                            and (self.high is None or key[1:] == (0, self.high))
                            and not any(mask & blocked == blocked for blocked in minimal))
        return tuple(minimal), required, options

    def narrow(self, required, available):
        if required.bit_count() == 8:
            return self.accepts(required), 0, 0
        # detect_melds deliberately returns no ordinary melds for belot. Do not
        # prune its triples while that exceptional completion remains possible.
        if any(required & ~suit == 0 and available & suit == suit and self.accepts(suit)
               for suit in SUIT_MASKS):
            return True, 0, 0
        forbidden, forced, options = self.rules()
        required |= forced
        if required & ~available or required.bit_count() > 8:
            return False, 0, 0
        excluded = 0
        for mask in forbidden:
            missing = mask & ~required
            if not missing:
                return False, 0, 0
            if missing.bit_count() == 1:
                excluded |= missing
        if options is not None:
            feasible = [mask for mask in options if not mask & ~available
                        and (mask | required).bit_count() <= 8
                        and not any((mask | required) & blocked == blocked for blocked in forbidden)]
            if not feasible:
                return False, 0, 0
            shared = feasible[0]
            for mask in feasible[1:]:
                shared &= mask
            forced |= shared
        return not bool(forced & excluded), forced, excluded


@dataclass
class ValidationStats:
    nodes: int = 0
    propagations: int = 0
    matching_attempts: int = 0
    witness_hits: int = 0


_WITNESSES = deque(maxlen=32)
_WITNESS_LOCK = Lock()


def clear_witness_cache():
    with _WITNESS_LOCK:
        _WITNESSES.clear()


def allocation_exists(domains, checks, *, max_nodes=100_000, seconds=3.0, stats=None):
    """Prove existence or nonexistence; raise ValidationLimit on exhaustion.

    Domains describe INITIAL ownership, including already played cards. Opaque
    hand predicates remain supported for tests; structured constraints also
    support sound partial-hand propagation. No witness leaves this module.
    """
    stats = stats if stats is not None else ValidationStats()
    deadline = monotonic() + seconds
    nodes = 0
    domains = tuple(domains)
    if len(domains) != 32 or any(type(m) is not int or not 0 < m <= 15 for m in domains):
        return False

    def tick():
        nonlocal nodes
        nodes += 1
        stats.nodes += 1
        if nodes > max_nodes or monotonic() >= deadline:
            raise ValidationLimit("Validation reached its computation limit. The input was not accepted; "
                                  "this does not prove it is wrong. Add revealed cards or a more specific declaration.")

    def accepts(seat, hand):
        check = checks.get(seat)
        if check is None:
            return True
        if isinstance(check, MeldConstraint):
            return check.accepts(hand)
        return check(frozenset(CARDS[i] for i in range(32) if hand & (1 << i)))

    def valid(witness, masks):
        if any(not masks[i] & (1 << seat) for seat, hand in enumerate(witness)
               for i in range(32) if hand & (1 << i)):
            return False
        return all(accepts(seat, hand) for seat, hand in enumerate(witness))

    def remember(witness):
        with _WITNESS_LOCK:
            if witness not in _WITNESSES:
                _WITNESSES.appendleft(witness)

    def propagate(masks):
        masks = list(masks)
        while True:
            tick()
            stats.propagations += 1
            before = tuple(masks)
            for seat in range(4):
                bit = 1 << seat
                fixed = sum(1 << i for i, mask in enumerate(masks) if mask == bit)
                available = sum(1 << i for i, mask in enumerate(masks) if mask & bit)
                if fixed.bit_count() > 8 or available.bit_count() < 8:
                    return None
                forced = available if available.bit_count() == 8 else 0
                excluded = available & ~fixed if fixed.bit_count() == 8 else 0
                check = checks.get(seat)
                if isinstance(check, MeldConstraint):
                    possible, extra, blocked = check.narrow(fixed, available)
                    if not possible:
                        return None
                    forced |= extra
                    excluded |= blocked
                elif fixed.bit_count() == 8 and not accepts(seat, fixed):
                    return None
                for i in range(32):
                    if forced & (1 << i):
                        if not masks[i] & bit:
                            return None
                        masks[i] = bit
                    if excluded & (1 << i):
                        masks[i] &= ~bit
                        if not masks[i]:
                            return None
            # Hall capacity constraints for every subset of the four players.
            # A saturated subset owns all its restricted cards, so it cannot
            # also own other cards. This detects joint, not just per-seat, conflicts.
            for subset in range(1, 15):
                capacity = 8 * subset.bit_count()
                restricted = [i for i, mask in enumerate(masks) if mask & ~subset == 0]
                if len(restricted) > capacity:
                    return None
                if len(restricted) == capacity:
                    for i, mask in enumerate(masks):
                        if mask & ~subset:
                            masks[i] &= ~subset
                            if not masks[i]:
                                return None
            if tuple(masks) == before:
                return tuple(masks)

    def matching(masks, attempt):
        tick()
        stats.matching_attempts += 1
        slots = [None] * 32
        rng = Random(attempt)
        order = list(range(32))
        rng.shuffle(order)
        order.sort(key=lambda i: masks[i].bit_count())
        seats = list(range(4))
        rng.shuffle(seats)

        def assign(card, seen):
            for seat in seats:
                if not masks[card] & (1 << seat):
                    continue
                for slot in range(seat * 8, seat * 8 + 8):
                    if slot in seen:
                        continue
                    seen.add(slot)
                    if slots[slot] is None or assign(slots[slot], seen):
                        slots[slot] = card
                        return True
            return False

        for card in order:
            if not assign(card, set()):
                return None
        return tuple(sum(1 << card for card in slots[seat * 8:seat * 8 + 8]) for seat in range(4))

    tick()  # Limits apply to cache hits too.
    with _WITNESS_LOCK:
        hints = tuple(_WITNESSES)
    for hint in hints:
        tick()
        if valid(hint, domains):
            stats.witness_hits += 1
            return True
    dead = set()

    def search(masks, root=False):
        masks = propagate(masks)
        if masks is None or masks in dead:
            return False
        # Fast deterministic witness attempts are only a shortcut to TRUE.
        # Failure always falls through to exhaustive branching below.
        for attempt in range(16 if root else 1):
            witness = matching(masks, attempt)
            if witness is None:
                return False
            if valid(witness, masks):
                remember(witness)
                return True
        unresolved = [i for i, mask in enumerate(masks) if mask.bit_count() > 1]
        if not unresolved:
            dead.add(masks)
            return False
        card = min(unresolved, key=lambda i: (masks[i].bit_count(), i))
        for seat in range(4):
            if masks[card] & (1 << seat):
                branch = list(masks)
                branch[card] = 1 << seat
                if search(tuple(branch)):
                    return True
        dead.add(masks)
        return False

    return search(domains, root=True)
