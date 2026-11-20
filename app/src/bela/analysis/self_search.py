"""Monte Carlo continuation decisions indexed only by permitted information."""

from math import log, sqrt

from bela.domain.cards import Rank
from bela.rules.play import card_points, strength, trick_winner


SELF_SEARCH = "information_set_tree_v1"
SHARED_SELF_SEARCH = "shared_information_set_tree_v2"
BELA_CREDIT_SELF_SEARCH = "bela_credit_shared_tree_v3"
LEARN_EVALUATE_SELF_SEARCH = "learn_then_evaluate_v1"
COMPETENT_LEARN_EVALUATE_SELF_SEARCH = "learn_then_evaluate_v2"
DIRECT_COMPETENT_SELF_POLICY = "direct_competent_mix_v1"
LEARN_EVALUATE_POLICIES = (LEARN_EVALUATE_SELF_SEARCH, COMPETENT_LEARN_EVALUATE_SELF_SEARCH)
SELF_POLICIES = (SELF_SEARCH, SHARED_SELF_SEARCH, BELA_CREDIT_SELF_SEARCH,
                 *LEARN_EVALUATE_POLICIES, DIRECT_COMPETENT_SELF_POLICY, "tactical_v1")


def information_key(view):
    # Declarations are fixed for this analysis. Never include sampled hands,
    # opponent profile identities, trial number or the root sampled world.
    return (view.player, view.hand, view.trump, view.dealer, view.caller,
            view.match_score, view.completed_tricks, view.current_trick,
            view.remaining_counts, view.bela_announcements)


def losing_trump_discard(view, legal):
    """Conservative self-play heuristic for an already lost trump trick.

    Prefer the cheapest/weakest trump only if every legal card is a losing
    trump and an opponent's win is certain: we act last, or their jack cannot
    be beaten. Otherwise keep the complete search choice. This preserves a
    useful trump for later; it is not a proof of optimal whole-deal play.
    Uses only our hand, the current public trick and legal actions.
    """
    trick = view.current_trick
    if len(legal) < 2 or not trick.cards or any(c.suit != view.trump for c in legal):
        return None
    winner = trick_winner(trick, view.trump)
    if winner.team == view.player.team:
        return None
    winning_card = trick.cards[(int(winner)-int(trick.leader)) % 4]
    if winning_card.suit != view.trump:
        return None
    if len(trick.cards) != 3 and winning_card.rank != Rank.JACK:
        return None
    if any(strength(c, view.trump) > strength(winning_card, view.trump) for c in legal):
        return None
    return min(legal, key=lambda c: (card_points(c, view.trump), strength(c, view.trump)))


class SelfSearch:
    """UCT decisions shared across worlds with identical public observations.

    New nodes explore uniformly except for the narrow losing-trump preference.
    Only fully completed paired trials update action values.
    This finite tree approximates future replanning; it does not run a fresh
    full root search recursively at every future turn.
    """

    def __init__(self):
        self.nodes = {}
        self.selections = 0
        self.forced_selections = 0
        self.exploration_selections = 0
        self.value_selections = 0
        self.losing_trump_selections = 0

    def select(self, view, legal, rng):
        key = information_key(view)
        node = self.nodes.setdefault(key, {card: [0, 0.0] for card in legal})
        discard = losing_trump_discard(view, legal)
        if discard is not None:
            # Retain every legal action in the node for honest coverage/frozen
            # fallback accounting. No unobserved action receives a reward.
            self.losing_trump_selections += 1
            self.selections += 1
            return (discard,)[rng.randrange(1)], (key, discard)
        unexplored = [card for card in legal if not node[card][0]]
        if unexplored:
            choices = unexplored
        else:
            visits = sum(row[0] for row in node.values())
            values = {card: total / count + sqrt(2 * log(visits) / count)
                      for card, (count, total) in node.items()}
            best = max(values.values())
            choices = [card for card in legal if values[card] == best]
        if len(legal) == 1:
            self.forced_selections += 1
        elif unexplored:
            self.exploration_selections += 1
        else:
            self.value_selections += 1
        card = choices[rng.randrange(len(choices))]
        self.selections += 1
        return card, (key, card)

    def commit(self, trace, reward):
        if not 0 <= reward <= 1:
            raise ValueError("Self-search reward must be normalized to [0, 1].")
        for key, card in trace:
            row = self.nodes[key][card]
            row[0] += 1
            row[1] += reward

    def statistics(self):
        decisions = [node for node in self.nodes.values() if len(node) > 1]
        visits = [sum(row[0] for row in node.values()) for node in decisions]
        return {"nodes": len(self.nodes), "selections": self.selections,
                "committed_actions": sum(row[0] for node in self.nodes.values() for row in node.values()),
                "revisited_nodes": sum(sum(row[0] for row in node.values()) > 1
                                       for node in self.nodes.values()),
                "decision_nodes": len(decisions),
                "decision_nodes_revisited": sum(n > 1 for n in visits),
                "decision_nodes_fully_expanded": sum(all(row[0] for row in node.values()) for node in decisions),
                "decision_node_visit_histogram": {
                    "zero": sum(n == 0 for n in visits), "one": sum(n == 1 for n in visits),
                    "two_to_three": sum(2 <= n <= 3 for n in visits),
                    "four_to_seven": sum(4 <= n <= 7 for n in visits),
                    "eight_plus": sum(n >= 8 for n in visits)},
                "attempted_forced_selections": self.forced_selections,
                "attempted_exploration_selections": self.exploration_selections,
                "attempted_value_selections": self.value_selections,
                "attempted_losing_trump_selections": self.losing_trump_selections,
                "self_play_heuristics": ["certain_losing_trump_v1"]}


def shared_context(view, legal):
    """Deliberately coarse public context, never a replacement for an exact key.

    Past trick order and scores are omitted to reuse evidence. Consequently
    pooled returns are a biased prior, not interchangeable state values.
    """
    from bela.rules.play import trick_winner
    trick = view.current_trick
    winner = trick_winner(trick, view.trump) if trick.cards else None
    return (view.hand, view.trump, view.caller.team == view.player.team,
            len(trick.cards), trick.cards[0].suit if trick.cards else None,
            (int(winner) - int(view.player)) % 4 if winner is not None else None,
            tuple(legal))


class SharedSelfSearch(SelfSearch):
    """Experimental UCT with bounded priors learned across public contexts.

    At most two pseudo-visits per action guide sparse exact nodes. Exact
    evidence eventually dominates; no fixed tactical continuation is used.
    Pools live for one analysis and update only on completed paired trials.
    """

    def __init__(self):
        super().__init__()
        self.pools = {}
        self.shared_selections = 0

    def context(self, view, legal):
        return shared_context(view, legal)

    def select(self, view, legal, rng):
        if len(legal) == 1 or losing_trump_discard(view, legal) is not None:
            return super().select(view, legal, rng)
        key = information_key(view)
        node = self.nodes.setdefault(key, {card: [0, 0.0] for card in legal})
        context = self.context(view, legal)
        pool = self.pools.setdefault(context, {card: [0, 0.0] for card in legal})
        # Subtract this exact node so it cannot provide its own prior.
        borrowed = {card: (pool[card][0] - node[card][0],
                           pool[card][1] - node[card][1]) for card in legal}
        usable = all(count >= 2 for count, _ in borrowed.values())
        if usable:
            stats = {card: (node[card][0] + 2,
                           node[card][1] + 2 * total / count)
                     for card, (count, total) in borrowed.items()}
            visits = sum(count for count, _ in stats.values())
            values = {card: total / count + sqrt(2 * log(visits) / count)
                      for card, (count, total) in stats.items()}
            best = max(values.values())
            choices = [card for card in legal if values[card] == best]
            self.shared_selections += 1
        else:
            unexplored = [card for card in legal if not node[card][0]]
            if unexplored:
                choices = unexplored
                self.exploration_selections += 1
            else:
                visits = sum(row[0] for row in node.values())
                values = {card: total / count + sqrt(2 * log(visits) / count)
                          for card, (count, total) in node.items()}
                best = max(values.values())
                choices = [card for card in legal if values[card] == best]
                self.value_selections += 1
        self.selections += 1
        card = choices[rng.randrange(len(choices))]
        return card, (key, card, context)

    def commit(self, trace, reward):
        if not 0 <= reward <= 1:
            raise ValueError("Self-search reward must be normalized to [0, 1].")
        for edge in trace:
            key, card = edge[:2]
            super().commit([(key, card)], reward)
            if len(edge) == 3:
                row = self.pools[edge[2]][card]
                row[0] += 1
                row[1] += reward

    def statistics(self):
        return super().statistics() | {
            "shared_contexts": len(self.pools),
            "attempted_shared_value_selections": self.shared_selections,
            "shared_prior_max_visits_per_action": 2,
            "shared_prior_is_approximate": True}


class BelaCreditSelfSearch(SharedSelfSearch):
    """Experimental v2 prior with only a three-state public Bela credit guard."""

    def context(self, view, legal):
        # There can be at most one timely Bela. Announcement timing and which
        # partner announced do not split the same team's scoring credit.
        credit = (view.bela_announcements[0].player.team == view.player.team
                  if view.bela_announcements else None)
        return shared_context(view, legal), credit

    def statistics(self):
        return super().statistics() | {"bela_credit_compatibility_guard": True}
