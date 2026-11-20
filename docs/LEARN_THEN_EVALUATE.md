# Learn, then evaluate

The current `learn_then_evaluate_v2` separates simulated learning from the estimates used to
rank the current cards. It is available in the dashboard under **Your future
play → Learn, then evaluate (experimental)** and through `self_policy` in the
Python/API configuration and batch CLI. The existing default remains available.
The earlier `learn_then_evaluate_v1` remains selectable through the API/CLI for
comparison. The versions differ only in the cold-state fallback.

Since 2026-10-25, both learning and frozen evaluation also apply the narrow
[certain-losing-trump preference](SELF_PLAY_IMPROVEMENT.md). It takes priority
over learned values and fallback choices only in its stated public conditions.
The historical results below predate this change. No opponent profile changed.

## How the mode works

1. Learn future self action values using the existing exact-history tree, with
   paired root candidates, sampled consistent hands and unknown fixed profiles
   for the other three players. Only complete paired trials update the tree.
2. Copy the learned values into an immutable policy. For sufficiently learned
   positions it chooses the highest learned mean, with random ties and no UCT
   exploration bonus. Every legal action must have at least one observation.
3. Evaluate every current card using fresh worlds and this same frozen policy.
   These outcomes alone enter card scores, success probabilities, paired
   comparisons and confidence intervals. Evaluation never changes the tree.

Unseen and incompletely learned positions in v2 use an equal mixture of
**Cautious, Card-counting and Tactical**. A separate named random stream selects
one fallback style for each simulated trial; all root candidates and subsequent
fallbacks in that trial use the same style. Learned choices take priority over
all three styles. Random and Basic are excluded from this self fallback, but
remain in the unchanged five-profile opponent mixture. These are the three most
developed existing heuristics, not independently established player ratings.
The legacy v1 fallback is uniform random legal play. Forced moves and Bela timing are preserved.
Learning values use only the acting player's hand and public observations.

Learning and evaluation have separate domain-seeded random streams. Evaluation
keeps the original configured seed stream, so its worlds can be paired with
the old model. A frozen policy may still make imperfect choices. Its intervals
target **fixed learned-policy value conditional on training**, not optimal play,
future unlimited replanning, training uncertainty or human-game calibration.

## Budget and reporting

`samples` still means requested **evaluation** trials. Learning adds the same
number by default; `learning_samples` can explicitly set a different learning
cap for this mode. Thus 128 evaluation trials ordinarily mean 128 learning plus
128 evaluation, not 128 total. The old model has no separate learning phase.

The existing total time limit still applies. Learning stops between complete
paired trials after its sample cap or half the remaining post-preparation time,
then leaves the remaining budget for evaluation. If time runs out before any
evaluation trial completes, no estimates or probabilities are invented.
Cancellation discards an unfinished paired trial in either phase.

Results record `requested_learning_samples`, `completed_learning_samples`,
`completed_samples` (evaluation), `total_completed_trials`,
`learning_stop_reason`, `stopped_phase`, and separate training/evaluation search
statistics. Evaluation statistics include learned choices and unseen/incomplete
fallback counts. Batch reports separate learning, evaluation and total work.
The dashboard displays learning and evaluation counts separately. All phases
and estimates remain reproducible from the saved original input/configuration
when sufficient time is available. Nothing trains persistent player weights.

```python
MonteCarloConfig(
    samples=512,
    learning_samples=512,
    seconds=8,
    self_policy="learn_then_evaluate_v2",
)
```

The dashboard allows up to 1000 learning and 1000 evaluation trials, with its
existing time limits. A manually smaller learning budget is not guaranteed to
cover the future positions needed for a reliable choice.

## Verification

Tests prove that learning rewards cannot enter evaluation probabilities, the
snapshot is deeply copied and immutable, evaluation cannot commit values,
random/profile streams are separated, only observed information is used, cold
states use the declared fallback, and interrupted paired work is excluded.
There are also checks for the time reservation, forced moves, invalid budgets,
dashboard selection and batch cost accounting.

The initial v1 [exact endgame regression set](ENDGAME_REFERENCE.md) compared the old and
new modes on the same 20 known-card positions, at 128/512 evaluation trials and
three seeds each (240 analyses). Eleven positions have all root cards tied;
only nine distinguish a worse choice. The set is a development/regression
diagnostic, not a claim about general hidden-card playing strength.

| Mode and budget | Total paired trials | Exactly optimal root choices |
| --- | --- | --- |
| Old, 128 | 128 | 57/60 |
| New, 128 learning + 128 evaluation | 256 | 57/60 |
| Old, 256 (equal total work) | 256 | 57/60 |
| Old, 512 | 512 | 57/60 |
| New, 512 learning + 512 evaluation | 1024 | 60/60 |
| Old, 1024 (equal total work) | 1024 | 57/60 |

The new mode fixes the repeatable spade-eight miss at 512+512 for all three
seeds, with no new misses on the other positions. At 128+128 the incomplete
fallback still leaves that miss: removing exploration from evaluation does not
make unlearned states well learned. Simply giving the old search 1024 trials
does not fix it. On the nine meaningful positions, accuracy improves from
24/27 to 27/27 at the higher new budget.

At equal evaluation counts the new mode does roughly twice the trial work;
the measured endgame means were 0.478 seconds old versus 0.895 seconds new at
512 evaluation trials. The old 1024-trial mean was 1.172 seconds in a separate
pass. These are noisy diagnostic timings, not a precise speed comparison.
The original old-mode estimates were retained for reproducibility checks.

Artifacts:

- `saves/diagnostics/learn-evaluate-20261025/`
- `saves/diagnostics/learn-evaluate-equal-work-20261025/`

The follow-up is four fresh paired matches, seed 2026102506, indices 0–3, with
equal per-decision work: old 256 versus new 128 learning + 128 evaluation.
Preserve all advice, actual plays, trick histories and separate phase counts.
This small integration check is not another 50-match strength study.

## Initial v1 matched-game results

All eight full games, 552 original decision records and their trick-by-trick
point histories passed replay audit. Every nonforced decision used exactly 256
total paired trials: old 256 evaluation, new 128 learning plus 128 evaluation.
All workers finished and there were no incomplete analyses.

| Metric | Old 256 | New 128+128 |
| --- | --- | --- |
| Match wins | 4/4 | 3/4 |
| Own contracts made on shared deals | 11/13 | 10/13 |
| Mean advice time under concurrent load | 2.470 s | 2.300 s |

Across 33 shared deals, new minus old net recorded points averaged -0.79 per
deal. The exploratory match-cluster bootstrap interval was [-16.05, +20.32].
Per-pair net changes were +224, -200, -42 and -8. Four pairs cannot establish
an overall strength gain or loss; the small runtime difference also is not a
controlled speed claim. Total trial counts differ across whole matches because
the versions sometimes finish after different numbers of deals.

The frozen policy used learned values for 10.53% of nonforced future choices;
the remainder used unseen/incomplete fallbacks. This is the main remaining
limitation in large hidden-card spaces. The change fixes the known higher-budget
endgame planning miss, but it does not guarantee useful learned values for
future positions it has not covered.

**Keep the new mode selectable and experimental, with the old default intact.**
The measured improvement is specific to the known-card regression set at the
higher budget. Do not describe these results as a general win-rate improvement.
All 285 Python tests ran: 283 passed, two opt-in simulation tests skipped. The
four dashboard checks passed, including mode selection and Croatian labels.
The new mode's dedicated tests cover phase separation, independent streams,
frozen values, cold fallback, cancellation, time reservation and the regression.

Fresh-game audit:
`saves/concurrency/learn-evaluate-four-20261025/validation-comparison.json`.
The two endgame passes contain 360 saved analyses in total; 120 old-model
forecasts exactly reproduced the original benchmark, and all 120 new-mode
analyses passed checks that evaluation did not commit learning values and that
learning trials did not enter the reported sample denominator.

## Competent fallback v2

This change leaves training, frozen learned values, time allocation, hand
sampling, root objective, opponent profiles and tie-break streams unchanged.
It replaces only v1's unseen/incomplete evaluation fallback. Choosing a fallback
style uses a domain-separated seed, so it cannot shift hand samples or opponent
profiles. It is assigned once outside the root-candidate loop. Learning still
explores; the competent fallback applies only during frozen evaluation.

Tests verify the allowed three profiles, learned-value priority, public-information
boundaries, single-draw tie breaks, fixed styles across candidate cards, and
identical learning snapshots and sampling streams between v1 and v2. The
spade-eight regression is checked at 128+128 for seeds 7, 42 and 119.

The same exact 20-position set (including nine meaningful choices) produced:

| Evaluation + learning budget | v1 random fallback | v2 competent fallback |
| --- | --- | --- |
| 128 + 128 | 57/60 optimal root choices | 60/60 |
| 512 + 512 | 60/60 | 60/60 |

The lower-budget miss is now fixed for all three seeds, with no new misses in
this development/regression set. These are 20 positions repeated across three
seeds, not 60 independent games. This is not proof of general playing strength.

All 240 analyses completed and passed audit. The 120 v1 forecasts reproduced
the earlier saved values and pair comparisons exactly. All 120 paired training
statistic sets and opponent weights were identical, learned values stayed frozen,
and the reported denominator remained evaluation trials only. The named profile
usage counters account for every new-mode cold-state selection.

At 128+128, the sequential mean times were 0.406 seconds v1 and 0.420 seconds v2;
at 512+512 they were 1.716 and 1.649 seconds. The small changes in opposite
directions do not establish a speed difference. The fallback uses the existing
cheap heuristics rather than nested Monte Carlo search.

Artifacts: `saves/diagnostics/competent-fallback-20261025/`.
The fresh check uses four paired matches, seed 2026102507, indices 0–3, comparing
v1 and v2 at identical 128 learning plus 128 evaluation trials per decision.
All inputs, forecasts, actual plays and trick scores are retained for replay.

### Fresh v2 comparison

The four fresh pairs completed without timeouts or incomplete analyses. All
eight full replays, 560 original decision records, actual selected cards and
trick-point histories passed audit. Both versions used 128 learning plus 128
evaluation trials per nonforced decision. All three new fallback styles were
exercised, and their usage totals account for every cold-state selection.

| Metric | v1 random fallback | v2 competent fallback |
| --- | --- | --- |
| Match wins | 1/4 | 1/4 |
| Own contracts made on shared deals | 14/16 | 12/16 |
| Mean analysis time under concurrent load | 2.602 s | 2.696 s |

Across 34 shared deals, new minus old net recorded points averaged -3.18 per
deal, with an exploratory four-match cluster-bootstrap interval of
[-13.00, +6.92]. Eight deals improved, 19 tied and seven worsened. The small
sample does not establish a general strength gain or loss. Runtime was slightly
higher in these games; the measurements are not a controlled speed benchmark.

The dashboard's learned-mode option now selects v2. Legacy v1 is retained for
reproducible comparison, and the earlier exact-history global default remains
unchanged. The demonstrated gain is the lower-budget exact endgame regression;
do not describe this integration sample as a win-rate improvement. No weights
were fitted to these four pairs and no persistent player model was trained.

Final checks: 292 Python tests ran, with 290 passed and two opt-in tests skipped;
four dashboard checks passed. Fresh-game artifacts and audits are in
`saves/concurrency/competent-fallback-four-20261025/`.

```powershell
python app/benchmarks/endgame_accuracy.py --output saves/diagnostics/NEW-FALLBACK-TEST --self-models learn_then_evaluate_v1 learn_then_evaluate_v2
python app/benchmarks/compare_search.py --output saves/concurrency/NEW-FALLBACK-MATCHES --matches 4 --seed 2026102507 --old-policy learn_then_evaluate_v1 --new-policy learn_then_evaluate_v2
python app/benchmarks/audit_search_matches.py saves/concurrency/NEW-FALLBACK-MATCHES
```
