"""Latent strategy lineups, assigned once per hypothetical complete match.

These are simulation assumptions, never facts about real players. Policies see
only their own observation. The lineup belongs to the simulator, not the view.
"""

from dataclasses import dataclass, replace
from hashlib import sha256
from random import Random

from bela.analysis.policies import POLICIES, choose_move
from bela.domain.game import Seat
from bela.gameplay.session import MatchSession
from bela.gameplay.simulation import observe, play_card


@dataclass(frozen=True)
class StrategyLineup:
    player: Seat
    seed: int
    policies: tuple[str, str, str, str]

    def __post_init__(self):
        if not isinstance(self.player, Seat) or type(self.seed) is not int or self.seed < 0:
            raise ValueError("A lineup needs a player seat and nonnegative seed.")
        if (not isinstance(self.policies, tuple) or len(self.policies) != 4
                or any(policy not in POLICIES for policy in self.policies)):
            raise ValueError("A lineup needs four valid concrete strategies.")

    @classmethod
    def assign(cls, player, seed, *, self_policy="tactical_v1"):
        if not isinstance(player, Seat) or type(seed) is not int or seed < 0 or self_policy not in POLICIES:
            raise ValueError("Invalid strategy assignment settings.")
        rng = Random(seed)
        return cls(player, seed, tuple(self_policy if seat == player else rng.choice(POLICIES)
                                       for seat in Seat))

    @classmethod
    def for_trial(cls, match_id, seed, trial, player):
        """Same virtual match index keeps its lineup across deals and revisions.

        A separate deterministic seed stream keeps assignments independent of
        rejection counts, deal numbers, card contents and rollout tie breaks.
        """
        if not isinstance(match_id, str) or type(seed) is not int or seed < 0 or type(trial) is not int or trial < 0:
            raise ValueError("Invalid hypothetical match identity.")
        digest = sha256(f"lineup-v1:{match_id}:{seed}:{trial}".encode()).digest()
        return cls.assign(player, int.from_bytes(digest[:16], "big"))

    def for_player(self, player):
        if not isinstance(player, Seat):
            raise ValueError("Expected a player seat.")
        return self.policies[player]


@dataclass(frozen=True)
class StrategyMatch:
    """Full-simulator session plus one persistent, hidden strategy assignment.

    Replacing a checkpoint or advancing to the next deal never redraws profiles.
    A fresh start creates a new match assignment. Rules for >1000 and belot stay
    in MatchSession. This wrapper does not choose trump or generate future deals.
    """

    session: MatchSession
    lineup: StrategyLineup

    @classmethod
    def start(cls, state, *, player, seed, name="Strategy simulation"):
        return cls(MatchSession.start(state, name=name), StrategyLineup.assign(player, seed))

    def with_current(self, state):
        return replace(self, session=self.session.with_current(state))

    @property
    def current(self):
        return self.session.current

    @property
    def score(self):
        return self.session.score

    @property
    def winner(self):
        return self.session.winner

    def next_deal(self, hands, *, trump, caller):
        return replace(self, session=self.session.next_deal(hands, trump=trump, caller=caller))

    def play_next(self, rng):
        state = self.session.current
        view = observe(state, state.next_player)
        move = choose_move(view, rng, self.lineup.for_player(view.player))
        return self.with_current(play_card(state, view.player, move.card, announce_bela=move.bela))
