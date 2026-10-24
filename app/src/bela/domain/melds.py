"""Declaration values and public records; no hidden hands in these objects."""

from dataclasses import dataclass
from enum import Enum

from bela.domain.cards import Card, Rank
from bela.domain.players import Seat


SEQUENCE_ORDER = tuple(Rank)  # 7, 8, 9, 10, J, Q, K, A
QUAD_POINTS = {Rank.JACK: 200, Rank.NINE: 150, Rank.ACE: 100,
               Rank.TEN: 100, Rank.KING: 100, Rank.QUEEN: 100}
QUAD_POWER = {Rank.QUEEN: 0, Rank.KING: 1, Rank.TEN: 2,
              Rank.ACE: 3, Rank.NINE: 4, Rank.JACK: 5}


class MeldKind(str, Enum):
    SEQUENCE = "sequence"
    FOUR_OF_A_KIND = "four_of_a_kind"


@dataclass(frozen=True, slots=True)
class Meld:
    kind: MeldKind
    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, MeldKind) or not isinstance(self.cards, tuple)
                or any(not isinstance(card, Card) for card in self.cards)
                or len(set(self.cards)) != len(self.cards)):
            raise ValueError("A meld needs a kind and distinct Card objects")
        if self.kind == MeldKind.FOUR_OF_A_KIND:
            ranks = {card.rank for card in self.cards}
            if len(self.cards) != 4 or len(ranks) != 1 or next(iter(ranks)) not in QUAD_POINTS:
                raise ValueError("Only four J, 9, A, 10, K or Q form a scoring quad")
        else:
            indices = sorted(SEQUENCE_ORDER.index(card.rank) for card in self.cards)
            if (not 3 <= len(self.cards) <= 7 or len({card.suit for card in self.cards}) != 1
                    or indices != list(range(indices[0], indices[0] + len(indices)))):
                raise ValueError("A sequence needs 3–7 consecutive cards in one suit")

    @property
    def high_rank(self) -> Rank:
        return max((card.rank for card in self.cards), key=SEQUENCE_ORDER.index)

    @property
    def points(self) -> int:
        if self.kind == MeldKind.FOUR_OF_A_KIND:
            return QUAD_POINTS[self.high_rank]
        return 20 if len(self.cards) == 3 else 50 if len(self.cards) == 4 else 100

    @property
    def strength_key(self) -> tuple[int, int, int]:
        """Equal-value sequences compare by endpoint, never by length or suit."""
        if self.kind == MeldKind.FOUR_OF_A_KIND:
            return self.points, 1, QUAD_POWER[self.high_rank]
        return self.points, 0, SEQUENCE_ORDER.index(self.high_rank)


@dataclass(frozen=True, slots=True)
class RevealedMelds:
    player: Seat
    melds: tuple[Meld, ...]

    @property
    def cards(self) -> frozenset[Card]:
        return frozenset(card for meld in self.melds for card in meld.cards)


@dataclass(frozen=True, slots=True)
class MeldContest:
    winning_player: Seat | None
    winning_team: int | None
    awarded_points: tuple[int, int]
    # Actual yes/no records. Full simulator setup supplies all four in play
    # order; tracked analysis retains only statements entered by the user.
    presence: tuple[tuple[Seat, bool], ...]
    # Only the winning team's ordinary meld cards must become public.
    revealed: tuple[RevealedMelds, ...]


@dataclass(frozen=True, slots=True)
class MeldValueAnnouncement:
    player: Seat
    points: int


@dataclass(frozen=True, slots=True)
class SequenceHighAnnouncement:
    player: Seat
    rank: Rank


MeldAnnouncement = MeldValueAnnouncement | SequenceHighAnnouncement


@dataclass(frozen=True, slots=True)
class MeldPresenceAnnouncement:
    player: Seat
    has_meld: bool


@dataclass(frozen=True, slots=True)
class CardsRevealedAnnouncement:
    player: Seat
    cards: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class MeldsFinishedAnnouncement:
    winning_team: int | None
    # Meld cards made public by finishing, e.g. the tracked player's melds.
    implicit_reveals: tuple[CardsRevealedAnnouncement, ...] = ()


RecordedDeclaration = (MeldPresenceAnnouncement | MeldAnnouncement |
                       CardsRevealedAnnouncement | MeldsFinishedAnnouncement)


@dataclass(frozen=True, slots=True)
class BelaAnnouncement:
    player: Seat
    card: Card
    trick_index: int
    position: int


@dataclass(frozen=True, slots=True)
class BelotResult:
    winner: Seat
    revealed_cards: frozenset[Card]
    previous_score: tuple[int, int]

    @property
    def winning_team(self) -> int:
        return self.winner.team
