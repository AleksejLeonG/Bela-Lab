from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    HEARTS = "H"
    SPADES = "S"
    DIAMONDS = "D"
    CLUBS = "C"


class Rank(str, Enum):
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


# Card IDs are stable archive values. Build these offsets once, rather than
# constructing and searching enum tuples on every simulation lookup.
_SUIT_OFFSETS = {suit: index * 8 for index, suit in enumerate(Suit)}
_RANK_INDICES = {rank: index for index, rank in enumerate(Rank)}


@dataclass(frozen=True, slots=True)
class Card:
    suit: Suit
    rank: Rank

    def __post_init__(self) -> None:
        if not isinstance(self.suit, Suit) or not isinstance(self.rank, Rank):
            raise ValueError("Card requires a Suit and a Rank")

    @classmethod
    def parse(cls, value: str) -> "Card":
        try:
            suit, rank = value.strip().upper().split("_")
            return cls(Suit(suit), Rank(rank))
        except (ValueError, AttributeError) as error:
            raise ValueError(f"Invalid card {value!r}; expected e.g. H_J or S_10") from error

    @property
    def id(self) -> int:
        return _SUIT_OFFSETS[self.suit] + _RANK_INDICES[self.rank]

    def __str__(self) -> str:
        return f"{self.suit.value}_{self.rank.value}"


def deck() -> tuple[Card, ...]:
    return tuple(Card(suit, rank) for suit in Suit for rank in Rank)
