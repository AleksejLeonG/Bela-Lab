"""Real-game tracking from one player's information, without invented hands.

Ownership domains and an existential constraint check validate observations.
Any complete allocation used by the validator is transient, never game data.
"""

from dataclasses import dataclass, replace
from functools import lru_cache
from uuid import uuid4

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, Seat, Trick
from bela.domain.melds import BelaAnnouncement, BelotResult
from bela.analysis.knowledge import EvidenceBuilder, KnowledgeEvidence, Reason
from bela.rules.melds import detect_melds, has_belot
from bela.rules.play import card_points, legal_cards, strength, trick_winner, winning_index
from bela.rules.scoring import DealResult, match_winner, settle_deal
from bela.analysis.validation import MeldConstraint, ValidationLimit, allocation_exists as _allocation_exists


class InconsistentInput(ValueError):
    """No legal game can explain the supplied observations."""


@dataclass(frozen=True, slots=True)
class DealSetup:
    player: Seat
    hand: tuple[Card, ...]
    dealer: Seat
    caller: Seat
    trump: Suit
    match_score: tuple[int, int] = (0, 0)

    def __post_init__(self):
        if not all(isinstance(s, Seat) for s in (self.player, self.dealer, self.caller)):
            raise ValueError("Player seats must be 0–3.")
        if not isinstance(self.trump, Suit):
            raise ValueError("Invalid trump.")
        if (not isinstance(self.hand, tuple) or len(self.hand) != 8
                or any(not isinstance(c, Card) for c in self.hand) or len(set(self.hand)) != 8):
            raise ValueError("Enter exactly eight distinct starting cards.")
        if (not isinstance(self.match_score, tuple) or len(self.match_score) != 2
                or any(type(n) is not int or n < 0 for n in self.match_score)):
            raise ValueError("The score must contain two nonnegative integers.")
        if match_winner(self.match_score) is not None:
            raise ValueError("The match had already ended before this deal.")


@dataclass(frozen=True, slots=True)
class Presence:
    player: Seat
    has_meld: bool


@dataclass(frozen=True, slots=True)
class MeldValue:
    player: Seat
    points: int


@dataclass(frozen=True, slots=True)
class SequenceHigh:
    player: Seat
    rank: Rank


@dataclass(frozen=True, slots=True)
class Reveal:
    player: Seat
    cards: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class FinishDeclarations:
    winning_team: int | None


@dataclass(frozen=True, slots=True)
class Play:
    player: Seat
    card: Card
    bela: bool = False


@dataclass(frozen=True, slots=True)
class Belot:
    player: Seat
    cards: tuple[Card, ...] = ()


Event = Presence | MeldValue | SequenceHigh | Reveal | FinishDeclarations | Play | Belot


@dataclass(frozen=True, slots=True)
class TrackedState:
    setup: DealSetup
    hand: frozenset[Card]
    current_trick: Trick
    completed_tricks: tuple[Trick, ...]
    phase: Phase
    revealed: tuple[frozenset[Card], ...]
    remaining_counts: tuple[int, ...]
    trick_points: tuple[int, int]
    trick_counts: tuple[int, int]
    awarded_melds: tuple[int, int]
    bela_announcements: tuple[BelaAnnouncement, ...]
    result: DealResult | BelotResult | None
    evidence: KnowledgeEvidence

    @property
    def next_player(self) -> Seat | None:
        return self.current_trick.next_player if self.phase == Phase.PLAYING else None

    @property
    def legal_actions(self) -> tuple[Card, ...]:
        if self.next_player != self.setup.player:
            return ()
        return legal_cards(self.hand, self.current_trick, self.setup.trump)

    @property
    def score(self) -> tuple[int, int]:
        if isinstance(self.result, DealResult):
            return tuple(a + b for a, b in zip(self.setup.match_score, self.result.recorded))
        return self.setup.match_score

    @property
    def winner(self) -> int | None:
        if isinstance(self.result, BelotResult):
            return self.result.winning_team
        return match_winner(self.score) if self.result is not None else None


def _seat(player):
    if not isinstance(player, Seat):
        raise ValueError("Invalid player seat.")


def _cards(cards):
    if (not isinstance(cards, tuple) or not 1 <= len(cards) <= 8
            or any(not isinstance(c, Card) for c in cards) or len(set(cards)) != len(cards)):
        raise ValueError("Reveal 1–8 distinct cards.")


@lru_cache(maxsize=256)
def replay_deal(setup: DealSetup, events: tuple[Event, ...]) -> TrackedState:
    """Rebuild public state and prove that at least one legal hidden deal exists."""
    if not isinstance(setup, DealSetup) or not isinstance(events, tuple) or len(events) > 96:
        raise ValueError("Invalid deal record.")
    domains = [15 & ~(1 << setup.player)] * 32
    for card in setup.hand:
        domains[card.id] = 1 << setup.player
    evidence = EvidenceBuilder(setup, domains)
    hand, shown, played = set(setup.hand), [set() for _ in Seat], set()
    presence, values, highs = {}, {}, {}
    trick, completed = Trick(setup.dealer.next), []
    points, counts, remaining = [0, 0], [0, 0], [8] * 4
    bela, awarded, expected_melds = [], [0, 0], None
    phase, result = Phase.DECLARATIONS, None
    winner_key = winner_priority = None

    def force(card, player, reason=None):
        if not domains[card.id] & (1 << player):
            raise InconsistentInput(f"Card {card} cannot belong to player {int(player)} given the recorded history.")
        domains[card.id] = 1 << player
        evidence.force(card, player, reason or Reason("played", int(player), (event_index,)))

    def exclude(player, predicate, reason):
        targets = [card for card in deck() if card not in played and predicate(card)]
        if targets:
            evidence.deduce(reason)
        for card in targets:
            domains[card.id] &= ~(1 << player)
            evidence.exclude(card, player, reason)
            if not domains[card.id]:
                raise InconsistentInput(f"The move contradicts known ownership of card {card}.")

    for event_index, event in enumerate(events):
        try:
            if hasattr(event, "player"):
                _seat(event.player)
            if phase in (Phase.DEAL_FINISHED, Phase.MATCH_FINISHED):
                raise ValueError("The deal has ended; correct an earlier event or start the next deal.")
            if isinstance(event, Play):
                if phase != Phase.PLAYING:
                    raise ValueError("Finish declarations first with 'melds none' or 'melds 0/1'.")
                if event.player != trick.next_player:
                    raise ValueError(f"Player to act: {int(trick.next_player)}.")
                if not isinstance(event.card, Card) or type(event.bela) is not bool:
                    raise ValueError("Invalid card or bela announcement.")
                card, player = event.card, event.player
                if card in played:
                    raise ValueError(f"Card {card} has already been played.")
                force(card, player)
                if player == setup.player and card not in legal_cards(hand, trick, setup.trump):
                    raise ValueError(f"Card {card} is not legal from your hand.")
                if trick.cards:
                    led = trick.cards[0].suit
                    winning = trick.cards[winning_index(trick, setup.trump)]
                    if card.suit != led:
                        exclude(player, lambda c: c.suit == led,
                                Reason("void_suit", int(player), (event_index,), led.value))
                        if card.suit != setup.trump:
                            exclude(player, lambda c: c.suit == setup.trump,
                                    Reason("void_suit", int(player), (event_index,), setup.trump.value))
                    if (card.suit == winning.suit
                            and (card.suit == led or card.suit == setup.trump)
                            and strength(card, setup.trump) <= strength(winning, setup.trump)):
                        exclude(player, lambda c: c.suit == winning.suit
                                and strength(c, setup.trump) > strength(winning, setup.trump),
                                Reason("no_higher", int(player), (event_index,), winning.suit.value, str(winning)))
                if event.bela:
                    pair = {Card(setup.trump, Rank.KING), Card(setup.trump, Rank.QUEEN)}
                    if bela or card not in pair or pair & played:
                        raise ValueError("Announce bela only with the first trump K/Q while holding both cards.")
                    for other in pair:
                        force(other, player, Reason("bela_pair", int(player), (event_index,),
                                                   cards=tuple(sorted(map(str, pair)))))
                    evidence.deduce(Reason("bela_pair", int(player), (event_index,),
                                           cards=tuple(sorted(map(str, pair)))))
                    bela.append(BelaAnnouncement(player, card, len(completed), len(trick.cards)))
                played.add(card)
                remaining[player] -= 1
                if player == setup.player:
                    hand.remove(card)
                trick = Trick(trick.leader, trick.cards + (card,))
                if len(trick.cards) == 4:
                    winner = trick_winner(trick, setup.trump)
                    points[winner.team] += sum(card_points(c, setup.trump) for c in trick.cards)
                    counts[winner.team] += 1
                    completed.append(trick)
                    trick = Trick(winner)
                    if len(completed) == 8:
                        phase = Phase.DEAL_FINISHED
                        bela_points = [0, 0]
                        for call in bela:
                            bela_points[call.player.team] += 20
                        result = settle_deal(card_points=tuple(points), trick_counts=tuple(counts),
                                             last_trick_team=winner.team, caller_team=setup.caller.team,
                                             awarded_melds=tuple(awarded), announced_bela=tuple(bela_points))
                continue
            if phase != Phase.DECLARATIONS:
                raise ValueError("Enter ordinary meld declarations and reveals before the first card; "
                                 "correct the history to add missing information.")
            if isinstance(event, Presence):
                if type(event.has_meld) is not bool or event.player in presence:
                    raise ValueError("Invalid or repeated meld presence declaration.")
                presence[event.player] = event.has_meld
            elif isinstance(event, MeldValue):
                if type(event.points) is not int or event.points not in (20, 50, 100, 150, 200) or event.player in values:
                    raise ValueError("The strongest meld must be 20, 50, 100, 150 or 200; enter it once.")
                values[event.player] = event.points
                if event.points in (150, 200):
                    rank = Rank.NINE if event.points == 150 else Rank.JACK
                    for suit in Suit:
                        force(Card(suit, rank), event.player,
                              Reason("announced_quad", int(event.player), (event_index,),
                                     cards=tuple(str(Card(s, rank)) for s in Suit)))
                    evidence.deduce(Reason("announced_quad", int(event.player), (event_index,),
                                           cards=tuple(str(Card(s, rank)) for s in Suit)))
            elif isinstance(event, SequenceHigh):
                if not isinstance(event.rank, Rank) or event.player not in values or event.player in highs:
                    raise ValueError("Enter the meld value first, then its high card once.")
                minimum = {20: Rank.NINE, 50: Rank.TEN, 100: Rank.JACK}.get(values[event.player])
                if minimum is None or tuple(Rank).index(event.rank) < tuple(Rank).index(minimum):
                    raise ValueError("That high card is impossible for the declared sequence value.")
                highs[event.player] = event.rank
            elif isinstance(event, Reveal):
                _cards(event.cards)
                for card in event.cards:
                    force(card, event.player, Reason("revealed", int(event.player), (event_index,)))
                shown[event.player].update(event.cards)
            elif isinstance(event, FinishDeclarations):
                if event.winning_team is not None and (type(event.winning_team) is not int or event.winning_team not in (0, 1)):
                    raise ValueError("The winning team must be 0, 1 or no melds.")
                expected_melds = {}
                candidates = []
                order = [Seat((int(setup.dealer) + offset) % 4) for offset in range(1, 5)]
                for player in order:
                    if player.team != event.winning_team:
                        continue
                    known = set(setup.hand) if player == setup.player else shown[player]
                    if has_belot(known):
                        raise ValueError("Declare eight cards of one suit as belot.")
                    melds = detect_melds(known)
                    expected_melds[player] = melds
                    for meld in melds:
                        shown[player].update(meld.cards)
                        for card in meld.cards:
                            evidence.force(card, player, Reason("revealed", int(player), (event_index,)))
                    if melds:
                        candidates.append((melds[0].strength_key, -order.index(player)))
                        awarded[player.team] += sum(m.points for m in melds)
                if event.winning_team is not None and not candidates:
                    raise ValueError("Reveal all melds of the winning team before finishing declarations.")
                if candidates:
                    winner_key, winner_priority = max(candidates)
                phase = Phase.PLAYING
            elif isinstance(event, Belot):
                known = event.cards or (setup.hand if event.player == setup.player else tuple(shown[event.player]))
                _cards(known)
                if not has_belot(known):
                    raise ValueError("Belot requires revealing all eight cards of one suit.")
                for card in known:
                    force(card, event.player, Reason("belot", int(event.player), (event_index,)))
                shown[event.player].update(known)
                result = BelotResult(event.player, frozenset(known), setup.match_score)
                phase = Phase.MATCH_FINISHED
            else:
                raise ValueError("Unknown event type.")
        except ValueError as error:
            raise InconsistentInput(f"Event {event_index + 1}: {error}") from error

    def check_for(player):
        exact = None
        if expected_melds is not None and player in expected_melds:
            exact = tuple(sorted((meld.kind.value, sum(1 << card.id for card in meld.cards))
                                 for meld in expected_melds[player]))
        losing = expected_melds is not None and player not in expected_melds
        priority = -((int(player) - int(setup.dealer) - 1) % 4)
        return MeldConstraint(
            presence=presence.get(player), points=values.get(player),
            high=tuple(Rank).index(highs[player]) if player in highs else None,
            exact=exact, no_belot=expected_melds is not None,
            no_melds=losing and winner_key is None,
            ceiling=winner_key if losing else None,
            strict_ceiling=losing and winner_key is not None and priority > winner_priority)

    constrained = set(presence) | set(values) | set(highs)
    if expected_melds is not None:
        constrained.update(Seat)
    checks = {player: check_for(player) for player in constrained}
    if not _allocation_exists(domains, checks):
        raise InconsistentInput("No card distribution satisfies all moves, melds "
                                "and reveals. Check the last event or correct the history.")
    return TrackedState(setup, frozenset(hand), trick, tuple(completed), phase,
                        tuple(frozenset(cards) for cards in shown), tuple(remaining),
                        tuple(points), tuple(counts), tuple(awarded), tuple(bela), result,
                        evidence.freeze(domains, checks))


@dataclass(frozen=True, slots=True)
class TrackedDeal:
    setup: DealSetup
    events: tuple[Event, ...] = ()

    @property
    def state(self):
        return replay_deal(self.setup, self.events)


@dataclass(frozen=True, slots=True)
class AddEvent:
    event: Event


@dataclass(frozen=True, slots=True)
class ReplaceEvent:
    index: int
    event: Event


@dataclass(frozen=True, slots=True)
class InsertEvent:
    index: int
    event: Event


@dataclass(frozen=True, slots=True)
class DeleteEvent:
    index: int


@dataclass(frozen=True, slots=True)
class ReplaceSetup:
    setup: DealSetup


@dataclass(frozen=True, slots=True)
class NextDeal:
    setup: DealSetup


Command = AddEvent | ReplaceEvent | InsertEvent | DeleteEvent | ReplaceSetup | NextDeal


@dataclass(frozen=True, slots=True)
class UserMatch:
    id: str
    name: str
    initial: DealSetup
    commands: tuple[Command, ...] = ()

    @classmethod
    def start(cls, setup: DealSetup, name="My match"):
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Match name must contain 1–200 characters.")
        match = cls(str(uuid4()), name, setup)
        materialize(match)
        return match

    @property
    def deals(self) -> tuple[TrackedDeal, ...]:
        return materialize(self)

    @property
    def state(self) -> TrackedState:
        return self.deals[-1].state

    @property
    def revision(self) -> int:
        return len(self.commands)

    def perform(self, command: Command):
        candidate = replace(self, commands=self.commands + (command,))
        materialize(candidate)
        return candidate


@lru_cache(maxsize=128)
def materialize(match: UserMatch) -> tuple[TrackedDeal, ...]:
    if len(match.commands) > 10_000:
        raise ValueError("The match has too many revisions.")
    deals = [TrackedDeal(match.initial)]
    deals[0].state
    for revision, command in enumerate(match.commands, 1):
        current = deals[-1]
        try:
            if isinstance(command, AddEvent):
                current = replace(current, events=current.events + (command.event,))
            elif isinstance(command, InsertEvent):
                if type(command.index) is not int or not 0 <= command.index <= len(current.events):
                    raise ValueError("No insertion position exists at that index.")
                current = replace(current, events=current.events[:command.index] + (command.event,)
                                  + current.events[command.index:])
            elif isinstance(command, (ReplaceEvent, DeleteEvent)):
                if type(command.index) is not int or not 0 <= command.index < len(current.events):
                    raise ValueError("No event exists at that index.")
                replacement = (command.event,) if isinstance(command, ReplaceEvent) else ()
                current = replace(current, events=current.events[:command.index] + replacement
                                  + current.events[command.index + 1:])
            elif isinstance(command, ReplaceSetup):
                current = replace(current, setup=command.setup)
            elif isinstance(command, NextDeal):
                if current.state.result is None or current.state.winner is not None:
                    raise ValueError("Start the next deal only after the current deal finishes and before the match has a winner.")
                deals.append(TrackedDeal(command.setup))
                current = deals[-1]
            else:
                raise ValueError("Unknown change.")
            if current.setup.player != match.initial.player:
                raise ValueError("The user's seat must stay the same throughout the match.")
            if len(deals) > 1:
                previous = deals[-2].state
                if (current.setup.match_score != previous.score
                        or current.setup.dealer != previous.setup.dealer.next):
                    raise ValueError("Score and dealer must follow the previous deal.")
            current.state
            deals[-1] = current
        except ValidationLimit:
            raise
        except ValueError as error:
            raise InconsistentInput(f"Revision {revision}: {error}") from error
    return tuple(deals)
