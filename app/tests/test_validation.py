"""Independent oracle checks for pruning, complete hands and hidden allocation."""

from itertools import combinations
import random
import unittest
from unittest.mock import patch

from bela.domain.cards import Rank, Suit, deck
from bela.domain.game import Seat
from bela.domain.melds import MeldKind
from bela.rules.melds import detect_melds, has_belot
from bela.rules.play import legal_cards
from bela.gameplay.simulation import play_card, resolve_declarations, settle_play, start_play
from bela.gameplay.tracking import (DealSetup, FinishDeclarations, MeldValue, Play, Presence,
                           Reveal, SequenceHigh, replay_deal)
from bela.analysis.validation import (MeldConstraint, ValidationLimit, ValidationStats,
                             allocation_exists, clear_witness_cache, meld_signature)


CARDS = deck()


def bits(cards):
    return sum(1 << c.id for c in cards)


def cards(mask):
    return frozenset(c for c in CARDS if mask & (1 << c.id))


def oracle(constraint, hand):
    """The original object-based rules, independent of bitboard pruning."""
    melds = detect_melds(hand)
    strongest = melds[0] if melds else None
    if constraint.no_belot and has_belot(hand):
        return False
    if constraint.presence is not None and bool(melds) != constraint.presence:
        return False
    if constraint.points is not None and (strongest is None or strongest.points != constraint.points):
        return False
    if constraint.high is not None and (strongest is None or strongest.kind != MeldKind.SEQUENCE
                                       or tuple(Rank).index(strongest.high_rank) != constraint.high):
        return False
    if constraint.exact is not None and tuple(sorted((m.kind.value, bits(m.cards)) for m in melds)) != constraint.exact:
        return False
    if constraint.no_melds and melds:
        return False
    if constraint.ceiling is not None and strongest is not None:
        if strongest.strength_key > constraint.ceiling:
            return False
        if constraint.strict_ceiling and strongest.strength_key == constraint.ceiling:
            return False
    return True


def constraints(hand):
    melds = detect_melds(hand)
    strongest = melds[0] if melds else None
    return (
        MeldConstraint(), MeldConstraint(presence=False), MeldConstraint(presence=True),
        MeldConstraint(no_belot=True, no_melds=True),
        MeldConstraint(points=strongest.points if strongest else 50),
        MeldConstraint(points=50, high=7),
        MeldConstraint(points=100, high=7),
        MeldConstraint(points=200),
        MeldConstraint(exact=tuple(sorted((m.kind.value, bits(m.cards)) for m in melds)), no_belot=True),
        MeldConstraint(ceiling=(100, 0, 7), strict_ceiling=False, no_belot=True),
        MeldConstraint(ceiling=(20, 0, 7), strict_ceiling=True, no_belot=True),
    )


class BitboardMeldTests(unittest.TestCase):
    def test_complete_hand_signatures_match_object_rules(self):
        rng = random.Random(20261024)
        hands = [rng.sample(CARDS, 8) for _ in range(1200)]
        hands += [[c for c in CARDS if c.suit == suit] for suit in Suit]
        # All maximal run lengths/endpoints, with overlapping quads possible.
        for suit in Suit:
            suited = [c for c in CARDS if c.suit == suit]
            for length in range(3, 8):
                for start in range(9 - length):
                    run = suited[start:start + length]
                    fillers = [c for c in CARDS if c.suit != suit]
                    hands.append(run + fillers[:8 - length])
        for hand in hands:
            with self.subTest(hand=sorted(map(str, hand))):
                melds = detect_melds(hand)
                signature, strongest = meld_signature(bits(hand))
                self.assertEqual(signature, tuple(sorted((m.kind.value, bits(m.cards)) for m in melds)))
                self.assertEqual(strongest, melds[0].strength_key if melds else None)
                for constraint in constraints(hand):
                    self.assertEqual(constraint.accepts(bits(hand)), oracle(constraint, hand))

    def test_partial_pruning_preserves_every_legal_completion(self):
        rng = random.Random(9981)
        for _ in range(80):
            available_cards = rng.sample(CARDS, 11)
            required = bits(available_cards[:5])
            available = bits(available_cards)
            completions = [frozenset(available_cards[:5] + list(rest))
                           for rest in combinations(available_cards[5:], 3)]
            for constraint in constraints(completions[0]):
                valid = [bits(hand) for hand in completions if oracle(constraint, hand)]
                possible, forced, excluded = constraint.narrow(required, available)
                if valid:
                    self.assertTrue(possible, (constraint, required, available))
                    for hand in valid:
                        self.assertEqual(hand & forced, forced)
                        self.assertEqual(hand & excluded, 0)

    def test_belot_exception_survives_partial_no_meld_constraints(self):
        suit = tuple(c for c in CARDS if c.suit == Suit.HEARTS)
        allowed = MeldConstraint(presence=False)
        self.assertTrue(allowed.narrow(bits(suit[:4]), bits(suit))[0])
        self.assertTrue(allowed.accepts(bits(suit)))
        self.assertFalse(MeldConstraint(presence=False, no_belot=True).narrow(
            bits(suit[:4]), bits(suit))[0])


class AllocationOracleTests(unittest.TestCase):
    def setUp(self):
        clear_witness_cache()

    def test_matches_exhaustive_nearly_known_deals(self):
        rng = random.Random(4102)
        for scenario in range(12):
            shuffled = list(CARDS)
            rng.shuffle(shuffled)
            hands = [shuffled[i:i + 8] for i in range(0, 32, 8)]
            pool = hands[1][:4] + hands[2][:4]
            domains = [0] * 32
            for seat, hand in enumerate(hands):
                for card in hand:
                    domains[card.id] = 6 if card in pool else 1 << seat
            for first, second in zip(constraints(hands[1]), reversed(constraints(hands[2]))):
                expected = False
                for pick in combinations(pool, 4):
                    hand1 = frozenset(hands[1][4:] + list(pick))
                    hand2 = frozenset(hands[2][4:]) | (frozenset(pool) - frozenset(pick))
                    if oracle(first, hand1) and oracle(second, hand2):
                        expected = True
                        break
                with self.subTest(scenario=scenario, first=first, second=second):
                    self.assertEqual(allocation_exists(domains, {1: first, 2: second}), expected)

    def test_hall_capacity_conflict_is_detected_before_matching(self):
        stats = ValidationStats()
        self.assertFalse(allocation_exists([3] * 17 + [12] * 15, {}, stats=stats))
        self.assertEqual(stats.matching_attempts, 0)

    def test_cached_witness_rechecks_ownership_and_declarations(self):
        domains = [1 << (i // 8) for i in range(32)]
        self.assertTrue(allocation_exists(domains, {}))
        stats = ValidationStats()
        self.assertTrue(allocation_exists(domains, {}, stats=stats))
        self.assertEqual(stats.witness_hits, 1)
        # The old hint has belot in every hand and is no longer acceptable.
        self.assertFalse(allocation_exists(domains, {1: MeldConstraint(no_belot=True)}))
        changed = domains.copy()
        changed[8] = 1  # Nine cards forced to player 0.
        self.assertFalse(allocation_exists(changed, {}))
        # New evidence can reject an old hint while another allocation is legal.
        stats = ValidationStats()
        self.assertTrue(allocation_exists([15] * 32,
                        {s: MeldConstraint(no_belot=True, no_melds=True) for s in range(4)}, stats=stats))
        self.assertEqual(stats.witness_hits, 0)

    def test_two_individually_possible_quads_can_be_jointly_impossible(self):
        self.assertTrue(allocation_exists([15] * 32, {0: MeldConstraint(points=200)}))
        self.assertTrue(allocation_exists([15] * 32, {1: MeldConstraint(points=200)}))
        self.assertFalse(allocation_exists([15] * 32,
                         {0: MeldConstraint(points=200), 1: MeldConstraint(points=200)}))

    def test_exhaustive_fallback_supports_opaque_hand_predicates(self):
        domains = [1 << (i // 8) for i in range(32)]
        pool = list(range(8, 12)) + list(range(16, 20))
        for i in pool:
            domains[i] = 6
        target = frozenset(CARDS[i] for i in [8, 10, 17, 19, 12, 13, 14, 15])

        class Unshuffled:
            def __init__(self, seed):
                pass

            def shuffle(self, values):
                pass

        stats = ValidationStats()
        with patch("bela.analysis.validation.Random", Unshuffled):
            self.assertTrue(allocation_exists(domains, {1: lambda hand: hand == target}, stats=stats))
        self.assertGreater(stats.matching_attempts, 16)

    def test_budgets_apply_even_to_cached_success_and_do_not_poison_retries(self):
        domains = [15] * 32
        self.assertTrue(allocation_exists(domains, {}))
        for kwargs in ({"max_nodes": 0}, {"seconds": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationLimit):
                allocation_exists(domains, {}, **kwargs)
        self.assertTrue(allocation_exists(domains, {}))


class RandomPublicHistoryTests(unittest.TestCase):
    def test_random_legal_games_and_truthful_spoken_melds_remain_consistent(self):
        for seed in range(8):
            with self.subTest(seed=seed):
                rng = random.Random(7020 + seed)
                shuffled = list(CARDS)
                rng.shuffle(shuffled)
                hands = [shuffled[i:i + 8] for i in range(0, 32, 8)]
                self.assertFalse(any(has_belot(hand) for hand in hands))
                full = resolve_declarations(start_play(hands, trump=tuple(Suit)[seed % 4],
                                            dealer=Seat(seed % 4), caller=Seat((seed + 1) % 4)))
                own = Seat((seed + 2) % 4)
                setup = DealSetup(own, tuple(hands[own]), full.dealer, full.caller, full.trump)
                events = []
                for seat, present in full.meld_contest.presence:
                    events.append(Presence(seat, present))
                    melds = detect_melds(hands[seat])
                    if melds:
                        events.append(MeldValue(seat, melds[0].points))
                        if melds[0].kind == MeldKind.SEQUENCE:
                            events.append(SequenceHigh(seat, melds[0].high_rank))
                for reveal in full.meld_contest.revealed:
                    events.append(Reveal(reveal.player, tuple(sorted(reveal.cards, key=lambda c: c.id))))
                events.append(FinishDeclarations(full.meld_contest.winning_team))
                while not full.finished:
                    actor = full.next_player
                    card = rng.choice(legal_cards(full.hands[actor], full.current_trick, full.trump))
                    pair = {CARDS[list(Suit).index(full.trump) * 8 + i] for i in (5, 6)}
                    bela = card in pair and pair.issubset(full.hands[actor])
                    full = play_card(full, actor, card, announce_bela=bela)
                    events.append(Play(actor, card, bela))
                    tracked = replay_deal(setup, tuple(events))
                    self.assertEqual(tracked.current_trick, full.current_trick)
                    self.assertEqual(tracked.hand, full.hands[own])
                self.assertEqual(tracked.result, settle_play(full))
