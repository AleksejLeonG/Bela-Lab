# Exact endgame reference and search diagnostics

This is an offline correctness benchmark. It does not change dashboard advice,
the default continuation model, or persistent player/model weights.

## What is exact

`analysis/endgame_reference.py` evaluates every reachable continuation in a
small, known-card position using rational arithmetic. It supports at most
twelve cards still in hands and requires every other player's remaining card
to be publicly revealed. Ordinary hidden-card positions are rejected.

The three other seats, including the partner, each have an independent uniform
mixture over the same five profiles used in Monte Carlo advice. A profile stays
fixed for that seat throughout the continuation. Random tie breaks are
enumerated exactly from the actual policy implementation. The prior starts at
the analysis root, matching the current advisor's deliberate omission of
inference from earlier player behavior.

Future public actions condition the mixture exactly. Self chooses the action
with the best expected deal objective across that mixture, without being told
which profile was sampled. The solver does not maximize separately for each
hidden profile and average those clairvoyant choices. Future equal-valued self
actions use stable card-ID order; all exactly optimal root cards are reported.
Both point difference and contract success objectives are supported.

An optional fixed `self_policy` produces a different reference: it follows that
known self policy on later turns. That reference is used to test Monte Carlo
estimates with **identical continuation assumptions**. Adaptive tree rollouts
are compared by root-choice regret against optimal self continuation, not by
pretending their estimates or confidence intervals target optimal values.

The result includes exact fraction strings, expected recorded scores, success
probabilities under this model, objective variance, all optimal root cards,
visited nodes and runtime. Node, time or cancellation limits raise
`ReferenceLimit`; partial work is never labelled exact. Default limits are
100,000 nodes and 30 seconds. No exponential full-deal enumeration is attempted.

These are model-conditional values, not optimal play against arbitrary human
opponents or calibrated human-game probabilities. The reference reuses the
engine's existing legal-play/scoring rules, so it checks search and probability
math rather than independently reimplementing Croatian Bela rules.

## Independent checks

Tests compare rational values with exhaustive uniform-random continuations and
with explicitly enumerated fixed opponent lineups. A nontrivial three-card
fixture also expands joint profile scenarios, groups them by observable history,
and only then chooses the next self card. This independently checks the order
of expectation and maximization, without using the solver's posterior updater.

Further checks cover Bayesian profile persistence, Bela, exact objective
variance, probability normalization, preservation of the supplied state,
hidden-card rejection and resource-limit behavior. Public synthetic fixtures
are in `app/tests/fixtures/known_endgame_control.json` and
`known_endgame_planning.json`.

## Reproduction

Run from the project root with Python 3.11+:

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python app/benchmarks/endgame_accuracy.py --output saves/diagnostics/NEW-ENDGAME-RUN
python -m unittest discover -s app/tests
```

The benchmark defaults to:

- Case seed 2026102504; 16 nonforced known-card positions, half with two own
  cards and half with three, with varying positions within the trick.
- Four additional, separately labelled three-card challenges. They are selected
  using only exact references: root cards differ in value, and optimal future
  self control can improve a continuation over fixed Tactical. No tested
  Monte Carlo model's performance selects these cases. Candidate draws and
  rejections are saved; the challenge screening has a fixed candidate limit.
- Four self-continuation models: fixed Tactical, default exact-history tree v1,
  shared-context v2, and Bela-credit guarded v3.
- Trial budgets 128 and 512, with three seeds per position (7, 42, 119).

Outputs preserve full original advice/input records, rational references,
per-run root regret, case-selection metadata, engine source snapshots, Python
version, a benchmark copy, summaries and an audit. Existing output folders are
never overwritten. A Windows keep-awake request lasts only for the benchmark.

## Initial results

Artifacts: `saves/diagnostics/exact-endgame-20261025/`.

All **480 analyses** finished their requested trials. All **306 like-for-like
fixed-Tactical candidate estimates** were within six theoretical standard
errors of their exact reference. This is a conservative diagnostic check,
not a proof from finite Monte Carlo observations or an optimal-value check.

There were 20 positions: 16 baseline and four deliberately selected challenges.
Only nine had a meaningful root choice (at least one legal card was inferior).
The other eleven had all cards exactly tied. Three seeds on one position are
not three independent games.

| Continuation model | Optimal root choices at 128 | At 512 | Mean root regret, either budget | Worst root regret |
| --- | --- | --- | --- | --- |
| Fixed Tactical | 57/60 | 57/60 | 7.308 points | 146.16 points |
| Exact-history tree v1 | 57/60 | 57/60 | 0.0936 points | 1.8713 points |
| Shared-context v2 | 57/60 | 57/60 | 0.0936 points | 1.8713 points |
| Bela-credit guarded v3 | 57/60 | 57/60 | 0.0936 points | 1.8713 points |

On the nine meaningful positions each model selected an optimal card in 24/27
analyses per budget. Equal accuracy hides very different errors: Tactical
failed a deliberately selected challenge with large consequences, while the
search variants missed a different position by a small amount. The benchmark
does not distinguish the three search variants or establish general playing
strength. Root regret assumes optimal self continuation after that first card;
it is not the loss of an entire subsequently replanned game.

### Fixed Tactical trap

Challenge case 18 has hearts as trump and heart eight, ten and jack in hand.
Under optimal self continuation, eight and ten each have expected net value
10; jack has -136.16. Fixed-Tactical continuation instead makes jack appear
best. Increasing trials does not change that continuation assumption: fixed
Tactical chooses jack at both budgets and all three seeds, incurring 146.16
points of root regret under the optimal-continuation reference. All three
search variants avoid this trap. This is not a general rule against leading
the trump jack.

### Repeatable search miss

Baseline case 12 has hearts as trump and heart nine, heart queen and spade
eight in hand. Independent joint-scenario enumeration verifies these exact
expected net recorded points:

| Root card | Exact optimal-continuation value |
| --- | --- |
| Heart nine | -116 |
| Heart queen | -1151/30 (about -38.3667) |
| Spade eight | -54743/1500 (about -36.4953) |

Spade eight is best by 1.8713 points. All three search variants choose heart
queen at both trial budgets and all seeds. At 512 trials, seed 42, the default
tree estimates queen at -38.3320 but spade eight at -58.6680. The exact values
under fixed Tactical happen to equal the optimal values for these root cards;
under random self continuation, queen becomes best.

A traced rerun reproduced the original advice exactly. After spade eight,
124/372 nonforced future self selections differed from the Tactical choice
set. The trace repeatedly spends the valuable heart nine under an opponent's
winning heart jack when heart queen is also available. All cards in this
diagnostic are known, so this is not hidden-hand sampling uncertainty. The tree
had revisited and fully expanded most decision nodes; merely counting
value-guided selections does not ensure effective future play.

The concrete issue is that root estimates include the costs of the search's
exploratory future self behavior. They are valid estimates of their evolving
continuation target, not of best future self play. This explains why node reuse
and more trials alone have not reliably solved the planning mismatch. The next
search change can now be evaluated against a specific regression fixture rather
than justified from noisy full-match outcomes alone. This work does not tune
exploration weights, add a new continuation strategy, or change live advice.
