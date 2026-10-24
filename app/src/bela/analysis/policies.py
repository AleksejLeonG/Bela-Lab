"""Small explicit rollout policies operating only on a player's observation."""

from dataclasses import dataclass
from random import Random

from bela.domain.cards import Card, Rank, deck
from bela.domain.game import PlayerObservation, Trick
from bela.domain.melds import CardsRevealedAnnouncement, MeldsFinishedAnnouncement
from bela.rules.play import card_points, legal_cards, strength, trick_winner


POLICIES = ("random_v1", "simple_v1", "cautious_v1", "counting_v1", "tactical_v1")
MIXED_POLICY = "mixed_match_v1"
ANALYSIS_POLICIES = (MIXED_POLICY, *POLICIES)
# Levels describe intended sophistication, not measured ratings.
PROFILE_NAMES = ("Random", "Basic", "Cautious", "Card counting", "Tactical")
CARDS = deck()


@dataclass(frozen=True, slots=True)
class PolicyMove:
    card: Card
    bela: bool


def announce_bela(view: PlayerObservation, card: Card) -> bool:
    pair = {Card(view.trump, Rank.KING), Card(view.trump, Rank.QUEEN)}
    return not view.bela_announcements and card in pair and pair.issubset(view.hand)


def choose_move(view: PlayerObservation, rng: Random, policy="simple_v1") -> PolicyMove:
    """One of five legal continuation profiles, with random tie breaks.

    All announce timely bela. Basic retains the original simple heuristic;
    cautious, counting and tactical add progressively more public reasoning.
    Strategy identities of the other players are never part of the input.
    """
    if not isinstance(view, PlayerObservation) or view.next_player != view.player:
        raise ValueError("A policy requires only the acting player's observation.")
    if policy not in POLICIES:
        raise ValueError("Unknown continuation policy.")
    legal = legal_cards(view.hand, view.current_trick, view.trump)
    if not legal:
        raise ValueError("The acting player has no legal move.")
    choices = legal
    if policy in ("cautious_v1", "counting_v1", "tactical_v1"):
        choices = _informed_choices(view, legal, policy)
    elif policy == "simple_v1":
        def cost(card):
            return card.suit == view.trump, card_points(card, view.trump), strength(card, view.trump)

        if not view.current_trick.cards:
            aces = tuple(c for c in legal if c.suit != view.trump and c.rank == Rank.ACE)
            if aces:
                choices = aces
            else:
                plain = tuple(c for c in legal if c.suit != view.trump) or legal
                length = {c.suit: sum(other.suit == c.suit for other in view.hand) for c in plain}
                best = min((-length[c.suit], *cost(c)) for c in plain)
                choices = tuple(c for c in plain if (-length[c.suit], *cost(c)) == best)
        elif trick_winner(view.current_trick, view.trump).team == view.player.team:
            best = max(card_points(c, view.trump) for c in legal)
            choices = tuple(c for c in legal if card_points(c, view.trump) == best)
        else:
            winners = tuple(c for c in legal if trick_winner(
                Trick(view.current_trick.leader, view.current_trick.cards + (c,)), view.trump) == view.player)
            pool = winners or legal
            best = min(cost(c) for c in pool)
            choices = tuple(c for c in pool if cost(c) == best)
    card = choices[rng.randrange(len(choices))]
    return PolicyMove(card, announce_bela(view, card))


def _public_context(view):
    """Only public ownership and voids, never the sampled hidden hands."""
    played, known = set(), {}
    voids = [set() for _ in range(4)]
    for trick in (*view.completed_tricks, view.current_trick):
        if not trick.cards:
            continue
        led = trick.cards[0].suit
        for index, card in enumerate(trick.cards):
            played.add(card)
            seat = trick.seat_at(index)
            if card.suit != led:
                voids[seat].add(led)
                if card.suit != view.trump:
                    voids[seat].add(view.trump)
    if view.meld_contest:
        for reveal in view.meld_contest.revealed:
            known.update((card, reveal.player) for card in reveal.cards)
    for record in view.declaration_history:
        records = record.implicit_reveals if isinstance(record, MeldsFinishedAnnouncement) else (record,)
        for reveal in records:
            if isinstance(reveal, CardsRevealedAnnouncement):
                known.update((card, reveal.player) for card in reveal.cards)
    return played, known, voids


def _informed_choices(view, legal, policy):
    """Three progressively richer heuristics; all choices remain legal.

    Cautious avoids donating to an unsecured trick. Counting recognizes public
    outstanding winners and proven voids. Tactical also considers trump control,
    exposed-suit leads and preserving outstanding winners on a losing discard.
    """
    def cost(card):
        return card.suit == view.trump, card_points(card, view.trump), strength(card, view.trump)

    def cheapest(pool):
        best = min(cost(c) for c in pool)
        return tuple(c for c in pool if cost(c) == best)

    if policy == "cautious_v1":
        if not view.current_trick.cards:
            aces = tuple(c for c in legal if c.suit != view.trump and c.rank == Rank.ACE)
            return aces or cheapest(tuple(c for c in legal if c.suit != view.trump) or legal)
        winning = tuple(c for c in legal if trick_winner(
            Trick(view.current_trick.leader, view.current_trick.cards + (c,)), view.trump).team == view.player.team)
        # Fourth to act: no opponent can steal this trick after our card.
        if len(view.current_trick.cards) == 3 and winning:
            best = max(card_points(c, view.trump) for c in winning)
            return tuple(c for c in winning if card_points(c, view.trump) == best)
        return cheapest(winning or legal)

    played, known, voids = _public_context(view)
    unseen = tuple(c for c in CARDS if c not in played and c not in view.hand)

    def master(card):
        return not any(c.suit == card.suit and strength(c, view.trump) > strength(card, view.trump)
                       for c in unseen)

    def possible_cards(seat, led):
        candidates = tuple(c for c in unseen if c.suit not in voids[seat]
                           and (c not in known or known[c] == seat))
        held = tuple(c for c, owner in known.items() if owner == seat and c not in played)
        if len(held) == view.remaining_counts[seat]:
            candidates = held
        # A revealed held card proves a following obligation.
        if any(c.suit == led for c in held):
            candidates = tuple(c for c in candidates if c.suit == led)
        return candidates

    def secure(card):
        trick = Trick(view.current_trick.leader, view.current_trick.cards + (card,))
        winner = trick_winner(trick, view.trump)
        if winner.team != view.player.team:
            return False
        for index in range(len(trick.cards), 4):
            seat = trick.seat_at(index)
            if seat.team == view.player.team:
                continue
            for possible in possible_cards(seat, trick.cards[0].suit):
                # Position does not affect card strength: append a possible
                # challenger to determine whether the current winner survives.
                challenge = Trick(trick.leader, trick.cards + (possible,))
                if trick_winner(challenge, view.trump) != winner:
                    return False
        return True

    if not view.current_trick.cards:
        plain = tuple(c for c in legal if c.suit != view.trump)
        winners = tuple(c for c in plain if master(c))
        if policy == "tactical_v1":
            trumps = tuple(c for c in legal if c.suit == view.trump)
            outside_trumps = tuple(c for c in unseen if c.suit == view.trump)
            # Calling side with length and a master trump can start removing
            # opposing trumps. This is a heuristic, not an optimality claim.
            controlled = tuple(c for c in trumps if master(c))
            if view.player.team == view.caller.team and len(trumps) >= 3 and outside_trumps and controlled:
                return cheapest(controlled)
            safe_winners = tuple(c for c in winners if not any(
                seat % 2 != view.player.team and c.suit in voids[seat] and view.trump not in voids[seat]
                for seat in range(4)))
            if safe_winners:
                return cheapest(safe_winners)
            if plain:
                def lead_cost(c):
                    risk = sum(seat % 2 != view.player.team and c.suit in voids[seat]
                               and view.trump not in voids[seat] for seat in range(4))
                    length = sum(other.suit == c.suit for other in view.hand)
                    return risk, -length, *cost(c)
                best = min(lead_cost(c) for c in plain)
                return tuple(c for c in plain if lead_cost(c) == best)
        return cheapest(winners or plain or legal)

    safe = tuple(c for c in legal if secure(c))
    if safe:
        # When our team is safe, bring points into the trick; among equal-point
        # options preserve trump strength.
        best = min((-card_points(c, view.trump), c.suit == view.trump, strength(c, view.trump)) for c in safe)
        return tuple(c for c in safe if (-card_points(c, view.trump), c.suit == view.trump,
                                         strength(c, view.trump)) == best)
    current_winners = tuple(c for c in legal if trick_winner(
        Trick(view.current_trick.leader, view.current_trick.cards + (c,)), view.trump) == view.player)
    if current_winners:
        return cheapest(current_winners)
    if policy == "tactical_v1":
        expendable = tuple(c for c in legal if not master(c))
        return cheapest(expendable or legal)
    return cheapest(legal)
