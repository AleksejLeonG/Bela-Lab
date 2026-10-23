"""A match archive: completed deals and one current deal, with derived scores."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from uuid import uuid4

from bela.domain.cards import Card, Suit
from bela.domain.game import PlayState, Seat
from bela.domain.melds import BelotResult
from bela.rules.scoring import match_winner
from bela.simulation import settle_play, start_play


def initial_hands(state: PlayState) -> tuple[tuple[Card, ...], ...]:
    """Recover dealt hands from remaining cards and their recorded owners."""
    hands = [list(hand) for hand in state.hands]
    for trick in (*state.completed_tricks, state.current_trick):
        for index, card in enumerate(trick.cards):
            hands[trick.seat_at(index)].append(card)
    return tuple(tuple(sorted(hand, key=lambda card: card.id)) for hand in hands)


@dataclass(frozen=True, slots=True)
class MatchSession:
    id: str
    name: str
    deals: tuple[PlayState, ...]

    @classmethod
    def start(cls, state: PlayState, *, name: str = "Bela match") -> "MatchSession":
        if not isinstance(state, PlayState):
            raise ValueError("A match needs a PlayState")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Match name must contain 1–200 characters")
        return cls(str(uuid4()), name, (state,))

    @property
    def current(self) -> PlayState:
        return self.deals[-1]

    @property
    def score(self) -> tuple[int, int]:
        state = self.current
        if not state.finished:
            return state.match_score
        result = settle_play(state)
        if isinstance(result, BelotResult):
            return state.match_score
        return tuple(a + b for a, b in zip(state.match_score, result.recorded))

    @property
    def winner(self) -> int | None:
        if not self.current.finished:
            return None
        result = settle_play(self.current)
        return result.winning_team if isinstance(result, BelotResult) else match_winner(self.score)

    def with_current(self, state: PlayState) -> "MatchSession":
        """Replace the current checkpoint; prior deals stay untouched."""
        previous = self.current
        if not isinstance(state, PlayState) or (
            state.trump, state.dealer, state.caller, state.match_score, initial_hands(state)
        ) != (
            previous.trump, previous.dealer, previous.caller,
            previous.match_score, initial_hands(previous)
        ):
            raise ValueError("The checkpoint must belong to the same deal")
        return replace(self, deals=self.deals[:-1] + (state,))

    def next_deal(self, hands: Iterable[Iterable[Card]], *, trump: Suit,
                  caller: Seat) -> "MatchSession":
        if not self.current.finished:
            raise ValueError("Finish the current deal before starting the next")
        if self.winner is not None:
            raise ValueError("The match already has a winner")
        state = start_play(hands, trump=trump, dealer=self.current.dealer.next,
                           caller=caller, match_score=self.score)
        return replace(self, deals=self.deals + (state,))
