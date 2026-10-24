"""Explainable knowledge from the player's permitted evidence, never witnesses."""

from dataclasses import asdict, dataclass
from functools import lru_cache
from time import monotonic

from bela.domain.cards import Suit, deck
from bela.analysis.validation import MeldConstraint, ValidationLimit, allocation_exists


@dataclass(frozen=True)
class Reason:
    kind: str
    player: int
    events: tuple[int, ...] = ()
    suit: str | None = None
    threshold: str | None = None
    cards: tuple[str, ...] = ()
    includes_setup: bool = False


@dataclass(frozen=True)
class KnowledgeEvidence:
    domains: tuple[int, ...]
    constraints: tuple[tuple[int, MeldConstraint], ...]
    exclusions: tuple[tuple[Reason | None, ...], ...]
    origins: tuple[Reason | None, ...]
    deductions: tuple[Reason, ...]


class EvidenceBuilder:
    """Record the reasons for the existing replay's ownership changes."""

    def __init__(self, setup, domains):
        reason = Reason("starting_hand", int(setup.player))
        self.exclusions = [[None if mask & (1 << seat) else reason for seat in range(4)] for mask in domains]
        self.origins = [reason if mask == 1 << setup.player else None for mask in domains]
        self.deductions = []

    def force(self, card, player, reason):
        previous = self.origins[card.id]
        if previous is None or previous.kind not in ("revealed", "belot"):
            self.origins[card.id] = reason
        for seat in range(4):
            if seat != player and self.exclusions[card.id][seat] is None:
                self.exclusions[card.id][seat] = reason

    def exclude(self, card, player, reason):
        if self.exclusions[card.id][player] is None:
            self.exclusions[card.id][player] = reason

    def deduce(self, reason):
        signature = lambda r: (r.kind, r.player, r.suit, r.threshold, r.cards)
        if not any(signature(old) == signature(reason) for old in self.deductions):
            self.deductions.append(reason)

    def freeze(self, domains, checks):
        return KnowledgeEvidence(tuple(domains), tuple(sorted(checks.items())),
                                 tuple(tuple(row) for row in self.exclusions),
                                 tuple(self.origins), tuple(self.deductions))


@lru_cache(maxsize=8192)
def _owner_possible(domains, constraints, card_id, seat):
    narrowed = list(domains)
    narrowed[card_id] &= 1 << seat
    # Exceptions are not memoized: a later refresh can retry unfinished checks.
    return allocation_exists(narrowed, dict(constraints), seconds=0.05, max_nodes=8000)


def knowledge_view(match, *, seconds=0.75):
    """Return exact ownership support, reasons and explicitly unfinished checks."""
    from bela.storage.user_storage import event_data

    deal, state = match.deals[-1], match.state
    evidence = state.evidence
    events = tuple(event_data(event) for event in deal.events)
    played = {event["card"] for event in events if event["type"] == "play"}
    own = {str(card) for card in state.hand}
    all_events = tuple(range(len(events)))
    combined = Reason("combined_evidence", int(state.setup.player), all_events, includes_setup=True)
    deadline = monotonic() + seconds
    rows, pending = [], 0
    remaining_support = {}
    for card in deck():
        code = str(card)
        if code in played:
            continue
        mask = evidence.domains[card.id]
        if code in own:
            remaining_support[code] = [int(state.setup.player)]
            continue
        owners, possible, excluded = [], [], []
        for seat in range(4):
            reason = evidence.exclusions[card.id][seat]
            if not mask & (1 << seat):
                excluded.append({"player": seat, "reason": asdict(reason or combined)})
                continue
            supported = None
            if mask.bit_count() == 1:
                supported = True  # Replay already proved the base state consistent.
            elif monotonic() + 0.05 < deadline:
                try:
                    supported = _owner_possible(evidence.domains, evidence.constraints, card.id, seat)
                except ValidationLimit:
                    pass
            if supported is False:
                excluded.append({"player": seat, "reason": asdict(combined)})
            else:
                owners.append(seat)
                if supported:
                    possible.append(seat)
                else:
                    pending += 1
        if not owners:
            raise ValueError("Ownership checks contradict the validated deal.")
        # A consistent base deal and excluded alternatives prove the last owner.
        if len(owners) == 1:
            pending -= len(set(owners) - set(possible))
            possible = owners.copy()
        remaining_support[code] = owners
        origin = evidence.origins[card.id]
        rows.append({"card": code, "owners": owners, "confirmed_possible": possible,
                     "excluded": excluded, "complete": len(owners) == len(possible),
                     "origin": asdict(origin) if origin else None,
                     "revealed": card in state.revealed[owners[0]] if len(owners) == 1 else False})
    deductions = list(evidence.deductions)
    for seat in range(4):
        if seat == state.setup.player or state.remaining_counts[seat] == 0:
            continue
        for suit in Suit:
            if any(code.startswith(suit.value + "_") and seat in owners for code, owners in remaining_support.items()):
                continue
            if not any(r.kind == "void_suit" and r.player == seat and r.suit == suit.value for r in deductions):
                deductions.append(Reason("void_suit", seat, all_events, suit.value, includes_setup=True))
    facts = [{"index": i, "event": event,
              "revealed_cards": [{"player": reason.player, "card": str(card)}
                                  for card, reason in zip(deck(), evidence.origins)
                                  if reason and reason.kind == "revealed" and reason.events == (i,)]
              if event["type"] == "finish_declarations" else []}
             for i, event in enumerate(events) if event["type"] != "play" or event.get("bela")]
    return {"match_id": match.id, "revision": match.revision, "deal_number": len(match.deals),
            "player": int(state.setup.player), "facts": facts,
            "deductions": [asdict(reason) for reason in deductions], "cards": rows,
            "played_count": len(played), "own_hand": sorted(own),
            "revealed_count": sum(str(card) not in played for known in state.revealed for card in known),
            "complete": pending == 0, "pending_checks": pending}
