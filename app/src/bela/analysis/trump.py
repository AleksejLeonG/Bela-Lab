"""Explainable six-card baseline. Scores are heuristics, never probabilities."""

from dataclasses import dataclass

from bela.domain.cards import Card, Rank, Suit
from bela.gameplay.calling import CallingObservation
from bela.rules.melds import detect_melds


BASELINE_POLICY = "six_card_control_v1"
POLICY = "position_control_v2"
CALLING_POLICIES = (BASELINE_POLICY, POLICY)
CALL_THRESHOLD = 45
POSITION_THRESHOLDS = (45, 49, 45, None)


@dataclass(frozen=True, slots=True)
class TrumpEvaluation:
    suit: Suit
    score: int
    trump_count: int
    components: tuple[tuple[str, int], ...]
    qualifies: bool


@dataclass(frozen=True, slots=True)
class TrumpAdvice:
    action: Suit | None  # None means pass, not an unknown trump.
    forced: bool
    rankings: tuple[TrumpEvaluation, ...]
    policy: str = POLICY
    threshold: int | None = CALL_THRESHOLD
    position: int = 1
    first_leader: str = "self"


def advise_trump(view: CallingObservation, policy=POLICY) -> TrumpAdvice:
    """Rank four suits using only the acting player's six cards.

    Third position favors the jack because the partner leads and the caller
    plays third. Second position requires more strength with an opponent on
    lead. These are explicit, uncalibrated conventions, not card deductions.
    The v1 baseline is retained for reproducible comparisons.
    """
    if not isinstance(view, CallingObservation):
        raise ValueError("Trump advice requires a six-card CallingObservation.")
    if policy not in CALLING_POLICIES:
        raise ValueError("Unknown calling policy.")
    position = len(view.state.passes) + 1
    first_leader = ("self", "opponent", "partner", "opponent")[position-1]
    threshold = POSITION_THRESHOLDS[position-1] if policy == POLICY else CALL_THRESHOLD
    hand = frozenset(view.hand)
    known_meld = min(20, max((m.points for m in detect_melds(hand)), default=0) // 10)
    rankings = []
    for suit in Suit:
        ranks = {c.rank for c in hand if c.suit == suit}
        count = len(ranks)
        side_aces = sum(c.rank == Rank.ACE and c.suit != suit for c in hand)
        supported_tens = sum(c.rank == Rank.TEN and c.suit != suit
                             and Card(c.suit, Rank.ACE) in hand for c in hand)
        parts = (
            ("Trump length", 6 * count),
            ("Trump jack", 18 * (Rank.JACK in ranks)),
            ("Trump nine", 12 * (Rank.NINE in ranks)),
            ("Trump ace", 6 * (Rank.ACE in ranks)),
            ("Trump ten", 3 * (Rank.TEN in ranks)),
            ("Length beyond two trumps", 5 * max(0, count - 2)),
            ("Missing trump jack", -8 * (count > 0 and Rank.JACK not in ranks)),
            ("Missing trump nine", -4 * (count > 0 and Rank.NINE not in ranks)),
            ("No visible trumps", -40 * (count == 0)),
            ("Side aces", 8 * side_aces),
            ("Side tens supported by an ace", 3 * supported_tens),
            ("Visible bela pair", 6 * ({Rank.KING, Rank.QUEEN} <= ranks)),
            ("Strongest visible ordinary meld", known_meld),
        )
        if policy == POLICY:
            parts += (
                ("Third-position jack with partner leading", 8 * (position == 3 and Rank.JACK in ranks)),
                ("Third-position call without the jack", -8 * (position == 3 and Rank.JACK not in ranks)),
                ("Forced-dealer singleton trump exposure", -12 * (position == 4 and count == 1)),
            )
        score = sum(points for _, points in parts)
        rankings.append(TrumpEvaluation(suit, score, count, parts,
                                       threshold is not None and count >= 2 and score >= threshold))
    # Explicit lexical tiebreak: C, D, H, S. No random choice or hidden input.
    rankings.sort(key=lambda row: (-row.score, row.suit.value))
    best = rankings[0]
    action = best.suit if view.state.forced or best.qualifies else None
    return TrumpAdvice(action, view.state.forced, tuple(rankings), policy, threshold, position, first_leader)
