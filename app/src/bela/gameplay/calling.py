"""Single-round calling, before any player sees their last two cards."""

from dataclasses import dataclass, replace

from bela.domain.cards import Card, Suit
from bela.domain.players import Seat


@dataclass(frozen=True, slots=True)
class CallingState:
    dealer: Seat
    passes: tuple[Seat, ...] = ()
    caller: Seat | None = None
    trump: Suit | None = None

    def __post_init__(self):
        if not isinstance(self.dealer, Seat) or not isinstance(self.passes, tuple):
            raise ValueError("Calling requires a dealer and a tuple of passes.")
        order = tuple(Seat((int(self.dealer) + i) % 4) for i in range(1, 5))
        if (len(self.passes) > 3 or any(not isinstance(s, Seat) for s in self.passes)
                or self.passes != order[:len(self.passes)]):
            raise ValueError("Passes must follow calling order; the dealer cannot pass.")
        if (self.caller is None) != (self.trump is None):
            raise ValueError("Caller and trump must be recorded together.")
        if self.caller is not None and (not isinstance(self.caller, Seat)
                or not isinstance(self.trump, Suit) or self.caller != order[len(self.passes)]):
            raise ValueError("Only the next player may call trump.")

    @property
    def next_player(self) -> Seat | None:
        return None if self.caller is not None else Seat((int(self.dealer) + 1 + len(self.passes)) % 4)

    @property
    def forced(self) -> bool:
        return self.caller is None and len(self.passes) == 3

    def _check_turn(self, player):
        if not isinstance(player, Seat) or self.next_player is None or player != self.next_player:
            raise ValueError("It is not this player's calling turn.")

    def pass_turn(self, player: Seat) -> "CallingState":
        self._check_turn(player)
        if self.forced:
            raise ValueError("The dealer must call after three passes.")
        return replace(self, passes=self.passes + (player,))

    def call_trump(self, player: Seat, trump: Suit) -> "CallingState":
        self._check_turn(player)
        if not isinstance(trump, Suit):
            raise ValueError("Choose a valid trump suit.")
        return replace(self, caller=player, trump=trump)


@dataclass(frozen=True, slots=True)
class CallingObservation:
    """Exactly six private cards and public calling history; no talon input."""

    player: Seat
    hand: tuple[Card, ...]
    state: CallingState

    def __post_init__(self):
        if (not isinstance(self.state, CallingState) or not isinstance(self.player, Seat)
                or self.state.next_player != self.player):
            raise ValueError("A calling observation requires the acting player.")
        if (not isinstance(self.hand, tuple) or len(self.hand) != 6
                or any(not isinstance(c, Card) for c in self.hand) or len(set(self.hand)) != 6):
            raise ValueError("Calling uses exactly six distinct visible cards, before talon pickup.")
