"""Resumption, exact public facts, revisions, continuation and information limits."""

from dataclasses import replace
from random import Random
import unittest
from unittest.mock import patch

from bela.analysis.advisor import analyze
from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, Seat
from bela.domain.melds import (CardsRevealedAnnouncement, MeldPresenceAnnouncement,
                              MeldsFinishedAnnouncement, MeldValueAnnouncement,
                              SequenceHighAnnouncement)
from bela.storage.persistence import InvalidSaveError, dumps_match
from bela.gameplay.session import MatchSession
from bela.rules.melds import detect_melds
from bela.rules.play import legal_cards
from bela.analysis.sampling import HandSampler, SampledDeal
from bela.gameplay.simulation import observe, play_card, settle_play
from bela.analysis.simulation_bridge import (IncompleteSimulation, InvalidSimulationDeal,
                                    SimulationBridge, SimulationMismatch, StaleSimulation)
from bela.gameplay.tracking import (AddEvent, Belot, DealSetup, DeleteEvent, FinishDeclarations,
                           MeldValue, NextDeal, Play, Presence, Reveal, SequenceHigh, UserMatch)
from bela.storage.user_storage import dumps_user_match, loads_user_match


def cards(text):
    return tuple(Card.parse(c) for c in text.split())


def match_with(*events, hand="H_Q H_K S_9 S_10 S_A D_K C_8 C_9", score=(230, 410)):
    match = UserMatch.start(DealSetup(Seat.ZERO, cards(hand), Seat.THREE, Seat.ZERO,
                                     Suit.HEARTS, score))
    for event in events:
        match = match.perform(AddEvent(event))
    return match


def samples(match, count=1):
    batch = HandSampler(match.state.evidence).sample(count, seed=54, seconds=10)
    assert batch.complete
    return batch.deals


def losing_claim_match():
    return match_with(Presence(Seat.ZERO, True), MeldValue(Seat.ZERO, 20),
                      SequenceHigh(Seat.ZERO, Rank.NINE),
                      Reveal(Seat.ONE, cards("H_10 H_J H_Q H_K")),
                      FinishDeclarations(1), hand="H_7 H_8 H_9 S_7 S_8 S_9 D_7 C_7")


class SimulationBridgeTests(unittest.TestCase):
    def test_refuses_unfinished_declarations_and_stale_revision(self):
        match = match_with(Presence(Seat.ONE, False))
        with self.assertRaises(IncompleteSimulation):
            SimulationBridge.from_match(match)
        with self.assertRaises(StaleSimulation):
            SimulationBridge.from_match(match, expected_revision=0)
        for value in (True, -1, "1"):
            with self.assertRaises(ValueError):
                SimulationBridge.from_match(match, expected_revision=value)

    def test_mid_trick_preserves_state_and_never_redeclares(self):
        match = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                           Play(Seat.ONE, Card.parse("C_7")))
        before = dumps_user_match(match)
        bridge = SimulationBridge.from_match(match, expected_revision=match.revision)
        with patch("bela.gameplay.simulation.resolve_declarations", side_effect=AssertionError("No redeclaration")):
            simulated = bridge.resume(samples(match)[0])
        self.assertEqual((bridge.match_id, bridge.revision, bridge.deal_number),
                         (match.id, match.revision, 1))
        self.assertEqual(simulated.current_trick, match.state.current_trick)
        self.assertEqual(simulated.completed_tricks, match.state.completed_tricks)
        self.assertEqual(simulated.match_score, (230, 410))
        self.assertEqual(simulated.next_player, Seat.TWO)
        self.assertEqual(tuple(map(len, simulated.hands)), match.state.remaining_counts)
        self.assertEqual(simulated.hands[0], match.state.hand)
        self.assertEqual(before, dumps_user_match(match))

    def test_losing_claims_are_preserved_and_missing_presence_not_invented(self):
        match = losing_claim_match()
        simulated = SimulationBridge.from_match(match).resume(samples(match)[0])
        view = observe(simulated, Seat.ZERO)
        self.assertEqual(view.meld_contest.presence, ((Seat.ZERO, True),))
        self.assertEqual(view.meld_announcements,
                         (MeldValueAnnouncement(Seat.ZERO, 20), SequenceHighAnnouncement(Seat.ZERO, Rank.NINE)))
        self.assertEqual(view.declaration_history, (
            MeldPresenceAnnouncement(Seat.ZERO, True), MeldValueAnnouncement(Seat.ZERO, 20),
            SequenceHighAnnouncement(Seat.ZERO, Rank.NINE),
            CardsRevealedAnnouncement(Seat.ONE, cards("H_10 H_J H_Q H_K")),
            MeldsFinishedAnnouncement(1)))
        self.assertEqual(view.meld_contest.winning_player, Seat.ONE)
        self.assertEqual(view.meld_contest.awarded_points, (0, 50))
        self.assertEqual(len(view.meld_contest.revealed), 1)

    def test_arbitrary_public_reveals_and_implicit_own_winning_meld(self):
        match = match_with(Reveal(Seat.ONE, cards("C_7")), FinishDeclarations(0),
                           hand="H_7 H_8 H_9 C_8 H_Q C_10 D_Q C_A")
        simulated = SimulationBridge.from_match(match).resume(samples(match)[0])
        expected = MeldsFinishedAnnouncement(0, (
            CardsRevealedAnnouncement(Seat.ZERO, cards("H_7 H_8 H_9")),))
        for seat in Seat:
            view = observe(simulated, seat)
            self.assertEqual(view.declaration_history[0], CardsRevealedAnnouncement(Seat.ONE, cards("C_7")))
            self.assertEqual(view.declaration_history[-1], expected)
            self.assertEqual(view.meld_contest.revealed[0].cards, frozenset(cards("H_7 H_8 H_9")))
            self.assertEqual(view.hand, simulated.hands[seat])
            self.assertFalse(hasattr(view, "hands"))

    def test_unrevealed_world_changes_do_not_change_our_observation(self):
        match = losing_claim_match()
        bridge = SimulationBridge.from_match(match)
        deals = samples(match, 100)
        # Player 2's unrecorded presence really varies between worlds. The
        # observation must still be identical, not regenerated from that hand.
        self.assertEqual({bool(detect_melds(d.hands[2])) for d in deals}, {False, True})
        first = observe(bridge.resume(deals[0]), Seat.ZERO)
        for deal in deals[1:]:
            alternative = observe(bridge.resume(deal), Seat.ZERO)
            self.assertEqual(first, alternative)
            self.assertEqual(analyze(first), analyze(alternative))

    def test_every_actors_observation_is_invariant_to_hidden_swaps(self):
        match = match_with(FinishDeclarations(None))
        bridge = SimulationBridge.from_match(match)
        worlds = [bridge.resume(d) for d in samples(match, 30)]
        for actor in Seat:
            original = worlds[0]
            others = [seat for seat in Seat if seat != actor]
            altered = list(original.hands)
            altered[others[0]], altered[others[1]] = altered[others[1]], altered[others[0]]
            alternative = replace(original, hands=tuple(altered))
            self.assertEqual(observe(original, actor), observe(alternative, actor))
            self.assertEqual(observe(original, actor).hand, original.hands[actor])
            self.assertEqual(observe(original, actor).declaration_history, original.declaration_history)

    def test_resumed_deal_continues_to_identical_settlement_with_and_without_bela(self):
        for announce in (False, True):
            match = losing_claim_match()
            deal = samples(match)[0]
            simulated = SimulationBridge.from_match(match).resume(deal)
            rng = Random(127)
            count = 0
            while not simulated.finished:
                actor = simulated.next_player
                card = rng.choice(legal_cards(simulated.hands[actor], simulated.current_trick, simulated.trump))
                pair = {Card(simulated.trump, Rank.KING), Card(simulated.trump, Rank.QUEEN)}
                bela = announce and card in pair and pair.issubset(simulated.hands[actor])
                simulated = play_card(simulated, actor, card, announce_bela=bela)
                match = match.perform(AddEvent(Play(actor, card, bela)))
                resumed = SimulationBridge.from_match(match).resume(deal)
                self.assertEqual(resumed, simulated)
                count += 1
            self.assertEqual(count, 32)
            self.assertEqual(bool(simulated.bela_announcements), announce)
            self.assertEqual(settle_play(simulated), match.state.result)
            self.assertEqual(match.state.score, tuple(a + b for a, b in
                                                     zip(simulated.match_score, settle_play(simulated).recorded)))

    def test_existing_bela_position_and_missed_announcement_timing(self):
        match = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("H_Q"), True))
        bridge = SimulationBridge.from_match(match)
        resumed = bridge.resume(samples(match)[0])
        self.assertEqual(resumed.bela_announcements, match.state.bela_announcements)
        self.assertEqual((resumed.bela_announcements[0].trick_index,
                          resumed.bela_announcements[0].position), (0, 0))
        # A missed first announcement remains missed after resumption.
        missed = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("H_Q")))
        state = SimulationBridge.from_match(missed).resume(samples(missed)[0])
        self.assertEqual(state.bela_announcements, ())
        while state.next_player != Seat.ZERO or Card.parse("H_K") not in legal_cards(
                state.hands[Seat.ZERO], state.current_trick, state.trump):
            actor = state.next_player
            card = legal_cards(state.hands[actor], state.current_trick, state.trump)[0]
            state = play_card(state, actor, card)
        with self.assertRaisesRegex(ValueError, "first trump K/Q"):
            play_card(state, Seat.ZERO, Card.parse("H_K"), announce_bela=True)

    def test_belot_is_preserved_as_immediate_match_result(self):
        match = match_with(Belot(Seat.ZERO), hand="H_7 H_8 H_9 H_10 H_J H_Q H_K H_A")
        state = SimulationBridge.from_match(match).resume(samples(match)[0])
        self.assertEqual(state.phase, Phase.MATCH_FINISHED)
        self.assertEqual(settle_play(state), match.state.result)
        self.assertEqual(observe(state, Seat.TWO).belot.revealed_cards, frozenset(match.initial.hand))
        self.assertEqual(state.completed_tricks, ())
        self.assertEqual(state.match_score, (230, 410))
        with self.assertRaises(InvalidSaveError):
            dumps_match(MatchSession.start(state))
        with self.assertRaises(ValueError):
            play_card(state, Seat.ZERO, Card.parse("H_7"))

    def test_rejects_bad_ownership_and_declaration_contradictions(self):
        match = match_with(FinishDeclarations(None))
        bridge = SimulationBridge.from_match(match)
        good = samples(match)[0]
        invalid = [SampledDeal((0, 0, 0, 0)), SampledDeal((-1, *good.masks[1:])),
                   SampledDeal((good.masks[0] | (1 << 40), *good.masks[1:])),
                   SampledDeal((good.masks[1], good.masks[0], *good.masks[2:])),
                   SampledDeal((good.masks[0], good.masks[0], *good.masks[2:]))]
        for deal in invalid:
            with self.assertRaises(InvalidSimulationDeal):
                bridge.resume(deal)
        # Capacity-correct and matching our hand, but violating no-meld evidence.
        unconditioned = samples(match_with(), 50)
        contradiction = next(d for d in unconditioned if any(detect_melds(h) for h in d.hands))
        with self.assertRaises(InvalidSimulationDeal):
            bridge.resume(contradiction)

    def test_corrections_and_save_reload_preserve_snapshot_identity(self):
        original = match_with(Presence(Seat.ONE, False), FinishDeclarations(None))
        old_bridge = SimulationBridge.from_match(original)
        corrected = original.perform(DeleteEvent(0))
        with self.assertRaises(StaleSimulation):
            SimulationBridge.from_match(corrected, expected_revision=old_bridge.revision)
        current = SimulationBridge.from_match(corrected, expected_revision=corrected.revision)
        deal = samples(corrected)[0]
        self.assertEqual(old_bridge.resume(deal).meld_contest.presence, ((Seat.ONE, False),))
        self.assertEqual(current.resume(deal).meld_contest.presence, ())
        loaded = loads_user_match(dumps_user_match(corrected))
        self.assertEqual(SimulationBridge.from_match(loaded).resume(deal), current.resume(deal))
        with self.assertRaises(InvalidSaveError):
            dumps_match(MatchSession.start(current.resume(deal)))

    def test_all_trumps_and_tracked_seats_resume_without_swapping_ownership(self):
        hand = cards("H_Q H_K S_9 S_10 S_A D_K C_8 C_9")
        for seat in Seat:
            for trump in Suit:
                setup = DealSetup(seat, hand, seat, seat.partner, trump, (810, 770))
                match = UserMatch.start(setup).perform(AddEvent(FinishDeclarations(None)))
                deal = samples(match)[0]
                state = SimulationBridge.from_match(match).resume(deal)
                self.assertEqual(state.hands[seat], frozenset(hand))
                self.assertEqual(state.next_player, seat.next)
                self.assertEqual(state.trump, trump)
                self.assertEqual(state.caller, seat.partner)
                self.assertEqual(state.match_score, (810, 770))
                self.assertEqual(observe(state, seat).hand, frozenset(hand))

    def test_detects_internal_replay_disagreement(self):
        match = match_with(FinishDeclarations(None))
        bridge = SimulationBridge.from_match(match)
        corrupted = replace(bridge, _tracked=replace(bridge._tracked, trick_points=(1, 0)))
        with self.assertRaises(SimulationMismatch):
            corrupted.resume(samples(match)[0])

    def test_next_deal_uses_only_current_history_and_carried_score(self):
        match = match_with(FinishDeclarations(None), score=(0, 0))
        deal = samples(match)[0]
        state = SimulationBridge.from_match(match).resume(deal)
        while not state.finished:
            actor = state.next_player
            card = legal_cards(state.hands[actor], state.current_trick, state.trump)[0]
            state = play_card(state, actor, card)
            match = match.perform(AddEvent(Play(actor, card)))
        setup = replace(match.initial, dealer=match.state.setup.dealer.next, match_score=match.state.score)
        match = match.perform(NextDeal(setup)).perform(AddEvent(FinishDeclarations(None)))
        bridge = SimulationBridge.from_match(match)
        state = bridge.resume(samples(match)[0])
        self.assertEqual(bridge.deal_number, 2)
        self.assertEqual(state.completed_tricks, ())
        self.assertEqual(state.current_trick.cards, ())
        self.assertEqual(state.current_trick.leader, setup.dealer.next)
        self.assertEqual(state.match_score, setup.match_score)
        self.assertEqual(state.declaration_history, (MeldsFinishedAnnouncement(None),))


if __name__ == "__main__":
    unittest.main()
