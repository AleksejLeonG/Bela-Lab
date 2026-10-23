"""Initial advisor contract: list legal actions, without invented probabilities."""

from dataclasses import dataclass

from bela.domain.cards import Card
from bela.domain.game import PlayerObservation
from bela.rules.play import legal_cards


@dataclass(frozen=True, slots=True)
class Analysis:
    legal_actions: tuple[Card, ...]
    status: str = "legal_actions_only"
    explanation: str = "Statistical ranking is not implemented yet."


def analyze(observation: PlayerObservation) -> Analysis:
    if observation.next_player != observation.player:
        raise ValueError("Analysis requires this player's turn")
    return Analysis(legal_cards(observation.hand, observation.current_trick,
                               observation.trump))
