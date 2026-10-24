"""Exact small-space oracles and reproducible uniformity checks."""

from collections import Counter
from itertools import product
from math import factorial
from random import Random
import unittest
from unittest.mock import patch

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Seat
from bela.analysis.knowledge import KnowledgeEvidence
from bela.rules.melds import detect_melds
from bela.rules.play import legal_cards
from bela.analysis.sampling import HandSampler, NoConsistentDeals, SamplingLimit
from bela.gameplay.simulation import play_card, resolve_declarations, start_play
from bela.gameplay.tracking import (AddEvent, DealSetup, DeleteEvent, FinishDeclarations,
                           MeldValue, Play, Presence, Reveal, SequenceHigh, UserMatch,
                           replay_deal)
from bela.storage.user_storage import dumps_user_match
from bela.analysis.validation import MeldConstraint


CARDS = deck()


def evidence(domains, checks=()):
    return KnowledgeEvidence(tuple(domains), tuple(checks), (), (), ())


def oracle(domains, checks=()):
    """Brute force small fixtures without sampler code or meld bitboards."""
    options = [[seat for seat in range(4) if mask & (1 << seat)] for mask in domains]
    found = set()
    for owners in product(*options):
        if any(owners.count(seat) != 8 for seat in range(4)):
            continue
        hands = tuple(frozenset(c for c, owner in zip(CARDS, owners) if owner == seat)
                      for seat in range(4))
        if any(bool(detect_melds(hands[seat])) != presence for seat, presence in checks):
            continue
        found.add(tuple(sum(1 << c.id for c in hand) for hand in hands))
    return found


def match_with(*events):
    cards = tuple(Card.parse(c) for c in "H_Q H_K S_9 S_10 S_A D_K C_8 C_9".split())
    match = UserMatch.start(DealSetup(Seat.ZERO, cards, Seat.THREE, Seat.ZERO, Suit.HEARTS))
    for event in events:
        match = match.perform(AddEvent(event))
    return match


class SamplingTests(unittest.TestCase):
    def test_opening_count_and_private_hand(self):
        match = match_with()
        before = dumps_user_match(match)
        with patch("bela.analysis.validation.allocation_exists", side_effect=AssertionError("No witnesses")):
            sampler = HandSampler(match.state.evidence)
            batch = sampler.sample(200, seed=42, seconds=10)
        self.assertEqual(sampler.proposal_count, factorial(24) // factorial(8) ** 3)
        self.assertTrue(batch.complete)
        self.assertEqual(batch.attempts, 200)
        for deal in batch.deals:
            self.assertEqual(deal.hands[0], frozenset(match.state.setup.hand))
            self.assertEqual([len(h) for h in deal.hands], [8] * 4)
            self.assertEqual(set().union(*deal.hands), set(CARDS))
        self.assertEqual(before, dumps_user_match(match))
        self.assertEqual(sampler.sample(200, seed=42, seconds=10).deals, batch.deals)

    def test_weighted_sampling_matches_asymmetric_exhaustive_space(self):
        domains = [1 << (i // 7) for i in range(28)] + [3, 7, 14, 15]
        expected = oracle(domains)
        sampler = HandSampler(evidence(domains))
        self.assertEqual(sampler.proposal_count, len(expected))
        batch = sampler.sample(12000, seed=372, seconds=20)
        self.assertTrue(batch.complete)
        frequencies = Counter(d.masks for d in batch.deals)
        self.assertEqual(set(frequencies), expected)
        mean = 12000 / len(expected)
        # Six standard deviations; seeded and intentionally broad, not an exact
        # histogram assertion that mirrors implementation details.
        tolerance = 6 * (mean * (1 - 1 / len(expected))) ** .5
        self.assertTrue(all(abs(n - mean) < tolerance for n in frequencies.values()))

    def test_no_declaration_rejection_matches_independent_rules(self):
        ids = list(range(32))
        Random(51).shuffle(ids)
        domains = [0] * 32
        for seat in range(4):
            for i in ids[seat * 8:seat * 8 + 8]:
                domains[i] = 1 << seat
        for i in ids[:4] + ids[8:12]:
            domains[i] = 3
        expected = oracle(domains, ((0, False), (1, False)))
        self.assertGreater(len(expected), 1)
        sampler = HandSampler(evidence(domains, ((0, MeldConstraint(presence=False)),
                                                  (1, MeldConstraint(presence=False)))))
        batch = sampler.sample(8000, seed=972, seconds=20)
        self.assertTrue(batch.complete)
        frequencies = Counter(d.masks for d in batch.deals)
        self.assertEqual(set(frequencies), expected)
        mean = len(batch.deals) / len(expected)
        tolerance = 6 * (mean * (1 - 1 / len(expected))) ** .5
        self.assertTrue(all(abs(n - mean) < tolerance for n in frequencies.values()))

    def test_random_restricted_spaces_counted_exactly(self):
        rng = Random(391)
        for _ in range(12):
            domains = [1 << (i // 8) for i in range(32)]
            for i in (6, 7, 14, 15, 22, 23, 30, 31):
                domains[i] |= rng.randrange(1, 16)
            expected = oracle(domains)
            sampler = HandSampler(evidence(domains))
            self.assertEqual(sampler.proposal_count, len(expected))
            batch = sampler.sample(30, seed=4, seconds=10)
            self.assertTrue(all(d.masks in expected for d in batch.deals))

    def test_spoken_sequence_and_no_declarations(self):
        match = match_with(Presence(Seat.TWO, False), MeldValue(Seat.ONE, 50),
                           SequenceHigh(Seat.ONE, Rank.ACE))
        sampler = HandSampler(match.state.evidence)
        batch = sampler.sample(100, seed=8, seconds=10)
        self.assertTrue(batch.complete)
        for deal in batch.deals:
            self.assertFalse(detect_melds(deal.hands[2]))
            strongest = detect_melds(deal.hands[1])[0]
            self.assertEqual((strongest.points, strongest.high_rank), (50, Rank.ACE))

    def test_play_history_and_remaining_hands(self):
        match = match_with(FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                           Play(Seat.ONE, Card.parse("C_7")))
        sampler = HandSampler(match.state.evidence)
        batch = sampler.sample(80, seed=19, seconds=10)
        self.assertTrue(batch.complete)
        played = (Card.parse("S_9"), Card.parse("C_7"))
        for deal in batch.deals:
            remaining = deal.remaining_hands(played)
            self.assertEqual(tuple(map(len, remaining)), match.state.remaining_counts)
            self.assertTrue(all(c.suit not in (Suit.HEARTS, Suit.SPADES) for c in remaining[1]))
            self.assertTrue(all(not detect_melds(h) for h in deal.hands))

    def test_evidence_correction_requires_new_sampler(self):
        match = match_with(Presence(Seat.ONE, False))
        old = HandSampler(match.state.evidence)
        corrected = match.perform(DeleteEvent(0))
        new = HandSampler(corrected.state.evidence)
        # Both snapshots remain independent and immutable after corrections.
        self.assertTrue(all(not detect_melds(d.hands[1]) for d in old.sample(100, seed=4, seconds=10).deals))
        self.assertTrue(any(detect_melds(d.hands[1]) for d in new.sample(100, seed=4, seconds=10).deals))

    def test_sampled_deals_allow_recorded_plays_in_independent_simulator(self):
        for seed in range(3):
            rng = Random(7020 + seed)
            shuffled = list(CARDS)
            rng.shuffle(shuffled)
            hands = [shuffled[i:i + 8] for i in range(0, 32, 8)]
            original = resolve_declarations(start_play(hands, trump=tuple(Suit)[seed],
                                                       dealer=Seat(seed), caller=Seat.ONE))
            setup = DealSetup(Seat.ZERO, tuple(hands[0]), original.dealer, original.caller, original.trump)
            events = [Presence(seat, present) for seat, present in original.meld_contest.presence]
            events += [Reveal(item.player, tuple(item.cards)) for item in original.meld_contest.revealed]
            events.append(FinishDeclarations(original.meld_contest.winning_team))
            plays = []
            full = original
            for _ in range(16):
                actor = full.next_player
                card = rng.choice(legal_cards(full.hands[actor], full.current_trick, full.trump))
                pair = {c for c in CARDS if c.suit == full.trump and c.rank in (Rank.KING, Rank.QUEEN)}
                bela = card in pair and pair.issubset(full.hands[actor])
                full = play_card(full, actor, card, announce_bela=bela)
                plays.append(Play(actor, card, bela))
            tracked = replay_deal(setup, tuple(events + plays))
            batch = HandSampler(tracked.evidence).sample(20, seed=seed, seconds=10)
            self.assertTrue(batch.complete)
            for deal in batch.deals:
                simulated = resolve_declarations(start_play(deal.hands, trump=original.trump,
                                                            dealer=original.dealer, caller=original.caller))
                self.assertEqual(simulated.meld_contest.winning_team, original.meld_contest.winning_team)
                for play in plays:
                    simulated = play_card(simulated, play.player, play.card, announce_bela=play.bela)
                self.assertEqual(simulated.current_trick, tracked.current_trick)
                self.assertEqual(simulated.hands[0], tracked.hand)
                self.assertEqual(simulated.completed_tricks, tracked.completed_tricks)

    def test_single_deal_duplicates_and_counts(self):
        domains = [1 << (i // 8) for i in range(32)]
        sampler = HandSampler(evidence(domains))
        batch = sampler.sample(10, seed=1, seconds=10)
        self.assertEqual(sampler.proposal_count, 1)
        self.assertEqual(len(set(batch.deals)), 1)
        self.assertTrue(batch.complete)
        for i, row in enumerate(batch.ownership_counts()):
            self.assertEqual(row[i // 8], 10)
            self.assertEqual(sum(row), 10)

    def test_limits_are_not_inconsistency_or_fake_samples(self):
        data = match_with().state.evidence
        with self.assertRaises(SamplingLimit):
            HandSampler(data, seconds=0)
        with self.assertRaises(SamplingLimit):
            HandSampler(data, max_states=1)
        sampler = HandSampler(data)
        batch = sampler.sample(10, seconds=0)
        self.assertEqual((batch.stop_reason, batch.deals), ("time_limit", ()))
        self.assertIsNone(batch.acceptance_rate)
        self.assertTrue(all(sum(row) == 0 for row in batch.ownership_counts()))
        batch = sampler.sample(10, max_attempts=2, seconds=10)
        self.assertEqual((batch.stop_reason, batch.attempts, len(batch.deals)), ("attempt_limit", 2, 2))
        self.assertFalse(batch.complete)
        self.assertTrue(sampler.sample(0).complete)
        declared = HandSampler(match_with(Presence(Seat.ONE, False)).state.evidence)
        with patch.object(MeldConstraint, "accepts", return_value=False):
            empty = declared.sample(10, seconds=10, max_attempts=3)
        self.assertEqual((empty.stop_reason, empty.attempts, empty.deals), ("attempt_limit", 3, ()))
        self.assertEqual(empty.acceptance_rate, 0)

    def test_proven_impossible_and_invalid_inputs(self):
        with self.assertRaises(NoConsistentDeals):
            HandSampler(evidence([1] * 9 + [14] * 23))
        # Joint capacity conflict with individually feasible seats.
        with self.assertRaises(NoConsistentDeals):
            HandSampler(evidence([3] * 17 + [12] * 15))
        with self.assertRaises(NoConsistentDeals):
            HandSampler(evidence([1 << (i // 8) for i in range(32)],
                                 ((0, MeldConstraint(no_belot=True)),)))
        with self.assertRaises(ValueError):
            HandSampler(evidence([0] * 32))
        sampler = HandSampler(match_with().state.evidence)
        for kwargs in ({"count": -1}, {"count": True}, {"count": 1, "seconds": float("nan")},
                       {"count": 1, "max_attempts": -1}):
            with self.assertRaises(ValueError):
                sampler.sample(**kwargs)


if __name__ == "__main__":
    unittest.main()
