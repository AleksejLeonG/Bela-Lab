from collections.abc import Iterable

from bela.domain.cards import Card, Rank, Suit
from bela.domain.game import Seat, Trick


PLAIN_ORDER = (Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.JACK,
               Rank.QUEEN, Rank.KING, Rank.TEN, Rank.ACE)
TRUMP_ORDER = (Rank.SEVEN, Rank.EIGHT, Rank.QUEEN, Rank.KING,
               Rank.TEN, Rank.ACE, Rank.NINE, Rank.JACK)
PLAIN_POINTS = dict(zip(PLAIN_ORDER, (0, 0, 0, 2, 3, 4, 10, 11)))
TRUMP_POINTS = dict(zip(TRUMP_ORDER, (0, 0, 3, 4, 10, 11, 14, 20)))
_PLAIN_STRENGTH = {rank: index for index, rank in enumerate(PLAIN_ORDER)}
_TRUMP_STRENGTH = {rank: index for index, rank in enumerate(TRUMP_ORDER)}


def strength(card: Card, trump: Suit) -> int:
    return (_TRUMP_STRENGTH if card.suit == trump else _PLAIN_STRENGTH)[card.rank]


def card_points(card: Card, trump: Suit) -> int:
    return (TRUMP_POINTS if card.suit == trump else PLAIN_POINTS)[card.rank]


def winning_index(trick: Trick, trump: Suit) -> int:
    if not trick.cards:
        raise ValueError("An empty trick has no winner")
    led = trick.cards[0].suit
    return max(range(len(trick.cards)), key=lambda i: (
        2 if trick.cards[i].suit == trump else 1 if trick.cards[i].suit == led else 0,
        strength(trick.cards[i], trump),
    ))


def trick_winner(trick: Trick, trump: Suit) -> Seat:
    """Current leader of a partial trick or winner of a completed one."""
    return trick.seat_at(winning_index(trick, trump))


def legal_cards(hand: Iterable[Card], trick: Trick, trump: Suit) -> tuple[Card, ...]:
    """Follow suit, head when required, otherwise trump and overtrump.

    Partner ownership does not waive any obligation (rules section 10).
    Stable card-ID order is presentation order, never a strategic ranking.
    """
    cards = tuple(hand)
    if len(set(cards)) != len(cards):
        raise ValueError("A hand cannot contain duplicate cards")
    if len(trick.cards) == 4:
        raise ValueError("Cannot play into a completed trick")
    if set(cards).intersection(trick.cards):
        raise ValueError("A card cannot be both in hand and on the table")
    if not trick.cards:
        return tuple(sorted(cards, key=lambda card: card.id))

    led = trick.cards[0].suit
    following = tuple(card for card in cards if card.suit == led)
    trumps = tuple(card for card in cards if card.suit == trump)
    candidates = following or trumps or cards
    winning = trick.cards[winning_index(trick, trump)]
    # After a cut, following a non-trump suit has no heading obligation.
    must_head = (bool(following) and winning.suit == led) or (
        not following and bool(trumps) and winning.suit == trump
    )
    if must_head:
        stronger = tuple(card for card in candidates
                         if card.suit == winning.suit
                         and strength(card, trump) > strength(winning, trump))
        candidates = stronger or candidates
    return tuple(sorted(candidates, key=lambda card: card.id))
