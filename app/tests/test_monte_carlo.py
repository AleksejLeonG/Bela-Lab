"""Policy boundaries, paired trials and exhaustive random-policy endgames."""

from fractions import Fraction
import json
from math import sqrt
from random import Random
import unittest

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves, confidence_interval
from bela.analysis.policies import POLICIES, announce_bela, choose_move
from bela.domain.cards import Card, Rank, Suit
from bela.domain.game import PlayerObservation, Seat
from bela.rules.play import legal_cards
from bela.gameplay.simulation import (observe, play_card, resolve_declarations,
                                      settle_play, start_play)
from bela.gameplay.tracking import (DealSetup, FinishDeclarations, Play, Reveal, UserMatch,
                                    AddEvent)
from bela.storage.user_storage import dumps_user_match


def cards(text):
    return tuple(Card.parse(c) for c in text.split())


HANDS = tuple(map(cards, (
    "H_J H_7 S_7 S_8 D_7 D_8 C_10 C_A",
    "H_9 H_8 S_9 S_10 D_9 D_10 C_7 C_8",
    "H_A H_Q S_J S_Q D_J D_Q C_9 C_J",
    "H_10 H_K S_K S_A D_K D_A C_Q C_K",
)))


def endgame(played=24, caller=Seat.ONE):
    full = resolve_declarations(start_play(HANDS, trump=Suit.HEARTS,
                                          dealer=Seat.THREE, caller=caller))
    plays = []
    for index in range(played):
        actor = full.next_player
        view = observe(full, actor)
        legal = legal_cards(view.hand, view.current_trick, view.trump)
        if index < 24:
            suit = (Suit.SPADES, Suit.DIAMONDS, Suit.CLUBS)[index // 8]
            options = [c for c in legal if c.suit == suit]
            card = min(options, key=lambda c: (_plain_strength(c), c.id))
        else:
            card = legal[0]
        full = play_card(full, actor, card)
        plays.append(Play(actor, card))
    own = full.next_player
    setup = DealSetup(own, HANDS[own], Seat.THREE, caller, Suit.HEARTS, (810, 770))
    match = UserMatch.start(setup)
    for seat in Seat:
        match = match.perform(AddEvent(Reveal(seat, HANDS[seat])))
    winner = resolve_declarations(start_play(HANDS, trump=Suit.HEARTS,
                                            dealer=Seat.THREE, caller=caller)).meld_contest.winning_team
    match = match.perform(AddEvent(FinishDeclarations(winner)))
    for play in plays:
        match = match.perform(AddEvent(play))
    return match, full


def _plain_strength(card):
    return ("7", "8", "9", "J", "Q", "K", "10", "A").index(card.rank.value)


def exact_random_outcomes(state, team):
    """Enumerate every legal continuation with exact uniform branch weights."""
    from bela.rules.play import legal_cards
    if state.finished:
        result = settle_play(state)
        success = int(result.caller_passed if team == result.caller_team else not result.caller_passed)
        difference = result.recorded[team] - result.recorded[1 - team]
        return [(difference, success, Fraction(1))]
    view = observe(state, state.next_player)
    legal = legal_cards(view.hand, view.current_trick, view.trump)
    outcomes = []
    for card in legal:
        child = play_card(state, view.player, card, announce_bela=announce_bela(view, card))
        outcomes += [(points, success, probability / len(legal))
                     for points, success, probability in exact_random_outcomes(child, team)]
    return outcomes


class MonteCarloTests(unittest.TestCase):
    def test_random_rollouts_agree_with_exact_endgame_distribution(self):
        match, full = endgame()
        self.assertEqual(len(match.state.legal_actions), 2)
        before = dumps_user_match(match)
        result = analyze_moves(match, MonteCarloConfig(samples=600, seconds=30, policy="random_v1"))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["completed_samples"], 600)
        for row in result["moves"]:
            state = play_card(full, full.next_player, Card.parse(row["card"]), announce_bela=row["bela"])
            exact = exact_random_outcomes(state, match.initial.player.team)
            self.assertEqual(sum(p for _, _, p in exact), 1)
            mean = float(sum(points * p for points, _, p in exact))
            variance = float(sum((points - mean) ** 2 * p for points, _, p in exact))
            probability = float(sum(success * p for _, success, p in exact))
            self.assertLessEqual(abs(row["expected_point_difference"] - mean),
                                 6 * sqrt(variance / 600) + 1e-8)
            self.assertLessEqual(abs(row["success_probability"] - probability),
                                 6 * sqrt(probability * (1 - probability) / 600) + 1e-8)
            self.assertLessEqual(row["objective_interval"][0], mean)
            self.assertGreaterEqual(row["objective_interval"][1], mean)
            self.assertEqual(row["samples"], 600)
        self.assertEqual(before, dumps_user_match(match))
        self.assertEqual(len(result["comparisons"]), 1)
        self.assertNotIn('"hands"', json.dumps(result))
        self.assertNotIn('"masks"', json.dumps(result))

    def test_seed_reproduces_estimates_and_pairs_use_same_denominator(self):
        match, _ = endgame()
        config = MonteCarloConfig(samples=12, seconds=30, seed=19)
        first = analyze_moves(match, config)
        second = analyze_moves(match, config)
        self.assertEqual(first["moves"], second["moves"])
        self.assertEqual(first["comparisons"], second["comparisons"])
        rows = {r["card"]: r for r in first["moves"]}
        for pair in first["comparisons"]:
            self.assertAlmostEqual(pair["mean_difference"], rows[pair["first"]]["objective_mean"]
                                   - rows[pair["second"]]["objective_mean"])
        self.assertTrue(all(row["samples"] == 12 for row in rows.values()))

    def test_contract_objective_and_defensive_success_definition(self):
        for caller in (Seat.ZERO, Seat.ONE):
            match, _ = endgame(caller=caller)
            result = analyze_moves(match, MonteCarloConfig(samples=12, seconds=30,
                                                          objective="contract_success"))
            expected = "make_contract" if match.initial.player.team == caller.team else "defeat_contract"
            self.assertEqual(result["success_definition"], expected)
            for row in result["moves"]:
                self.assertEqual(row["objective_mean"], row["success_probability"])
                self.assertEqual(row["objective_interval"], row["success_interval"])
                self.assertTrue(0 <= row["success_probability"] <= 1)

    def test_forced_move_does_not_invent_success_probabilities(self):
        match, _ = endgame(played=28)
        result = analyze_moves(match)
        self.assertEqual(result["status"], "forced_move")
        self.assertEqual(result["completed_samples"], 0)
        self.assertEqual(len(result["moves"]), 1)
        self.assertIsNone(result["moves"][0]["success_probability"])

    def test_root_bela_is_explicit_and_unavailable_turns_are_rejected(self):
        from test_sampling import match_with
        match = match_with(FinishDeclarations(None))
        result = analyze_moves(match, MonteCarloConfig(samples=2, seconds=30))
        rows = {row["card"]: row for row in result["moves"]}
        self.assertTrue(rows["H_Q"]["bela"])
        self.assertTrue(rows["H_K"]["bela"])
        self.assertFalse(rows["S_A"]["bela"])
        changed = match.perform(AddEvent(Play(Seat.ZERO, Card.parse("H_Q"), True)))
        with self.assertRaises(ValueError):
            analyze_moves(changed)
        with self.assertRaises(ValueError):
            analyze_moves(match_with())
        with self.assertRaises(ValueError):
            analyze_moves(match, {})

    def test_zero_budget_and_cancellation_discard_unpaired_work(self):
        match, _ = endgame()
        result = analyze_moves(match, MonteCarloConfig(seconds=0))
        self.assertEqual((result["status"], result["completed_samples"]), ("time_limit", 0))
        self.assertTrue(all(row["rank"] is None for row in result["moves"]))
        result = analyze_moves(match, cancelled=lambda: True)
        self.assertEqual(result["status"], "cancelled")
        checks = 0
        def stop_during_rollout():
            nonlocal checks
            checks += 1
            return checks > 5
        result = analyze_moves(match, MonteCarloConfig(seconds=30), cancelled=stop_during_rollout)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["completed_samples"], 0)
        self.assertEqual(result["discarded_trials"], 1)
        self.assertTrue(all(row["samples"] == 0 for row in result["moves"]))

    def test_policy_uses_only_observations_and_always_plays_legally(self):
        for policy in POLICIES:
            state = resolve_declarations(start_play(HANDS, trump=Suit.HEARTS,
                                                    dealer=Seat.THREE, caller=Seat.ONE))
            rng = Random(53)
            while not state.finished:
                view = observe(state, state.next_player)
                self.assertIsInstance(view, PlayerObservation)
                self.assertFalse(hasattr(view, "hands"))
                move = choose_move(view, rng, policy)
                state = play_card(state, view.player, move.card, announce_bela=move.bela)
            self.assertEqual(len(state.completed_tricks), 8)
        with self.assertRaises(ValueError):
            choose_move(state, Random(1))

    def test_policy_hidden_world_invariance(self):
        from dataclasses import replace
        match, state = endgame()
        actor = state.next_player
        others = [s for s in Seat if s != actor]
        swapped = list(state.hands)
        swapped[others[0]], swapped[others[1]] = swapped[others[1]], swapped[others[0]]
        alternative = replace(state, hands=tuple(swapped))
        for policy in POLICIES:
            self.assertEqual(choose_move(observe(state, actor), Random(8), policy),
                             choose_move(observe(alternative, actor), Random(8), policy))

    def test_bounds_and_invalid_configuration(self):
        interval = confidence_interval(.5, 0, 1, 100, 3)
        self.assertTrue(0 <= interval[0] < .5 < interval[1] <= 1)
        self.assertLess(confidence_interval(.5, 0, 1, 1000, 3)[1], interval[1])
        for options in ({"samples": 0}, {"samples": True}, {"seconds": float("inf")},
                        {"seconds": -1}, {"seed": -1}, {"policy": "oracle"}, {"objective": "match_win"}):
            with self.assertRaises(ValueError):
                MonteCarloConfig(**options)
