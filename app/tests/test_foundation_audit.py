"""Small exhaustive worlds: completeness, exact weights and history equivalence.

These checks deliberately enumerate original possibilities before pruning, so
they can detect accidentally removing valid worlds as well as admitting bad ones.
"""

from fractions import Fraction
from itertools import product
from random import Random
import unittest

from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Seat
from bela.analysis.knowledge import KnowledgeEvidence
from bela.rules.melds import detect_melds
from bela.rules.play import legal_cards
from bela.analysis.sampling import HandSampler, NoConsistentDeals
from bela.gameplay.simulation import play_card, resolve_declarations, start_play
from bela.gameplay.tracking import (DealSetup, FinishDeclarations, Play, Presence, Reveal,
                           replay_deal)
from bela.analysis.validation import MeldConstraint
from test_validation import oracle as accepts_by_object_rules


CARDS = deck()


def allocations(domains):
    """Enumerate from input domains without propagation or sampler helpers."""
    options = [[s for s in range(4) if domain & (1 << s)] for domain in domains]
    for owners in product(*options):
        if all(owners.count(s) == 8 for s in range(4)):
            yield tuple(sum(1 << i for i, owner in enumerate(owners) if owner == s)
                        for s in range(4))


def hands(masks):
    return tuple(frozenset(c for c in CARDS if mask & (1 << c.id)) for mask in masks)


def sampler_paths(sampler):
    """Inspect every positive draw path and its exact rational probability."""
    def visit(index, capacities, masks, probability):
        if index == 32:
            yield masks, probability
            return
        choices = sampler._weights[index, capacities]
        total = sum(weight for _, _, weight in choices)
        for seat, remaining, weight in choices:
            child = list(masks)
            child[seat] |= 1 << sampler._order[index]
            yield from visit(index + 1, remaining, tuple(child), probability * Fraction(weight, total))
    yield from visit(0, (8, 8, 8, 8), (0, 0, 0, 0), Fraction(1))


class FoundationAuditTests(unittest.TestCase):
    def test_every_valid_world_survives_and_has_equal_exact_draw_probability(self):
        rng = Random(10546)
        for case in range(16):
            shuffled = list(CARDS)
            rng.shuffle(shuffled)
            original = [shuffled[i:i + 8] for i in range(0, 32, 8)]
            domains = [0] * 32
            for seat, hand in enumerate(original):
                for c in hand:
                    domains[c.id] = 1 << seat
                # Two unknown cards per seat; the oracle tries all assignments.
                for c in hand[:2]:
                    domains[c.id] |= rng.randrange(1, 16)
            seat = case % 4
            melds = detect_melds(original[seat])
            signature = tuple(sorted((m.kind.value, sum(1 << c.id for c in m.cards)) for m in melds))
            variants = [MeldConstraint(presence=False, no_belot=True),
                        MeldConstraint(presence=True, no_belot=True),
                        MeldConstraint(exact=signature, no_belot=True),
                        MeldConstraint(points=50, high=7, no_belot=True),
                        MeldConstraint(ceiling=(20, 0, 7), strict_ceiling=bool(case % 2), no_belot=True)]
            checks = ((seat, variants[case % len(variants)]),)
            expected = {masks for masks in allocations(domains)
                        if all(accepts_by_object_rules(check, hands(masks)[s]) for s, check in checks)}
            evidence = KnowledgeEvidence(tuple(domains), checks, (), (), ())
            with self.subTest(case=case):
                try:
                    sampler = HandSampler(evidence)
                except NoConsistentDeals:
                    self.assertFalse(expected)
                    continue
                paths = dict(sampler_paths(sampler))
                self.assertEqual(len(paths), sampler.proposal_count)
                self.assertEqual(set(paths.values()), {Fraction(1, sampler.proposal_count)})
                accepted = {masks for masks in paths
                            if all(check.accepts(masks[s]) for s, check in checks)}
                self.assertEqual(accepted, expected)
                if accepted:
                    mass = sum(paths[masks] for masks in accepted)
                    self.assertEqual({paths[masks] / mass for masks in accepted},
                                     {Fraction(1, len(expected))})

    def test_tracker_worlds_equal_independent_legal_history_worlds(self):
        for seed in range(4):
            rng = Random(7020 + seed)
            shuffled = list(CARDS)
            rng.shuffle(shuffled)
            original = [shuffled[i:i + 8] for i in range(0, 32, 8)]
            own = Seat(seed)
            full = resolve_declarations(start_play(original, trump=tuple(Suit)[seed],
                                                   dealer=Seat(seed), caller=Seat((seed + 1) % 4)))
            setup = DealSetup(own, tuple(original[own]), full.dealer, full.caller, full.trump)
            events = [Presence(s, present) for s, present in full.meld_contest.presence]
            # Restrict to a small exhaustive space using six arbitrary public
            # cards per opponent, plus every mandatory winning-team meld card.
            known = [set(original[own]) if s == own else set(original[s][:6]) for s in range(4)]
            for reveal in full.meld_contest.revealed:
                known[reveal.player].update(reveal.cards)
            for s in Seat:
                if s != own:
                    events.append(Reveal(s, tuple(sorted(known[s], key=lambda c: c.id))))
            events.append(FinishDeclarations(full.meld_contest.winning_team))
            domains = [15 & ~(1 << own)] * 32
            for s, cards in enumerate(known):
                for c in cards:
                    domains[c.id] = 1 << s
            candidates = list(allocations(domains))
            public_contest = full.meld_contest
            plays = []
            for index in range(13):
                actor = full.next_player
                card = rng.choice(legal_cards(full.hands[actor], full.current_trick, full.trump))
                pair = {Card(full.trump, Rank.KING), Card(full.trump, Rank.QUEEN)}
                bela = card in pair and pair.issubset(full.hands[actor])
                full = play_card(full, actor, card, announce_bela=bela)
                plays.append(Play(actor, card, bela))
                if index not in (4, 12):
                    continue
                state = replay_deal(setup, tuple(events + plays))
                expected = set()
                for masks in candidates:
                    try:
                        simulated = resolve_declarations(start_play(hands(masks), trump=setup.trump,
                                                                    dealer=setup.dealer, caller=setup.caller))
                        # Compare mandatory public records, not hidden melds or
                        # unspoken losing-team values.
                        if simulated.meld_contest != public_contest:
                            continue
                        for play in plays:
                            simulated = play_card(simulated, play.player, play.card, announce_bela=play.bela)
                    except ValueError:
                        continue
                    expected.add(masks)
                actual = {masks for masks in candidates
                          if all(domain & (1 << s) for s, mask in enumerate(masks)
                                 for i, domain in enumerate(state.evidence.domains) if mask & (1 << i))
                          and all(accepts_by_object_rules(check, hands(masks)[s])
                                  for s, check in state.evidence.constraints)}
                with self.subTest(seed=seed, cards_played=len(plays)):
                    self.assertTrue(expected)
                    self.assertEqual(actual, expected)
