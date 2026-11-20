from collections.abc import Iterable

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.melds import (Meld, MeldContest, MeldKind, QUAD_POINTS,
                              RevealedMelds, SEQUENCE_ORDER)
from bela.domain.players import Seat


BELA_PAIRS = {suit: frozenset((Card(suit, Rank.KING), Card(suit, Rank.QUEEN)))
              for suit in Suit}


def _hand(cards: Iterable[Card]) -> frozenset[Card]:
    raw = tuple(cards)
    if (len(raw) > 8 or any(not isinstance(card, Card) for card in raw)
            or len(set(raw)) != len(raw)):
        raise ValueError("Expected at most eight distinct cards")
    return frozenset(raw)


def has_belot(cards: Iterable[Card]) -> bool:
    hand = _hand(cards)
    return len(hand) == 8 and len({card.suit for card in hand}) == 1


def detect_melds(cards: Iterable[Card]) -> tuple[Meld, ...]:
    """All scoring quads and maximal runs; belot is a separate match result."""
    hand = _hand(cards)
    if has_belot(hand):
        return ()
    result = []
    for rank in Rank:
        quad = tuple(Card(suit, rank) for suit in Suit)
        if rank in QUAD_POINTS and all(card in hand for card in quad):
            result.append(Meld(MeldKind.FOUR_OF_A_KIND, quad))
    for suit in Suit:
        run = []
        for rank in SEQUENCE_ORDER:
            card = Card(suit, rank)
            if card in hand:
                run.append(card)
            else:
                if len(run) >= 3:
                    result.append(Meld(MeldKind.SEQUENCE, tuple(run)))
                run = []
        if len(run) >= 3:
            result.append(Meld(MeldKind.SEQUENCE, tuple(run)))
    return tuple(sorted(result, key=lambda meld: meld.strength_key, reverse=True))


def compare_melds(left: Meld, right: Meld) -> int:
    """Positive when left wins; zero requires seating-order tiebreak upstream."""
    return (left.strength_key > right.strength_key) - (left.strength_key < right.strength_key)


def resolve_meld_contest(hands: Iterable[Iterable[Card]], dealer: Seat) -> MeldContest:
    """Truthful complete-information simulator of the declaration phase.

    Returns only public presence and mandatory winning-team reveals. Optional
    spoken comparisons are recorded separately by the simulator's announce APIs.
    """
    hands = tuple(_hand(hand) for hand in hands)
    if (not isinstance(dealer, Seat) or len(hands) != 4
            or any(len(hand) != 8 for hand in hands)
            or set().union(*hands) != set(deck())):
        raise ValueError("Expected a dealer and four disjoint eight-card hands")
    if any(has_belot(hand) for hand in hands):
        raise ValueError("Belot must be declared separately before ordinary play")
    melds = tuple(detect_melds(hand) for hand in hands)
    order = tuple(Seat((int(dealer) + offset) % 4) for offset in range(1, 5))
    presence = tuple((seat, bool(melds[seat])) for seat in order)
    contenders = tuple(seat for seat in order if melds[seat])
    if not contenders:
        return MeldContest(None, None, (0, 0), presence, ())
    # max keeps the first contender on equal strength: first right of dealer.
    winner = max(contenders, key=lambda seat: melds[seat][0].strength_key)
    revealed = tuple(RevealedMelds(seat, melds[seat]) for seat in order
                     if seat.team == winner.team and melds[seat])
    points = [0, 0]
    points[winner.team] = sum(meld.points for reveal in revealed for meld in reveal.melds)
    return MeldContest(winner, winner.team, tuple(points), presence, revealed)
