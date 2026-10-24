"""Simulator from talon pickup through declarations and the final result."""

from collections.abc import Iterable
from dataclasses import replace

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, PlayerObservation, PlayState, Seat, Trick
from bela.domain.melds import (BelaAnnouncement, BelotResult, MeldKind,
                              MeldValueAnnouncement, SequenceHighAnnouncement)
from bela.rules.melds import detect_melds, has_belot, resolve_meld_contest
from bela.rules.play import card_points, legal_cards, trick_winner
from bela.rules.scoring import DealResult, settle_deal


def start_play(
    hands: Iterable[Iterable[Card]], *, trump: Suit, dealer: Seat, caller: Seat,
    match_score: tuple[int, int] = (0, 0),
) -> PlayState:
    raw = tuple(tuple(hand) for hand in hands)
    if len(raw) != 4 or any(len(hand) != 8 for hand in raw):
        raise ValueError("Start play with four hands of eight cards")
    if any(not isinstance(card, Card) for hand in raw for card in hand):
        raise ValueError("Hands must contain Card objects")
    if set(card for hand in raw for card in hand) != set(deck()):
        raise ValueError("Hands must contain all 32 cards exactly once")
    if not isinstance(trump, Suit) or not all(isinstance(s, Seat) for s in (dealer, caller)):
        raise ValueError("Expected a Suit and Seat values")
    if (not isinstance(match_score, tuple) or len(match_score) != 2
            or any(type(n) is not int or n < 0 for n in match_score)):
        raise ValueError("Expected two nonnegative match scores")
    return PlayState(tuple(frozenset(hand) for hand in raw), trump, dealer, caller,
                     match_score, Trick(dealer.next))


def observe(state: PlayState, player: Seat) -> PlayerObservation:
    if not isinstance(player, Seat):
        raise ValueError("Expected a Seat")
    return PlayerObservation(player, state.hands[player], state.trump, state.dealer,
                             state.caller, state.match_score, state.current_trick,
                             state.completed_tricks, tuple(map(len, state.hands)),
                             state.next_player, state.phase, state.meld_contest,
                             state.meld_announcements, state.bela_announcements, state.belot,
                             state.declaration_history)


def _declaration_phase(state: PlayState) -> None:
    if state.phase != Phase.DECLARATIONS:
        raise ValueError("Declarations must occur before play")


def _declaring_hand(state: PlayState, player: Seat) -> frozenset[Card]:
    _declaration_phase(state)
    if not isinstance(player, Seat):
        raise ValueError("Expected a Seat")
    return state.hands[player]


def announce_meld_value(state: PlayState, player: Seat) -> PlayState:
    """Record a spoken strongest value, without exposing kind or exact cards.

    Call only for comparisons that were actually spoken. The interactive
    question/answer turn order will belong to the future session module.
    """
    melds = detect_melds(_declaring_hand(state, player))
    if not melds:
        raise ValueError("This player has no ordinary meld to announce")
    if any(isinstance(a, MeldValueAnnouncement) and a.player == player
           for a in state.meld_announcements):
        raise ValueError("This player's value is already public")
    return replace(state, meld_announcements=state.meld_announcements + (
        MeldValueAnnouncement(player, melds[0].points),))


def announce_sequence_high(state: PlayState, player: Seat) -> PlayState:
    """Record the endpoint of a strongest sequence during a spoken comparison."""
    melds = detect_melds(_declaring_hand(state, player))
    if not melds or melds[0].kind != MeldKind.SEQUENCE:
        raise ValueError("This player's strongest meld is not a sequence")
    if not any(isinstance(a, MeldValueAnnouncement) and a.player == player
               for a in state.meld_announcements):
        raise ValueError("Announce the value before its endpoint")
    if any(isinstance(a, SequenceHighAnnouncement) and a.player == player
           for a in state.meld_announcements):
        raise ValueError("This player's endpoint is already public")
    return replace(state, meld_announcements=state.meld_announcements + (
        SequenceHighAnnouncement(player, melds[0].high_rank),))


def resolve_declarations(state: PlayState) -> PlayState:
    """Complete truthful declarations and show all winning-team melds.

    Losing hands and unspoken details remain private. The summary contains
    mandatory presence announcements in order, plus only winning-team reveals.
    """
    _declaration_phase(state)
    contest = resolve_meld_contest(state.hands, state.dealer)
    return replace(state, phase=Phase.PLAYING, meld_contest=contest)


def declare_belot(state: PlayState, player: Seat) -> PlayState:
    """The actual declaration ends the match immediately, without point credit."""
    hand = _declaring_hand(state, player)
    if not has_belot(hand):
        raise ValueError("Belot requires all eight cards of one suit")
    result = BelotResult(player, hand, state.match_score)
    return replace(state, phase=Phase.MATCH_FINISHED, belot=result)


def play_card(state: PlayState, player: Seat, card: Card, *,
              announce_bela: bool = False) -> PlayState:
    if not isinstance(player, Seat):
        raise ValueError("Expected a Seat")
    if state.phase != Phase.PLAYING:
        raise ValueError("Cards can only be played after declarations and before the end")
    if type(announce_bela) is not bool:
        raise ValueError("Bela announcement must be a boolean")
    if player != state.next_player:
        raise ValueError("Player is out of turn")
    if card not in legal_cards(state.hands[player], state.current_trick, state.trump):
        raise ValueError(f"Illegal card: {card}")
    bela = state.bela_announcements
    if announce_bela:
        pair = frozenset((Card(state.trump, Rank.KING), Card(state.trump, Rank.QUEEN)))
        if card not in pair or not pair.issubset(state.hands[player]):
            raise ValueError("Announce bela on the first trump K/Q while holding both")
        if bela:
            raise ValueError("Bela has already been announced")
        bela += (BelaAnnouncement(player, card, len(state.completed_tricks),
                                  len(state.current_trick.cards)),)
    hands = list(state.hands)
    hands[player] = hands[player] - {card}
    trick = Trick(state.current_trick.leader, state.current_trick.cards + (card,))
    if len(trick.cards) == 4:
        winner = trick_winner(trick, state.trump)
        completed = state.completed_tricks + (trick,)
        return replace(state, hands=tuple(hands), current_trick=Trick(winner),
                       completed_tricks=completed, bela_announcements=bela,
                       phase=Phase.DEAL_FINISHED if len(completed) == 8 else Phase.PLAYING)
    return replace(state, hands=tuple(hands), current_trick=trick, bela_announcements=bela)


def settle_play(state: PlayState) -> DealResult | BelotResult:
    """Return a special belot victory or settle all eight tricks and declarations."""
    if state.belot is not None:
        return state.belot
    if state.phase != Phase.DEAL_FINISHED:
        raise ValueError("Finish all eight tricks before settlement")
    points, counts = [0, 0], [0, 0]
    for trick in state.completed_tricks:
        team = trick_winner(trick, state.trump).team
        points[team] += sum(card_points(card, state.trump) for card in trick.cards)
        counts[team] += 1
    bela_points = [0, 0]
    for announcement in state.bela_announcements:
        bela_points[announcement.player.team] += 20
    return settle_deal(card_points=tuple(points), trick_counts=tuple(counts),
                       last_trick_team=trick_winner(state.completed_tricks[-1], state.trump).team,
                       caller_team=state.caller.team,
                       awarded_melds=state.meld_contest.awarded_points,
                       announced_bela=tuple(bela_points))
