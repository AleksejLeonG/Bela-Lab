from dataclasses import dataclass
from enum import Enum

from bela.domain.cards import Card, Suit
from bela.domain.melds import BelaAnnouncement, BelotResult, MeldAnnouncement, MeldContest
from bela.domain.players import Seat


class Phase(str, Enum):
    DECLARATIONS = "declarations"
    PLAYING = "playing"
    DEAL_FINISHED = "deal_finished"
    MATCH_FINISHED = "match_finished"


@dataclass(frozen=True, slots=True)
class Trick:
    """Cards in play order; ownership follows increasing seat indices.

    Seat indices advance in the agreed counterclockwise physical play direction.
    """

    leader: Seat
    cards: tuple[Card, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.leader, Seat) or not isinstance(self.cards, tuple):
            raise ValueError("Trick requires a Seat and a tuple of cards")
        if len(self.cards) > 4 or len(set(self.cards)) != len(self.cards):
            raise ValueError("A trick contains at most four distinct cards")

    def seat_at(self, index: int) -> Seat:
        if not 0 <= index < 4:
            raise ValueError("Trick index must be between 0 and 3")
        return Seat((int(self.leader) + index) % 4)

    @property
    def next_player(self) -> Seat:
        if len(self.cards) == 4:
            raise ValueError("A completed trick has no next player")
        return self.seat_at(len(self.cards))


@dataclass(frozen=True, slots=True)
class PlayState:
    """Complete simulator state after talon pickup and trump selection.

    Construct through simulation.start_play; do not pass this to a policy.
    Declarations must be resolved (or belot declared) before the first card.
    Bidding and session revisions are not implemented yet.
    """

    hands: tuple[frozenset[Card], ...]
    trump: Suit
    dealer: Seat
    caller: Seat
    match_score: tuple[int, int]
    current_trick: Trick
    completed_tricks: tuple[Trick, ...] = ()
    phase: Phase = Phase.DECLARATIONS
    meld_contest: MeldContest | None = None
    meld_announcements: tuple[MeldAnnouncement, ...] = ()
    bela_announcements: tuple[BelaAnnouncement, ...] = ()
    belot: BelotResult | None = None

    @property
    def finished(self) -> bool:
        return self.phase in (Phase.DEAL_FINISHED, Phase.MATCH_FINISHED)

    @property
    def next_player(self) -> Seat | None:
        return self.current_trick.next_player if self.phase == Phase.PLAYING else None


@dataclass(frozen=True, slots=True)
class PlayerObservation:
    """Public play history plus exactly one player's private hand.

    Public declaration records include only what was announced or shown.
    """

    player: Seat
    hand: frozenset[Card]
    trump: Suit
    dealer: Seat
    caller: Seat
    match_score: tuple[int, int]
    current_trick: Trick
    completed_tricks: tuple[Trick, ...]
    remaining_counts: tuple[int, ...]
    next_player: Seat | None
    phase: Phase
    meld_contest: MeldContest | None
    meld_announcements: tuple[MeldAnnouncement, ...]
    bela_announcements: tuple[BelaAnnouncement, ...]
    belot: BelotResult | None
