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
        return tuple(Suit).index(self.suit) * 8 + tuple(Rank).index(self.rank)

    def __str__(self) -> str:
        return f"{self.suit.value}_{self.rank.value}"


def deck() -> tuple[Card, ...]:
    return tuple(Card(suit, rank) for suit in Suit for rank in Rank)
