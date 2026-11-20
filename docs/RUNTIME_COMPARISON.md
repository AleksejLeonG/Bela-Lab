# Three-way runtime-budget comparison

This compares three complete advice approaches, with their existing rules,
consistent-hand sampler, point-difference objective, position-aware calling,
and unchanged five-profile opponent mixture:

- `direct_competent_mix_v1`: no tree or learning. All simulated future self
  moves follow an equal mixture of Cautious, Card-counting and Tactical, with
  one style per hypothetical trial, shared across candidate cards.
- `learn_then_evaluate_v2`: learn, freeze, then evaluate; competent mixture only
  when frozen self values are unavailable or incomplete.
- `information_set_tree_v1`: the current default, learning during rollouts.

Direct mode is available through the self-policy configuration, batch CLI and
the dashboard's **Direct Monte Carlo (experimental)** option. It does not claim
optimal future play or access to hidden hands/profile identities.

## Protocol fixed before the fresh games

The six saved-position timing pilot succeeded for all modes at 0.5 seconds.
Its 18 original counts/timings are saved in
`saves/diagnostics/runtime-architecture-pilot-20261025/pilot.json`.

The primary comparison uses:

- Fresh seed 2026102508, indices 0–15: 16 matched sets, 48 complete matches.
  This covers every initial player/dealer combination.
- **0.5 seconds per nonforced decision**, including preparation, sampling and
  any learning. A 10,000-evaluation cap prevents the usual small sample target
  from ending runs before the runtime budget. Learning keeps its existing half
  of the post-preparation budget. Forced moves require no simulations.
- Exactly one game worker at a time. The model order cycles through all six
  permutations to reduce order/hardware-load bias. No concurrent model workers
  divide the available CPU unevenly. A temporary Windows keep-awake request
  prevents idle system sleep and is released on exit.
- Identical shuffled deals, dealer schedules, calling and actual assigned
  opponent profiles for each set. Compare the common deal prefix completed by
  all three modes; each mode still plays a full ordinary 1000-point match.
- Preserve every original input, advice result, completed evaluation and
  learning count, actual move and trick-point history. Wall-time limited
  estimates need not reproduce bit-for-bit; original estimates are retained.
- Accept `time_limit` results only with at least one complete paired evaluation.
  Stop before a move on zero estimates, unexpected status, worker/persistence
  failure, or an analysis overshoot beyond the budget plus 0.2 seconds. The
  learned mode must also complete at least one learning trial. Source changes
  during the experiment stop it. Never turn failed attempts into wins/losses.

Primary metric: paired net recorded points per three-way shared deal, clustered
by match set. Secondary metrics: match wins, own contracts made, elapsed advice
time, and actual learning/evaluation trial counts. Shared-prefix selection is
not an uncensored sample of all possible deals; reported uncertainty is
descriptive of this experimental schedule.

Use 12,000 matched-set bootstrap resamples, seed 2026102509, and three pairwise
comparisons. The exploratory percentile intervals use Bonferroni-adjusted
98.33% levels (5% family error split over three comparisons). They are not exact
finite-sample confidence guarantees.

A pragmatic five-net-point/deal noninferiority margin is fixed in advance:
prefer the simpler Direct approach only if both adjusted lower bounds against
the alternatives are at least -5. Also require its worst known-card root regret
in the timed sanity set to be at most five points, so an average-match result
does not conceal a large already-known endgame failure. Prefer learned over
current only with an adjusted lower bound above zero and the same endgame
sanity limit. Otherwise retain current. These are practical screening criteria,
not a declaration of optimality or equivalence from inconclusive results.
Recommendations apply to the tested half-second budget; larger budgets and
human opponents are outside this comparison's scope.

Before the fresh games, run the existing 20-position known-card regression set
under the same 0.5-second budget, with seeds 7, 42 and 119 for every mode. The
set includes deliberately selected challenges and is development/safety data,
not additional fresh strength evidence. It measures root regret against the
stated opponent model's exact optimal self continuation, not accuracy of the
Direct strategy assumption.

## Results — 2026-10-25

These results precede the subsequent [focused self-play improvement](SELF_PLAY_IMPROVEMENT.md).
The original source snapshots and advice records retain the tested behavior.

The run completed all 48 matches in 1,328.6 seconds (22.1 minutes), including
the timed endgame checks. No worker failures, missing estimates or runtime
overshoot stops occurred. The audit replayed all game archives, verified every
trick total and selected move, and checked 3,568 original decision records.
There were 142 deals in the three-way shared prefixes.

| Mode | Match wins | Net points/shared deal | Own contracts made | Mean advice time | Mean evaluation trials | Mean learning trials |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Direct competent mixture | 10/16 | +11.42 | 56/74 | 0.493 s | 79.3 | 0 |
| Learn then evaluate | 9/16 | +9.15 | 59/74 | 0.494 s | 36.3 | 38.1 |
| Current tree | 10/16 | +12.56 | 58/74 | 0.494 s | 74.1 | 0 |

Times and trial means exclude forced moves. Learning trials for the current
tree are zero in this table because it updates during evaluation rollouts;
it has no separate learning phase. Contract counts use the shared deals.

| Paired difference | Net points/shared deal | Exploratory adjusted interval |
| --- | ---: | ---: |
| Direct minus learned | +2.27 | [-8.39, +13.25] |
| Direct minus current | -1.14 | [-11.55, +7.51] |
| Learned minus current | -3.41 | [-20.81, +8.51] |

These are the predeclared 98.33% exploratory bootstrap intervals. All include
zero; neither an improvement nor equivalence has been established. Direct
fails the five-point noninferiority screen because both lower bounds are
below -5. This does not establish that Direct is worse; the comparison is
too uncertain to justify replacing the default under the stated rule.

The known-card checks selected an optimal root card in 60/60 analyses for
Direct, 60/60 for learned, and 57/60 for current. Current's largest root regret
was 1.87 points; all three passed the five-point sanity limit. This development
set is small and includes many tied choices, so it is not a general accuracy
rate. Direct's good result does not remove its fixed future-strategy assumption.

**Decision:** retain the current default. Keep Direct available as an
experimental simpler approach. The separate learning phase has not earned
its runtime cost in this half-second comparison; do not expand it on the
basis of these results. No default, opponent weights or trump settings were
changed. Any future architecture change should target a concrete failure
in the saved decision records rather than merely repeat this experiment.

Original data: `saves/concurrency/runtime-architecture-20261025/`.
`comparison.json` contains all paired sets and audit metrics; `endgames/`
contains the exact references and original timed analyses. Full game archives
and original journals are retained under each mode's match folders. Generated
data remains local and ignored by Git.

## Reproduction commands

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python app/benchmarks/compare_runtime_modes.py --output saves/concurrency/NEW-RUNTIME-COMPARISON
python app/benchmarks/compare_runtime_modes.py --output saves/concurrency/NEW-RUNTIME-COMPARISON --audit
```

All output folders are fresh; full game archives, journals, a source snapshot,
protocol, run order, exact sanity references and final paired comparisons are
kept together. Defaults are not changed while collecting data. No persistent
player weights are trained and no paid API or online game platform is used.
