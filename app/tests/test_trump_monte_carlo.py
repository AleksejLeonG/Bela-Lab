"""Pre-talon privacy, paired calling outcomes and exact continuation checks."""
from dataclasses import replace
from fractions import Fraction
from math import sqrt
from random import Random
from threading import Event
import unittest
from unittest.mock import patch

import bela.analysis.trump_monte_carlo as mc
from bela.analysis.endgame_reference import policy_distribution, solve_known_endgame
from bela.analysis.lineups import StrategyLineup
from bela.analysis.rollout_random import TrialRandomness
from bela.domain.cards import Suit, deck
from bela.domain.game import Seat
from bela.gameplay.calling import CallingObservation, CallingState
from bela.gameplay.simulation import observe
from test_calling import observation, cards
from test_endgame_reference import known_endgame
from test_monte_carlo import HANDS


HAND = 'C_9 C_J C_K H_A S_Q D_A'


class TrumpMonteCarloTests(unittest.TestCase):
    def config(self, **kwargs):
        return mc.TrumpMonteCarloConfig(**({'samples':8,'seconds':30} | kwargs))

    def test_sampling_has_exact_six_known_cards_and_no_fixed_talon(self):
        v = observation(HAND)
        additions = set()
        for seed in range(50):
            hands = mc._sample_hands(v, Random(seed))
            self.assertEqual(set(hands[v.player][:6]), set(v.hand))
            self.assertEqual(tuple(map(len,hands)), (8,8,8,8))
            self.assertEqual({c for h in hands for c in h}, set(deck()))
            additions.add(hands[v.player][6:])
        self.assertGreater(len(additions), 40)

    def test_paired_actions_share_hands_styles_and_randomness(self):
        calls = []
        original = mc._rollout
        def record(hands, calling, own, lineup, style, randomness, check):
            calls.append((hands,lineup,style,id(randomness),calling))
            return original(hands,calling,own,lineup,style,randomness,check)
        with patch.object(mc,'_rollout',record):
            r = mc.analyze_trumps(observation(HAND), self.config())
        self.assertEqual(r['completed_samples'],8)
        self.assertEqual(len(calls),40)
        for start in range(0,40,5):
            group = calls[start:start+5]
            self.assertTrue(all(c[:4]==group[0][:4] for c in group))
            self.assertEqual({c[4].trump for c in group[:4]},set(Suit))
        self.assertEqual(len(r['comparisons']),10)
        self.assertTrue(all(row['samples']==8 for row in r['rankings']))
        self.assertEqual(sum(r['model']['other_player_weights'].values()),1)
        self.assertFalse(r['model']['nested_monte_carlo'])
        self.assertNotIn('hands',r)

    def test_all_positions_and_pass_branch_finish_legally(self):
        for dealer in Seat:
            state = CallingState(dealer)
            while state.next_player != Seat.ZERO:
                state = state.pass_turn(state.next_player)
            v = CallingObservation(Seat.ZERO,cards(HAND),state)
            r = mc.analyze_trumps(v,self.config(samples=2))
            self.assertEqual(r['status'],'complete')
            self.assertEqual(r['calling_position'],len(state.passes)+1)
            self.assertEqual(len(r['rankings']),4 if state.forced else 5)
            if state.forced:
                self.assertTrue(all(row['action']=='call' for row in r['rankings']))
            else:
                hands = mc._sample_hands(v,Random(3))
                result = mc._finish_calling(v,hands,None)
                self.assertIsNotNone(result.caller)
                self.assertNotEqual(result.caller,v.player)

    def test_passing_is_a_real_ranked_candidate_not_a_fixed_threshold(self):
        def outcome(hands, calling, own, lineup, style, randomness, check):
            value = 100 if calling.caller != own else 0
            return ((value,0),1,1,None)
        with patch.object(mc,'_rollout',outcome):
            r = mc.analyze_trumps(observation(HAND),self.config())
        self.assertEqual(r['recommendation'],{'action':'pass','suit':None})
        self.assertEqual(r['rankings'][0]['expected_point_difference'],100)

    def test_no_estimate_falls_back_without_fake_probabilities(self):
        v = observation(HAND,forced=True)
        for cfg, cancelled, status in ((self.config(seconds=0),None,'time_limit'),
                                      (self.config(),lambda:True,'cancelled')):
            r = mc.analyze_trumps(v,cfg,cancelled=cancelled)
            self.assertEqual(r['status'],status)
            self.assertEqual(r['recommendation_source'],'heuristic_fallback')
            self.assertEqual(r['recommendation']['action'],'call')
            self.assertTrue(all(row['rank'] is None and row['success_probability'] is None for row in r['rankings']))

    def test_partial_trial_is_discarded_for_every_action(self):
        stopped = Event()
        count = [0]
        original = mc._rollout
        def stop(*args):
            result = original(*args)
            count[0] += 1
            if count[0]==7:
                stopped.set()
            return result
        with patch.object(mc,'_rollout',stop):
            r = mc.analyze_trumps(observation(HAND),self.config(),cancelled=stopped.is_set)
        self.assertEqual(r['status'],'cancelled')
        self.assertEqual(r['completed_samples'],1)
        self.assertEqual(r['discarded_trials'],1)
        self.assertTrue(all(row['samples']==1 for row in r['rankings']))

    def test_pass_conditioning_is_explicit_and_rejection_is_bounded(self):
        v = observation(HAND,forced=True)
        with patch.object(mc,'_matches_passes',return_value=False) as matches:
            r = mc.analyze_trumps(v,self.config(condition_on_passes=True,max_sampling_attempts=3))
            self.assertEqual(matches.call_count,3)
        self.assertEqual(r['status'],'sampling_limit')
        self.assertEqual(r['completed_samples'],0)
        self.assertEqual(r['model']['past_pass_inference'],'position_control_v2')
        with patch.object(mc,'_matches_passes',side_effect=AssertionError('Unexpected card deduction')):
            r = mc.analyze_trumps(v,self.config(samples=1))
        self.assertEqual(r['model']['past_pass_inference'],'none')

    def test_conditioning_and_future_calls_see_only_six_not_the_sampled_talons(self):
        v = observation(HAND,forced=True)
        hands = mc._sample_hands(v,Random(2))
        original = mc.advise_trump
        seen = []
        def checked(view):
            seen.append(view)
            self.assertEqual(len(view.hand),6)
            self.assertEqual(set(view.hand),set(hands[view.player][:6]))
            return original(view)
        with patch.object(mc,'advise_trump',checked):
            mc._matches_passes(v,hands)
        self.assertTrue(seen)

    def test_seed_and_card_order_reproduce_values(self):
        v = observation(HAND)
        one = mc.analyze_trumps(v,self.config())
        two = mc.analyze_trumps(replace(v,hand=tuple(reversed(v.hand))),self.config())
        one.pop('elapsed_seconds'); two.pop('elapsed_seconds')
        self.assertEqual(one,two)

    def test_belot_is_terminal_without_invented_points(self):
        hands = tuple(tuple(c for c in deck() if c.suit==suit) for suit in Suit)
        own = Seat.ONE
        calling = CallingState(Seat.THREE).call_trump(Seat.ZERO,Suit.HEARTS)
        value = mc._rollout(hands,calling,own,StrategyLineup.assign(own,3),
                            'tactical_v1',TrialRandomness(3),lambda:None)
        self.assertEqual(value,((0,0),0,None,0))

    def test_rollout_matches_exact_small_endgame_profile_mixture(self):
        _, state = known_endgame(played=24)
        own = state.next_player
        view = observe(state,own)
        means, second, probabilities = [], [], []
        for policy in mc.COMPETENT_FALLBACK_PROFILES:
            exact = solve_known_endgame(state,self_policy=policy)
            rr = {r['card']:r for r in exact['moves']}
            dist = policy_distribution(view,policy)
            means.append(sum(p*Fraction(rr[str(m.card)]['objective_fraction']) for m,p in dist))
            second.append(sum(p*(Fraction(rr[str(m.card)]['objective_variance_fraction'])+
                Fraction(rr[str(m.card)]['objective_fraction'])**2) for m,p in dist))
            probabilities.append(sum(p*Fraction(rr[str(m.card)]['success_fraction']) for m,p in dist))
        mean, moment, probability = sum(means)/3, sum(second)/3, sum(probabilities)/3
        calling = CallingState(state.dealer)
        while calling.next_player != state.caller:
            calling = calling.pass_turn(calling.next_player)
        calling = calling.call_trump(state.caller,state.trump)
        values, successes = [], []
        with patch.object(mc,'start_play',return_value=state), patch.object(mc,'resolve_declarations',lambda s:s):
            for i in range(600):
                style = Random(9000+i).choice(mc.COMPETENT_FALLBACK_PROFILES)
                recorded, success, _, _ = mc._rollout(HANDS,calling,own,StrategyLineup.assign(own,i),
                    style,TrialRandomness(10000+i),lambda:None)
                values.append(recorded[own.team]-recorded[1-own.team]); successes.append(success)
        self.assertLessEqual(abs(sum(values)/600-float(mean)),6*sqrt(float(moment-mean*mean)/600)+1e-9)
        self.assertLessEqual(abs(sum(successes)/600-float(probability)),6*sqrt(float(probability*(1-probability))/600)+1e-9)

    def test_validation_rejects_private_extra_cards_and_invalid_settings(self):
        for cfg in ({'samples':True},{'samples':0},{'seconds':float('nan')},{'seed':-1},
                    {'condition_on_passes':1},{'max_sampling_attempts':0}):
            with self.assertRaises(ValueError):
                self.config(**cfg)
        with self.assertRaises(ValueError):
            mc.analyze_trumps(object())
        with self.assertRaises(ValueError):
            replace(observation(HAND),hand=cards(HAND+' H_7 H_8'))


if __name__=='__main__':
    unittest.main()
