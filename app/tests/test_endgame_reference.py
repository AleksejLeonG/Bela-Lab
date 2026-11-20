"""Exact references checked against independently expanded continuation trees."""
from dataclasses import replace
from fractions import Fraction
from itertools import product
from collections import defaultdict
from pathlib import Path
import unittest

from bela.analysis.endgame_reference import (ReferenceLimit, opponent_distribution,
    policy_distribution, solve_known_endgame)
from bela.analysis.policies import POLICIES, PolicyMove, announce_bela
from bela.analysis.sampling import SampledDeal
from bela.analysis.simulation_bridge import SimulationBridge
from bela.domain.cards import Card
from bela.domain.game import Seat
from bela.domain.melds import CardsRevealedAnnouncement
from bela.gameplay.simulation import observe, play_card, resolve_declarations, settle_play, start_play
from bela.rules.play import legal_cards
from bela.storage.user_storage import loads_user_match
from test_monte_carlo import HANDS, cards, endgame, exact_random_outcomes


def known_endgame(played=24, caller=Seat.ONE):
    match, _ = endgame(played, caller)
    deal = SampledDeal(tuple(sum(1 << c.id for c in hand) for hand in HANDS))
    return match, SimulationBridge.from_match(match).resume(deal)


def fixed_lineup_mean(state, own, lineup, self_policy):
    """Independent enumeration: profile assignment stays fixed down each tree."""
    if state.finished:
        result = settle_play(state)
        return Fraction(result.recorded[own.team] - result.recorded[1-own.team])
    actor = state.next_player
    view = observe(state, actor)
    policy = self_policy if actor == own else lineup[actor]
    return sum(probability * fixed_lineup_mean(
        play_card(state, actor, move.card, announce_bela=move.bela), own, lineup, self_policy)
        for move, probability in policy_distribution(view, policy))


def explicit_scenario_optimum(after_first, own, profiles):
    """Group joint profile scenarios by observed history BEFORE choosing self.

    With two own cards left after the imposed root move, only the next own
    choice can branch; its last card is forced. This independent reference
    never passes a posterior into the solver under test.
    """
    assert len(after_first.hands[own]) == 2
    frontiers = defaultdict(list)
    opponents = tuple(s for s in Seat if s != own)
    def expand(current, lineup, mass):
        if current.next_player == own:
            frontiers[current].append((lineup, mass))
            return
        assert not current.finished
        view = observe(current, current.next_player)
        for move, probability in policy_distribution(view, lineup[current.next_player]):
            expand(play_card(current, current.next_player, move.card, announce_bela=move.bela),
                   lineup, mass * probability)
    for assignments in product(profiles, repeat=3):
        expand(after_first, dict(zip(opponents, assignments)), Fraction(1, len(profiles)**3))
    value = Fraction(0)
    for state, scenarios in frontiers.items():
        view = observe(state, own)
        choices = []
        for card in legal_cards(view.hand, view.current_trick, view.trump):
            child = play_card(state, own, card, announce_bela=announce_bela(view, card))
            choices.append(sum(mass * fixed_lineup_mean(child, own, lineup, 'random_v1')
                               for lineup, mass in scenarios))
        value += max(choices)
    return value


class EndgameReferenceTests(unittest.TestCase):
    def test_repeatable_planning_fixture_has_independently_verified_action_values(self):
        match = loads_user_match((Path(__file__).parent / 'fixtures' / 'known_endgame_planning.json').read_text())
        domains = match.state.evidence.domains
        deal = SampledDeal(tuple(sum(1 << i for i, d in enumerate(domains) if d == 1 << seat) for seat in Seat))
        state = SimulationBridge.from_match(match).resume(deal)
        own = state.next_player
        result = solve_known_endgame(state)
        expected = {'H_9': Fraction(-116), 'H_Q': Fraction(-1151, 30), 'S_8': Fraction(-54743, 1500)}
        self.assertEqual(result['best_cards'], ['S_8'])
        for row in result['moves']:
            value = Fraction(row['objective_fraction'])
            self.assertEqual(value, expected[row['card']])
            child = play_card(state, own, Card.parse(row['card']), announce_bela=row['bela'])
            self.assertEqual(value, explicit_scenario_optimum(child, own, POLICIES))

    def test_optimal_self_groups_latent_scenarios_before_choosing(self):
        match = loads_user_match((Path(__file__).parent / 'fixtures' / 'known_endgame_control.json').read_text())
        domains = match.state.evidence.domains
        self.assertTrue(all(d in (1, 2, 4, 8) for d in domains))
        deal = SampledDeal(tuple(sum(1 << i for i, d in enumerate(domains) if d == 1 << seat) for seat in Seat))
        state = SimulationBridge.from_match(match).resume(deal)
        own = state.next_player
        profiles = ('random_v1', 'tactical_v1')
        result = solve_known_endgame(state, opponent_policies=profiles)
        fixed = solve_known_endgame(state, self_policy='tactical_v1', opponent_policies=profiles)
        self.assertTrue(any(Fraction(a['objective_fraction']) > Fraction(b['objective_fraction'])
                            for a, b in zip(result['moves'], fixed['moves'])))
        for row in result['moves']:
            child = play_card(state, own, Card.parse(row['card']), announce_bela=row['bela'])
            self.assertEqual(Fraction(row['objective_fraction']), explicit_scenario_optimum(child, own, profiles))

    def test_exact_random_distribution_matches_independent_fraction_enumeration(self):
        _, state = known_endgame()
        result = solve_known_endgame(state, self_policy='random_v1', opponent_policies=('random_v1',))
        own = state.next_player
        for row in result['moves']:
            child = play_card(state, own, Card.parse(row['card']), announce_bela=row['bela'])
            outcomes = exact_random_outcomes(child, own.team)
            mean = sum(value * probability for value, _, probability in outcomes)
            success = sum(win * probability for _, win, probability in outcomes)
            variance = sum((value-mean)**2 * probability for value, _, probability in outcomes)
            self.assertEqual(Fraction(row['objective_fraction']), mean)
            self.assertEqual(Fraction(row['success_fraction']), success)
            self.assertEqual(Fraction(row['objective_variance_fraction']), variance)

    def test_posterior_keeps_profiles_fixed_rather_than_redrawing_them(self):
        a, b = PolicyMove(Card.parse('H_7'), False), PolicyMove(Card.parse('H_8'), False)
        profiles = (((a, Fraction(1)),), ((a, Fraction(1, 2)), (b, Fraction(1, 2))))
        first = {move: (chance, posterior) for move, chance, posterior in
                 opponent_distribution(profiles, (Fraction(1, 2),)*2)}
        self.assertEqual(first[a], (Fraction(3, 4), (Fraction(2, 3), Fraction(1, 3))))
        self.assertEqual(first[b], (Fraction(1, 4), (Fraction(0), Fraction(1))))
        after_b = {move: chance for move, chance, _ in opponent_distribution(profiles, first[b][1])}
        self.assertEqual(after_b[a], Fraction(1, 2))  # A fresh draw would give 3/4.

    def test_mixed_reference_agrees_with_enumerating_fixed_latent_lineups(self):
        _, state = known_endgame(played=20)
        own = state.next_player
        opponents = tuple(s for s in Seat if s != own)
        profiles = ('random_v1', 'tactical_v1')
        result = solve_known_endgame(state, self_policy='tactical_v1', opponent_policies=profiles)
        for row in result['moves']:
            child = play_card(state, own, Card.parse(row['card']), announce_bela=row['bela'])
            total = Fraction(0)
            for choices in product(profiles, repeat=3):
                lineup = dict(zip(opponents, choices))
                total += fixed_lineup_mean(child, own, lineup, 'tactical_v1') / 8
            self.assertEqual(Fraction(row['objective_fraction']), total)

    def test_optimal_self_is_no_worse_than_fixed_self_for_each_root_move(self):
        _, state = known_endgame(played=20)
        best = solve_known_endgame(state)
        fixed = solve_known_endgame(state, self_policy='tactical_v1')
        self.assertEqual({r['card'] for r in best['moves']}, {r['card'] for r in fixed['moves']})
        for exact, baseline in zip(best['moves'], fixed['moves']):
            self.assertGreaterEqual(Fraction(exact['objective_fraction']), Fraction(baseline['objective_fraction']))
        self.assertEqual(state, known_endgame(played=20)[1])

    def test_root_bela_is_preserved_and_success_objective_is_exact(self):
        _, source = endgame()
        hands = tuple(map(cards, (
            'H_K H_Q S_7 S_8 D_7 D_8 C_10 C_A',
            'H_9 H_8 S_9 S_10 D_9 D_10 C_7 C_8',
            'H_J H_A S_J S_Q D_J D_Q C_9 C_J',
            'H_10 H_7 S_K S_A D_K D_A C_Q C_K')))
        state = resolve_declarations(start_play(hands, trump=source.trump, dealer=source.dealer, caller=source.caller))
        for trick in source.completed_tricks:
            for card in trick.cards:
                state = play_card(state, state.next_player, card)
        state = replace(state, declaration_history=tuple(CardsRevealedAnnouncement(s, hands[s]) for s in Seat))
        result = solve_known_endgame(state, objective='contract_success')
        self.assertTrue(all(r['bela'] for r in result['moves']))
        self.assertTrue(all(r['objective_fraction'] == r['success_fraction'] for r in result['moves']))
        self.assertTrue(all(0 <= r['success_probability'] <= 1 for r in result['moves']))

    def test_policy_distributions_normalize_and_are_legal(self):
        _, state = known_endgame(played=20)
        view = observe(state, state.next_player)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        for policy in POLICIES:
            choices = policy_distribution(view, policy)
            self.assertEqual(sum(p for _, p in choices), 1)
            self.assertTrue(all(move.card in legal and move.bela == announce_bela(view, move.card) for move, _ in choices))

    def test_hidden_hands_and_oversized_positions_are_rejected(self):
        _, hidden = endgame()
        with self.assertRaisesRegex(ValueError, 'publicly revealed'):
            solve_known_endgame(hidden)
        opening = resolve_declarations(start_play(HANDS, trump=hidden.trump, dealer=hidden.dealer, caller=hidden.caller))
        with self.assertRaisesRegex(ValueError, 'twelve'):
            solve_known_endgame(opening)

    def test_limits_never_return_partial_work_as_exact(self):
        _, state = known_endgame(played=20)
        for options in ({'seconds': 0}, {'max_nodes': 1}, {'cancelled': lambda: True}):
            with self.subTest(options=options), self.assertRaises(ReferenceLimit):
                solve_known_endgame(state, **options)
        for options in ({'opponent_policies': ()}, {'opponent_policies': ('unknown',)},
                        {'max_nodes': True}, {'seconds': float('inf')}, {'objective': 'match_win'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                solve_known_endgame(state, **options)


if __name__ == '__main__':
    unittest.main()
