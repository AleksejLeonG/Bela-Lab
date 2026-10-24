"""Resume a synthetic deal using exactly one tracked public-history snapshot.

This module is internal analysis plumbing. Full states belong to the simulator;
policies must receive simulation.observe(state, actor), never the bridge/state.
"""

from dataclasses import dataclass, replace

from bela.domain.game import Phase, PlayState, Seat
from bela.domain.melds import (BelotResult, CardsRevealedAnnouncement, MeldContest,
                              MeldAnnouncement, RecordedDeclaration,
                              MeldPresenceAnnouncement, MeldsFinishedAnnouncement,
                              MeldValueAnnouncement, RevealedMelds, SequenceHighAnnouncement)
from bela.rules.melds import detect_melds
from bela.rules.play import card_points, trick_winner
from bela.analysis.sampling import SampledDeal
from bela.gameplay.simulation import play_card, settle_play, start_play
from bela.gameplay.tracking import (FinishDeclarations, MeldValue, Play, Presence, Reveal,
                           SequenceHigh, TrackedState, UserMatch)


class IncompleteSimulation(ValueError):
    """Ordinary declarations must be finished before continuation analysis."""


class StaleSimulation(ValueError):
    """The caller requested a revision different from the supplied match."""


class InvalidSimulationDeal(ValueError):
    """A synthetic initial deal does not fit the current evidence."""


class SimulationMismatch(ValueError):
    """Independent simulator replay disagreed with the tracked state."""


@dataclass(frozen=True)
class SimulationBridge:
    """Prepared immutable analysis context; reuse for many sampled deals.

    from_match checks an optional expected revision. A bridge never follows live
    edits: the application must compare its metadata with the current match
    before displaying analysis and discard stale results.
    """

    match_id: str
    revision: int
    deal_number: int
    _tracked: TrackedState
    _plays: tuple[Play, ...]
    _contest: MeldContest | None
    _announcements: tuple[MeldAnnouncement, ...]
    _declarations: tuple[RecordedDeclaration, ...]

    @classmethod
    def from_match(cls, match: UserMatch, *, expected_revision=None):
        if not isinstance(match, UserMatch):
            raise ValueError("Expected a tracked UserMatch.")
        if expected_revision is not None:
            if type(expected_revision) is not int or expected_revision < 0:
                raise ValueError("Expected revision must be a nonnegative integer.")
            if expected_revision != match.revision:
                raise StaleSimulation("The tracked match revision has changed; prepare a new simulation.")
        deal = match.deals[-1]
        tracked = deal.state
        if tracked.phase == Phase.DECLARATIONS:
            raise IncompleteSimulation("Finish declarations before preparing a play simulation.")

        presence, announcements, declarations = [], [], []
        revealed = [set() for _ in Seat]
        finish = None
        for event in deal.events:
            if isinstance(event, Presence):
                record = MeldPresenceAnnouncement(event.player, event.has_meld)
                presence.append((event.player, event.has_meld))
            elif isinstance(event, MeldValue):
                record = MeldValueAnnouncement(event.player, event.points)
                announcements.append(record)
            elif isinstance(event, SequenceHigh):
                record = SequenceHighAnnouncement(event.player, event.rank)
                announcements.append(record)
            elif isinstance(event, Reveal):
                record = CardsRevealedAnnouncement(event.player, event.cards)
                revealed[event.player].update(event.cards)
            elif isinstance(event, FinishDeclarations):
                finish = event
                implicit = []
                for seat in Seat:
                    extra = tracked.revealed[seat] - revealed[seat]
                    if extra:
                        implicit.append(CardsRevealedAnnouncement(seat, tuple(sorted(extra, key=lambda c: c.id))))
                        revealed[seat].update(extra)
                record = MeldsFinishedAnnouncement(event.winning_team, tuple(implicit))
            else:
                continue  # Plays are replayed; a belot claim is public via result.
            declarations.append(record)

        contest = None
        if finish is not None:
            order = tuple(Seat((int(tracked.setup.dealer) + offset) % 4) for offset in range(1, 5))
            shown = []
            for seat in order:
                if seat.team == finish.winning_team:
                    melds = detect_melds(revealed[seat])
                    if melds:
                        shown.append(RevealedMelds(seat, melds))
            shown = tuple(shown)
            winner = max(shown, key=lambda item: item.melds[0].strength_key).player if shown else None
            contest = MeldContest(winner, finish.winning_team, tracked.awarded_melds,
                                  tuple(presence), shown)
        return cls(match.id, match.revision, len(match.deals), tracked,
                   tuple(event for event in deal.events if isinstance(event, Play)),
                   contest, tuple(announcements), tuple(declarations))

    def resume(self, deal: SampledDeal) -> PlayState:
        """Validate a hypothesis and replay actual moves without redeclaring.

        No hidden-world allocation search or random sampling is performed here.
        Replaying the existing simulator checks legal actions and bela timing.
        """
        if (not isinstance(deal, SampledDeal) or not isinstance(deal.masks, tuple)
                or len(deal.masks) != 4
                or any(type(mask) is not int or not 0 <= mask < (1 << 32)
                       or mask.bit_count() != 8 for mask in deal.masks)
                or sum(deal.masks) != (1 << 32) - 1
                or any(deal.masks[a] & deal.masks[b] for a in range(4) for b in range(a))):
            raise InvalidSimulationDeal("Expected four disjoint initial hands covering all 32 cards.")
        tracked = self._tracked
        for seat, hand in enumerate(deal.masks):
            if any(not domain & (1 << seat) for card_id, domain in enumerate(tracked.evidence.domains)
                   if hand & (1 << card_id)):
                raise InvalidSimulationDeal("The sampled ownership contradicts this tracked revision.")
        if any(not check.accepts(deal.masks[seat]) for seat, check in tracked.evidence.constraints):
            raise InvalidSimulationDeal("The sampled hand contradicts recorded declarations.")
        setup = tracked.setup
        state = start_play(deal.hands, trump=setup.trump, dealer=setup.dealer,
                           caller=setup.caller, match_score=setup.match_score)
        state = replace(state, analysis_only=True)
        if isinstance(tracked.result, BelotResult):
            state = replace(state, phase=Phase.MATCH_FINISHED, belot=tracked.result,
                            meld_announcements=self._announcements,
                            declaration_history=self._declarations)
        else:
            if self._contest is None:
                raise SimulationMismatch("The tracked play has no completed declaration record.")
            state = replace(state, phase=Phase.PLAYING, meld_contest=self._contest,
                            meld_announcements=self._announcements,
                            declaration_history=self._declarations)
            try:
                for event in self._plays:
                    state = play_card(state, event.player, event.card, announce_bela=event.bela)
            except ValueError as error:
                raise InvalidSimulationDeal(f"The sampled deal cannot replay the recorded moves: {error}") from error
        self._verify(state)
        return state

    def _verify(self, state):
        tracked = self._tracked
        points, counts = [0, 0], [0, 0]
        for trick in state.completed_tricks:
            team = trick_winner(trick, state.trump).team
            counts[team] += 1
            points[team] += sum(card_points(c, state.trump) for c in trick.cards)
        if (state.phase != tracked.phase or state.current_trick != tracked.current_trick
                or state.completed_tricks != tracked.completed_tricks
                or state.hands[tracked.setup.player] != tracked.hand
                or tuple(map(len, state.hands)) != tracked.remaining_counts
                or state.bela_announcements != tracked.bela_announcements
                or tuple(points) != tracked.trick_points or tuple(counts) != tracked.trick_counts):
            raise SimulationMismatch("Simulator replay disagrees with the tracked position.")
        if tracked.result is not None and settle_play(state) != tracked.result:
            raise SimulationMismatch("Simulator settlement disagrees with the tracked result.")
