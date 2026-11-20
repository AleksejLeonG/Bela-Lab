"""Immutable learned continuation values, with explicit cold-state fallbacks."""
from hashlib import sha256
from random import Random
from types import MappingProxyType

from bela.analysis.self_search import information_key, losing_trump_discard
from bela.analysis.policies import _choose_from_legal


COMPETENT_FALLBACK_PROFILES = ('cautious_v1', 'counting_v1', 'tactical_v1')


def fallback_profile(match_id, seed, trial):
    """One independent self style per hypothetical match/trial, shared by cards.

    This stream cannot shift hand sampling, opponent profiles or tie breaks.
    Random and Basic remain opponent assumptions, never self fallback profiles.
    """
    digest = sha256(f'bela-competent-self-fallback-v1:{match_id}:{seed}:{trial}'.encode()).digest()
    return COMPETENT_FALLBACK_PROFILES[Random(int.from_bytes(digest[:8], 'big')).randrange(len(COMPETENT_FALLBACK_PROFILES))]


def learning_seed(seed, match_id):
    """Domain-separate learning from the unchanged evaluation random stream."""
    digest = sha256(f'bela-policy-learning-v1:{seed}:{match_id}'.encode()).digest()
    value = int.from_bytes(digest[:8], 'big')
    return value if value != seed else value ^ 1


class FrozenSelfPolicy:
    """Greedy means from a copied tree; evaluation never updates action values.

    Outside the certain-losing-trump preference, every legal action needs at
    least one learned observation. Unseen or incomplete nodes use the explicitly
    selected fallback. Learned nodes never consult that fallback. The resulting
    stochastic policy stays fixed.
    Counters are diagnostics only and cannot influence choices.
    """

    def __init__(self, nodes, *, fallback_mode='uniform_legal_v1'):
        if fallback_mode not in ('uniform_legal_v1', 'competent_mix_v1'):
            raise ValueError('Unknown learned-policy fallback mode.')
        self.fallback_mode = fallback_mode
        self.nodes = MappingProxyType({key: MappingProxyType({
            card: tuple(row) for card, row in node.items()}) for key, node in nodes.items()})
        self.selections = self.forced = self.learned = self.unseen = self.incomplete = 0
        self.losing_trump_selections = 0
        self.profile_uses = dict.fromkeys(COMPETENT_FALLBACK_PROFILES, 0)

    def select(self, view, legal, rng, *, fallback_policy=None):
        if not legal:
            raise ValueError('A frozen policy requires a legal move.')
        self.selections += 1
        choices = legal
        if len(legal) == 1:
            self.forced += 1
        else:
            discard = losing_trump_discard(view, legal)
            if discard is not None:
                self.losing_trump_selections += 1
                return (discard,)[rng.randrange(1)]
            node = self.nodes.get(information_key(view))
            if node is None:
                self.unseen += 1
            elif set(node) != set(legal):
                raise ValueError('Frozen legal actions disagree with the observation.')
            elif any(node[card][0] == 0 for card in legal):
                self.incomplete += 1
            else:
                means = {card: node[card][1] / node[card][0] for card in legal}
                best = max(means.values())
                choices = tuple(card for card in legal if means[card] == best)
                self.learned += 1
            if self.fallback_mode == 'competent_mix_v1' and (node is None or any(node[card][0] == 0 for card in legal)):
                if fallback_policy not in COMPETENT_FALLBACK_PROFILES:
                    raise ValueError('A competent fallback requires its assigned trial profile.')
                self.profile_uses[fallback_policy] += 1
                return _choose_from_legal(view, rng, fallback_policy, legal).card
        return choices[rng.randrange(len(choices))]

    def statistics(self):
        return {'nodes': len(self.nodes), 'selections': self.selections,
                'attempted_forced_selections': self.forced,
                'attempted_exploration_selections': 0,
                'attempted_value_selections': self.learned,
                'attempted_losing_trump_selections': self.losing_trump_selections,
                'self_play_heuristics': ['certain_losing_trump_v1'],
                'fallback_unseen_selections': self.unseen,
                'fallback_incomplete_selections': self.incomplete,
                'fallback_policy': self.fallback_mode, 'values_frozen': True,
                'fallback_profile_weights': ({p: 1/len(COMPETENT_FALLBACK_PROFILES) for p in COMPETENT_FALLBACK_PROFILES}
                                             if self.fallback_mode == 'competent_mix_v1' else {}),
                'fallback_profile_selections': dict(self.profile_uses),
                'fallback_assignment_scope': 'hypothetical_match' if self.fallback_mode == 'competent_mix_v1' else None}
