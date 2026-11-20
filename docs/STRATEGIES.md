# Hidden strategies in simulated matches

**Hidden five-strategy mix** is the default Move advice model. The real strategies
of your partner and opponents are unknown. Each Monte Carlo trial represents a
possible match, with an independently chosen profile for each of those three
players. Every profile has probability 1/5; duplicates are allowed.

| Intended level | Profile | Decision logic |
| --- | --- | --- |
| 1 | Random (`random_v1`) | Uniformly choose a legal card |
| 2 | Basic (`simple_v1`) | Lead plain aces or a long suit, donate while partner currently wins, use a cheap current winner |
| 3 | Cautious (`cautious_v1`) | Preserve points on unsecured tricks; donate when last to act and our team wins |
| 4 | Card counting (`counting_v1`) | Track played cards and public reveals/voids, recognize promoted winners, donate when public evidence secures the trick |
| 5 | Tactical (`tactical_v1`) | Add trump-control leads, avoid known cut risks and preserve outstanding winners when discarding |

These are increasing levels of intended sophistication, not measured Elo or a
guarantee that a higher level wins every matchup. All five obey the same Bela
rules and announce a timely bela. Equal heuristic choices use random tie breaks.

## What stays hidden

Assignments belong to the internal simulator. No policy receives the lineup or
other players' profile identities; it receives only its own hand and public game
information. Our future simulated choices now use a bounded information-set
Monte Carlo tree (`information_set_tree_v1`), without being told which strategies
the other three players received. New nodes explore legal choices and later
visits use simulated values. Tactical is retained only as an explicit historical
self-model option. The root card is evaluated
across all sampled possibilities, not chosen after seeing an individual lineup.

The UI and analysis response report the model's uniform weights and available
profiles, never a guessed strategy label for a real player. Assignments are not
saved as facts in real-game archives. Observed choices do not update profile
weights in this version; we are not modelling or learning individual behavior.

## Lifetime and fair comparisons

Every hypothetical match gets one lineup. It is shared by every candidate root
card, remains fixed through all subsequent moves and is reused across deals in
that match. Another hypothetical match gets a new independent draw.

`StrategyLineup.for_trial(match_id, seed, trial_index, player)` derives a separate
reproducible lineup seed. Deal numbers, revisions, cards and rejection counts do
not enter the identity. Consequently, trial i at a later deal of the same match
keeps trial i's profiles, with the same analysis seed. Changing the analysis seed
draws another set of hypothetical matches. Profiles are not independently
redrawn per move, candidate or deal.

Each completed trial contributes one outcome to every card. Card values and
success estimates accumulate as running averages over these shared trials.
Interrupted trials contribute nothing to any card. Pooled percentages are estimates
under the explicitly chosen equal-weight mixture, not measured human frequencies.

The advisor still simulates the remainder of the **current deal**. It does not
play future deals or optimize match victory. Score-aware advice remains deferred,
especially around 800+; the existing victory rule stays strictly above 1000.

## Full-match simulator context

`analysis/lineups.py` also provides a `StrategyMatch` wrapper around the existing
full-simulator `MatchSession`. `with_current` and `next_deal` keep the same lineup
object until that match ends. New deals carry settled score and next dealer;
the existing rules handle >1000, ties and belot.

```python
from random import Random
from bela.analysis.lineups import StrategyMatch
from bela.domain.game import Seat
from bela.gameplay.simulation import resolve_declarations

# state is a full simulator state, with declarations already resolved.
game = StrategyMatch.start(state, player=Seat.ZERO, seed=123)
rng = Random(456)
while not game.current.finished:
    game = game.play_next(rng)

if game.winner is None:
    # Supply the next hands, caller and trump using existing simulator inputs.
    game = game.next_deal(next_hands, trump=next_trump, caller=next_caller)
    game = game.with_current(resolve_declarations(game.current))
    # Same hidden lineup, a new deal, and the previous settled score.
```

This context does not invent a bidding policy or generate future deals. The
advisor's `UserMatch` archives retain supplied observations only. Profile context
is an internal simulation concern, not an archive schema change.

## Tests

`test_strategy_lineups.py` checks five-profile sampling, approximately uniform
marginals, duplicate assignments, all tracked seats, reproducible identities,
paired candidate consistency, unchanged player archives and information boundaries.
It also plays a complete multi-deal match until >1000 while checking the lineup
never changes. Tactical fixtures cover unsecured donations, public following
obligations, fourth-player donations and a ten promoted after its ace was played.
