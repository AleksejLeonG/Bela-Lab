# Shared future-search experiment

The current exact-history search rarely revisits early future decisions. The
experimental `shared_information_set_tree_v2` keeps the exact-history tree and
adds a bounded prior learned from other simulated public contexts. The existing
`information_set_tree_v1` remains the default and comparator during evaluation.

Contexts match the acting player's remaining hand, trump, caller's team,
position within the trick, led suit, current winning seat relative to the actor,
and legal actions. They deliberately omit completed history and scores.
Consequently they can join situations with different risks and different
conditional hidden-card distributions. This is approximate generalization,
not an exact state equivalence or proof of optimal play.

For every action, a context needs at least two committed observations from
**other exact nodes** before supplying a prior. Its mean contributes at most two
pseudo-visits to that action's UCT score. This prevents unlimited prior weight
as the context accumulates data. Exact evidence ultimately dominates. In the
absence of sufficient shared data the original search is used. No tactical
policy chooses future self moves. Pools reset for every advice request.

Both exact and pooled values update only after a complete paired trial. No
opponent hand, latent profile, or trial identity enters a context. Simulated
match results are not persistent training data for this feature.

## Evaluation plan

The six previously inspected positions are diagnostic examples, not held-out
strength evidence. Compare both versions at 128, 512 and 2048 trials. Preserve
full advice and input records. Verify old 128-trial results exactly against
their original records. Report exact and shared value-guided choices separately;
more pooled choices alone cannot establish better decisions.

Then run four fresh paired full matches, seed 2026102501, indices 0–3, against
the existing version, at 128 trials with a 60-second safety limit per decision.
Keep cards, calling, dealer schedule and hidden opponent profiles identical.
Compare only shared deals when matches end at different times. Retain every
decision estimate, full game archive and trick-point history.

Before interpreting the four-match results, the screening rules for proceeding
to 50 further held-out pairs (indices 4–53) are:

- All tests and match/replay audits pass; every nonforced analysis finishes its
  128 trials. Stop on worker, rule, persistence or incomplete-analysis errors.
- Across the six positions at 128 trials, the fraction of nonforced future
  choices using exact or shared values at least doubles. Aggregate analysis
  time must remain within 1.5 times the comparator. Report larger-budget move
  changes as sensitivity, without treating stability as correctness.
- In the four pairs, average net recorded points per shared deal must not fall
  by more than five, and the new version must not lose more than one match win
  relative to the comparator. These are pragmatic severe-regression screens,
  not statistical evidence of strength.

The larger run uses batches of at most four concurrent matches. Report paired
mean net-point changes and a match-cluster bootstrap interval as well as wins,
contract outcomes, runtime and search coverage. Do not tune against the held-out
run or call success probabilities calibrated from these results. Promotion to
the default requires evidence of benefit, not merely passing the small screen.

## Reproduction

With `app/src` on `PYTHONPATH`:

```powershell
python app/benchmarks/compare_search.py --output saves/diagnostics/shared-search-20261025 --diagnostics saves/diagnostics/self-search-b2ea551b
python app/benchmarks/compare_search.py --output saves/concurrency/shared-search-smoke-20261025 --matches 4
python app/benchmarks/compare_search.py --output saves/concurrency/shared-search-heldout-20261025 --start 4 --matches 50
```

Use fresh output directories. Historical diagnostic files under `saves/` are
local artifacts and are intentionally ignored by Git.

## Diagnostic results

All 36 analyses completed the requested trials; every old-model 128-trial
estimate and pair comparison reproduced its original saved result. The full
records and source snapshot are in `saves/diagnostics/shared-search-20261025`.

| Trials | Old exact value-guided choices | New exact or shared value-guided choices |
| --- | --- | --- |
| 128 | 3.33% | 32.47% |
| 512 | 6.52% | 61.81% |
| 2048 | 10.88% | 84.01% |

These fractions exclude forced moves. Shared priors are counted separately in
the raw reports and must not be interpreted as exact-state evidence. Aggregate
128-trial analysis time was 7.830 seconds old versus 7.842 seconds new. Individual
timings varied; this single pass is not a precise speed comparison.

The top card changed between 128 and 2048 trials in two old-model positions and
three new-model positions, including a low-gap/tied case. Sharing results did
not establish greater stability or playing strength. The diagnostic screen
passed, allowing the four fresh paired matches to proceed. The full engine
suite passed 258 tests with two opt-in tests skipped; four dashboard checks
also passed.

## Four-pair screening results

Seed 2026102501, indices 0–3: both versions won all four matches. Across 39
shared deals the new version gained 6.82 net recorded points per deal. The
match-cluster bootstrap interval was [-7.90, 33.24]; four pairs cannot establish
a strength improvement. Three pairs declined slightly and one improved by 434
total net points, so the positive mean was concentrated in one pair.

All eight full replays, 640 original decision records, 46,592 completed trials,
and trick-point histories passed audit. Mean analysis times under four-worker
load were 2.746 seconds old and 2.127 seconds new, which must not be compared
directly with sequential diagnostic timings. The screening criteria passed;
50 further pairs at indices 4–53 were authorized by the evaluation plan.
Results: `saves/concurrency/shared-search-smoke-20261025/validation-comparison.json`.

During the held-out run, all four active new-model workers at indices 16–19 hit
the wall-clock limit at almost the same time. Their interrupted positions each
completed 128 trials in 0.20–1.04 seconds when rechecked sequentially. This is
consistent with a temporary machine interruption; its cause is unconfirmed.
The four failed attempts are preserved under `interrupted/attempt-1`, together
with their estimates. Completed games were retained, and only those unfinished
games were retried with identical seeds and engine settings. Failed attempts
are excluded from the strength comparison. The runner now preserves the first
stop cause and supports explicit resume with an identical configuration.

A second interruption affected old-model indices 28–31. A requested 45-second
monitoring wait elapsed after about 337 seconds; all four interrupted positions
then completed sequentially in 0.21–1.07 seconds. Those attempts were archived
under `interrupted/attempt-2`. The Windows batch runner now requests temporary
system wakefulness for its lifetime, without preventing display sleep or
changing power-plan settings. The request is released on exit. The remaining
run finished without further interruptions. Eight interrupted attempts in total
are preserved and excluded from the comparison; no complete game was rerun.

## Held-out results and decision

All 50 held-out pairs (100 complete matches), seed 2026102501 and indices 4–53,
passed replay and advice audits. There were 456 shared deals, 7,424 original
decision records and 546,944 completed trials. Every applied nonforced decision
completed 128 trials; saved advice matches the applied card and bela flag.
Trick-by-trick point histories match the replayed games.

| Metric | Exact-history v1 | Shared-context v2 |
| --- | --- | --- |
| Match wins | 31/50 | 31/50 |
| Own contracts passed on shared deals | 173/215 | 175/215 |
| Nonforced future choices using exact/shared values | 7.14% | 36.43% |
| Mean advice time under concurrent load | 2.070 s | 2.009 s |

The paired change in net recorded points was **+2.00 per shared deal**. A
5,000-resample match-cluster bootstrap gave a 95% interval of **[-2.23, +6.50]**.
There were three loss-to-win flips and three win-to-loss flips. At deal level,
55 improved, 353 tied and 48 worsened. The small positive point estimate does
not establish a playing-strength improvement. Similar runtimes show no evident
large overhead here, but this was not a controlled timing benchmark.

**Decision: retain `information_set_tree_v1` as the default.** Keep
`shared_information_set_tree_v2` available explicitly for further investigation.
The experiment demonstrates increased evidence reuse, not improved stability,
optimal play or calibrated success probabilities. No persistent model weights
were trained. Do not tune on these held-out matches and reuse them as fresh
validation; any follow-up strength test needs new seeds.

Raw results and the full audit are in
`saves/concurrency/shared-search-heldout-20261025/validation-comparison.json`.
The final runner invocation's elapsed time covers only the resumed portion;
per-decision timings above use complete attempts and exclude interrupted ones.
The engine source snapshot is retained with the frozen-position diagnostics.

## Diagnostic review: steps 1 and 2 only

Reviewed all 456 shared deals, including all 48 worse and 55 improved deals.
The first changed self decision was identified from the saved play sequences.
For each of the 103 changed-outcome deals, diagnostic tracing reanalysed that
original advice request at its original 128 trials and seed. Every candidate
estimate and paired comparison reproduced exactly. A second focused pass also
reproduced all 103 requests while inspecting canonical Bela credit status.
The engine source hash was identical before and after review. No strategy,
shared-context key, weight or default was changed, and no new matches were run.

### Outcomes and first changed decisions

| Finding | Worse deals | Improved deals |
| --- | --- | --- |
| Deals | 48 | 55 |
| Total change in net recorded points | -2348 | +3260 |
| Deals with a changed contract outcome | 7 | 10 |
| Net-point change in those contract-flip deals | -1444 | +2080 |
| Median predicted gain for the first switch | 1.77 | 3.28 |
| First switch predicted to gain at most one point | 15 | 10 |
| First-switch comparison interval includes zero | 48 | 55 |

Seven contract flips account for 61.5% of lost net points. Contract changes
also explain 63.8% of gained points: threshold effects drive both sides, not
just losses. The conservative 128-trial intervals separate none of these first
switches from their alternatives. This does not prove that all choices are
equivalent or justify a new one-point switching threshold.

To distinguish a whole-deal result from a first-move error, both first cards
were also replayed using the actual hidden cards and actual opponent profiles,
with each of the five existing fixed self continuations. Each uses the same
deterministic per-ply tie-break stream. This is a hindsight sensitivity check,
not optimal play or the actual future Monte Carlo policy. In 16/48 worse deals
the first switch was neutral or better on average across those continuations;
19/48 were worse under all five. Twelve worse and twelve improved deals had
both positive and negative counterfactual changes depending on continuation.

Examples use the saved zero-based match/deal identifiers:

| Match/deal | First changed card | Predicted gain | Full-deal net change | Hindsight observation |
| --- | --- | --- | --- | --- |
| 11/0 | diamond queen to club ace | +0.64 | -228 | First switch worse under all five fixed continuations |
| 15/8 | club ten to club nine | +0.23 | -252 | Contract flipped; hindsight result depended on continuation |
| 15/3 | heart nine to diamond queen | +1.45 | -186 | First switch better under all five: cannot blame it from the deal result alone |
| 26/1 | diamond nine to diamond ten | +4.33 | +218 | First switch better under all five, by 38–50 net points |
| 35/6 | diamond jack to club seven | +3.00 | +300 | First cards tied under all five: later replanning matters |

### Public-state sharing

Tracing inspected 63,583 attempted shared-prior selections in the 103 original
analyses. The pooled evidence frequently combines different public facts:
points already won **within the deal**, tricks won by each team, played trumps,
proven suit voids, current-trick cards, Bela credit, and remaining shown cards.
The review does not concern the overall match score or introduce a match-win
objective.

The diagnostic subgroups the foreign evidence by one public feature at a time,
subtracting the current exact node just as the real prior does. A comparison
requires at least two matching observations for every legal card. A ranking
conflict means the sets of highest estimated means in the full and matching
evidence are disjoint. It is a comparison of prior means, not necessarily the
actual UCT-selected move, an optimal-action verdict, or a causal intervention.

| Matching feature | Conflicts/comparable choices in worse-deal analyses | In improved-deal analyses |
| --- | --- | --- |
| Already-won card points | 422/1833 (23.0%) | 793/2284 (34.7%) |
| Played trumps | 538/7895 (6.8%) | 983/10876 (9.0%) |
| Proven voids | 813/9037 (9.0%) | 1171/10606 (11.0%) |
| Canonical Bela credit | 1217/25736 (4.73%) | 765/28379 (2.70%) |

These repeated choices are correlated and the subgroups are small and
observational. They must not be treated as independent significance tests.
Score, trump and void conflicts occur in successful cases too, sometimes more
often. Thus the review confirms heterogeneous sharing but does **not** establish
it as the cause of the 48 losses or justify adding every public fact to the key.
Exact-score matching in particular offers little comparable evidence and risks
recreating the original sparse-tree problem.

The Bela check ignores announcement timing and card order, using only no Bela,
own-team Bela, or opponent-team Bela. Different credit states supplied evidence
in 11,081/30,650 shared selections in worse-deal analyses and 9739/32,933 in
improved-deal analyses. A concrete simulated future position in the analysis of
match 10/deal 4 had clubs as trump and club ten, diamond jack and spade ten in
hand, with no Bela announced. Its pool also included opponent-Bela histories.
The full foreign evidence ranked spade ten first; evidence with the same Bela
credit ranked diamond jack first. The matching evidence had 26, 47 and 21
observations for the three cards. Other public features still differ, so this
is an illustrative mismatch, not proof that diamond jack was optimal.

### Suggested step 3 — not implemented

The first focused candidate is a **Bela-credit compatibility guard**: permit
borrowing only between the same three public states (none, own team, opponent
team). This separates a known 20-point scoring difference using a small number
of contexts, while avoiding full-history or exact-score partitioning. Leave the
remaining context and prior weight unchanged for that experiment.

This recommendation is a testable hypothesis, not a demonstrated fix. Compare
its remaining evidence coverage and decisions on diagnostic positions, then use
fresh seeds for strength validation if it looks useful. Do not introduce broad
card penalties, tune a switch threshold from these outcomes, or treat this
already-inspected dataset as fresh validation. Keep the existing exact-history
default meanwhile. No part of this proposed adjustment was implemented.

Raw review: `saves/concurrency/shared-search-heldout-20261025/review-public-contexts/`.
It contains per-deal findings, original-advice reanalyses, public-context traces,
the separate canonical Bela check, summaries and engine-source invariance proof.

## Bela-credit guard test

The proposed guard is implemented separately as `bela_credit_shared_tree_v3`.
It uses the identical v2 context plus no Bela/own-team Bela/opponent-team Bela.
The prior weight, root objective, sampling, opponent mixture, exact tree and
default remain unchanged. `shared_information_set_tree_v2` remains selectable
as the direct comparator, and `information_set_tree_v1` remains the default.

Tests check the three credit groups, prevention of cross-group borrowing and
retained sharing across different announcing partners/timings for the same team.
The full suite ran 263 tests: 261 passed, two opt-in tests skipped. Four dashboard
checks also passed.

The initial diagnostic test compares both shared variants on the six frozen
positions at 128 and 512 trials (24 analyses). All requested trials completed.
The 12 unguarded estimates and comparisons reproduced the previous v2 results
exactly. At 128 trials, value-guided future choices fell from 32.47% to 28.99%;
at 512, from 61.81% to 55.97%. Thus the guard retains most evidence reuse while
excluding incompatible Bela credit. Top-card changes from 128 to 512 fell from
three cases to one, which is a diagnostic observation, not proof of correctness.
Sequential aggregate times were 5.09 versus 5.50 seconds at 128 and 23.95 versus
22.03 seconds at 512. These noisy single-pass timings do not establish a speed
change. Results and a source snapshot are saved under
`saves/diagnostics/bela-credit-guard-20261025`.

The follow-up is a small, fresh four-pair test: seed 2026102503, indices 0–3,
v2 versus v3, 128 trials, a 60-second safety limit, identical deals and assigned
opponents, and at most four workers. Retain all original advice, full replays
and trick-point histories, and stop on incomplete analyses or worker failures.
This is an initial guard test, not another 50-pair strength study. Do not change
the default or fit weights from its results.

### Four-pair guard results

All eight fresh full games passed replay, forecast and trick-score audit.
There were 37 shared deals, 592 original decision records and 45,440 completed
trials. Every applied nonforced move completed 128 trials, the guarded variant
reported its guard active throughout, and no workers timed out.

| Metric | Unguarded shared v2 | Bela-credit guarded v3 |
| --- | --- | --- |
| Match wins | 1/4 | 1/4 |
| Own contracts passed on shared deals | 14/18 | 14/18 |
| Value-guided future choices in the fresh matches | 32.32% | 30.29% |
| Mean analysis time under concurrent load | 1.042 s | 1.048 s |

The guard changed net recorded points by -1.62 per shared deal. The exploratory
four-match cluster-bootstrap 95% interval was [-6.00, +0.78], so this very small
sample does not establish benefit or harm. Two deals improved, 33 tied and two
worsened; there were no match-win flips. The per-pair total net-point changes
were +8, +6, 0 and -74, showing that the negative mean is concentrated in one pair.

**Decision:** the guard passes its functional tests and retains most sharing,
but has not demonstrated stronger play or a speed improvement. Keep it as a
separate experimental option and retain the exact-history v1 default. Do not
promote v3 from this small test, and do not use the already-inspected matches as
fresh validation after further tuning. No automatic persistent training occurs.

Audit and original forecasts:
`saves/concurrency/bela-credit-guard-four-20261025/validation-comparison.json`.
The comparison runner now accepts `--old-policy` and `--new-policy`, allowing
version-specific comparisons without changing historical defaults. Reproduction:

```powershell
python app/benchmarks/compare_search.py --output saves/concurrency/NEW-GUARD-TEST --matches 4 --seed 2026102503 --old-policy shared_information_set_tree_v2 --new-policy bela_credit_shared_tree_v3
python app/benchmarks/audit_search_matches.py saves/concurrency/NEW-GUARD-TEST
```
