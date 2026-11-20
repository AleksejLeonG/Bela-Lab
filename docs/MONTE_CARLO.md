# Monte Carlo move advisor

Open **Move advice** on your turn, after completing declarations. Choose a
continuation policy, ranking objective, trial count and seed, then **Compare
moves**. Analysis runs in the background for up to eight seconds. You can stop
it, keep recording the game or click a suggested card to select it at the table.
Selection does not record a move: confirm only the card actually played.

This is a baseline under explicit simulated play, not an optimal-play solver.
It evaluates the current deal, not future match victory, trump selection or
individual opponents' behavior.

## Paired evaluation

`analysis/monte_carlo.py` connects the [sampler](SAMPLING.md), verified
[simulation bridge](SIMULATION_BRIDGE.md) and observation-only rollout policies.
Each trial draws one uniformly consistent initial deal, resumes the exact
public history, tries every legal root card and plays each branch to settlement.
No feasibility witnesses or hypothetical announcements are used.

The default [hidden five-strategy mix](STRATEGIES.md) also draws a latent strategy
for each of the other three players. Assignments are independent and equally
weighted, fixed for the hypothetical match and shared across all candidate cards.
Our future decisions now use `information_set_tree_v1`, a finite information-set
Monte Carlo search. Each node is keyed by our own hand and public play history,
never by another player's sampled cards or assigned profile. New nodes explore
legal moves uniformly; later visits use UCT selection and completed simulation
rewards. A narrow [losing-trump preference](SELF_PLAY_IMPROVEMENT.md) overrides
exploration when only losing trumps are legal and the opponent's trick is
certain. It preserves a stronger trump for later by discarding the cheapest,
weakest trump. Other choices still use the tree. There is no
fixed Tactical fallback for our future turns. Opponent profiles remain fixed
within each hypothetical match.

This is a bounded approximation of future replanning, not a recursive fresh
128-trial analysis at every simulated decision. Search values are committed only
after a whole paired trial finishes. The historical `tactical_v1` self rollout
remains selectable through `MonteCarloConfig.self_policy` and the batch CLI for
controlled comparisons. Single-policy experiments retain their explicit fixed
policy for every player.

**Experimental planning limitation:** six diagnostic positions from the four-pair
smoke test showed that only 3.3% of future non-forced selections reached UCT
selection using learned action values at 128 trials. At 2048 trials this rose to
10.9%; most future selections were still exploring untried actions uniformly.
Forced choices are excluded from these figures. These deliberately selected
positions are diagnostic cases, not a representative estimate of all games.
The root still evaluates every current candidate using Monte Carlo; the limitation
concerns future continuation. This replacement should not yet be treated as a
faithful model of repeated full future Monte Carlo decisions. A larger paired
strength evaluation was deferred pending a better allocation of future-search
work. Increasing the trial count alone did not resolve the observed sparsity.

Search statistics now distinguish decision nodes from forced nodes, report visit
histograms and count exploration versus value-informed selections. Original
128-trial estimates reproduced exactly in all six diagnostic positions after
adding these counters; instrumentation did not change the selected moves.

All candidates share the same cards, latent lineup and trial random seed. Subsequent random
generators are keyed by the absolute card position, so branch-specific tie breaks
cannot shift another branch's random stream. All candidates' outcomes are committed
together. An interrupted trial contributes nothing for any candidate. Different
trials use fresh randomness; duplicate worlds are valid.

Internal rollouts now compute legal cards once for each turn and reuse that
result for selection and application. A prepared turn is bound by identity to
its immutable simulator state; another state cannot reuse it. The public
`play_card` entry point still performs normal validation. Completed public facts
use a bounded 2048-entry immutable cache whose keys exclude private hands.
Prepared updates avoid a temporary state-field dictionary, and bela card pairs
are prebuilt. All changes preserve the public simulator's results and metadata.

The per-trial randomness cache reuses the exact first draw for each absolute
card position and tie-break choice count. It matches
`Random((trial_seed << 6) + ply).randrange(stop)` exactly, including rejection
sampling, rather than using a modulo approximation. It never shares draws
between independent trials. A policy requesting a second draw without a new
turn fails explicitly, so future changes cannot silently alter this contract.

| Ranking objective | Value maximized |
| --- | --- |
| `point_difference` (default) | Our settled recorded points minus opponents' recorded points |
| `contract_success` | Probability our call passes, or probability we defeat the opponents' call |

Both teams' expected recorded points and contract/defensive success are always
reported. Settlement includes strict contract thresholds, failure, eligible melds,
bela, last-trick points and sweep bonuses. Empirical mean determines the displayed
order; stable card order breaks exact sample ties without establishing superiority.
Previous total scores are preserved but do not change this deal-only objective.

## Continuation policies

`analysis/policies.py` accepts only a `PlayerObservation`, never a full simulation,
bridge, sample or tracked user's evidence. All policies play legally and announce
bela on the first valid pair card. A missed real earlier bela remains missed.

- `random_v1`: uniformly choose a current legal card.
- `simple_v1`: cash a plain ace on lead when possible; otherwise lead low from a
  long plain suit. Donate points while partner currently wins. Against opponents,
  prefer a cheap current winner; otherwise shed a cheap card. Break ties randomly.

Three additional policies provide cautious, card-counting and tactical play; see
[STRATEGIES.md](STRATEGIES.md) for their exact scope. Mixed advice averages their
outcomes under explicit equal weights. Single-policy comparisons remain available.
No policy sees another player's assigned strategy. Skill levels are intended,
not established by measured ratings.

## Conservative uncertainty

Reported intervals are 95% simultaneous, time-uniform Hoeffding bounds, adjusted
for every displayed success/objective interval and unordered candidate-pair gap.
This includes selecting the empirical leader and stopping on a time budget.

For `K` candidates the family size is `2K + K(K-1)/2`. At completed trial count
`n`, allocate error `.05 / (family * n * (n+1))` to each quantity. For observations
bounded by `[a,b]`, use radius:

```text
(b-a) * sqrt(log(2 * family * n * (n+1) / .05) / (2*n))
```

The two-sided Hoeffding inequality and union bound over all quantities and counts
give coverage because `sum 1/(n*(n+1)) = 1`. Fixed-policy experiments use independent
trials. With adaptive self search, bounded martingale differences instead bound
the average conditional rollout value over the evolving search, as recorded in
`interval_target`. These intervals do not bound the value of a final, fixed learned
policy or optimal play. Candidates within a trial remain paired. As usual,
pseudorandom sampling approximates the mathematical random-draw model.

The safe score bound is `B = 252 + awarded ordinary melds + 20`: a sweep is the
largest base deal, ordinary awards are fixed by declarations, and at most one bela
adds 20. Point differences lie in `[-B,B]`; paired differences in `[-2B,2B]`.
Success lies in `[0,1]`; paired success differences in `[-1,1]`.

Bounds can be wide. **Unresolved vs leader** means the simultaneous paired gap
does not establish that the empirical leader is better. It does not prove equal
quality. Intervals cover sampling uncertainty, not incorrect input, the uniform
model's behavioral limitations, weak rollout play or real-player differences.
More trials cannot remove those model limitations.

## Budgets and identity

Defaults: 128 trials, eight seconds, seed 42, `mixed_match_v1`, `point_difference`.
Core limits are 10000 trials and 60 seconds; dashboard limits are 1000 trials and
15 seconds, with the current UI choosing eight seconds. Sampling is capped at
100000 proposals. Preparation has a one-second cap inside the total budget.
Cancellation is checked between candidates and simulated cards; sampling slices
are about 0.1 seconds. A small in-progress operation can finish after a deadline.

Results distinguish `complete`, `time_limit`, `cancelled`, `sampling_limit`,
`preparation_limit` and `forced_move`. A forced move returns immediately without
an invented success probability. Empty/unfinished runs report no estimates.

Metadata records match/revision/deal identity, ruleset, method/model/policy versions,
objective, seed, requested/completed trials, sampling attempts, discarded trials,
previous score and elapsed time. No hypothetical hands or masks are returned.
Analysis never modifies the tracked game or its archives.

## Preserved diagnostics

The batch CLI now flushes and syncs `analyses.jsonl` before advancing a move,
including forced, interrupted and unsuccessful analyses. Every record contains
the original replayable player input, all candidate estimates and intervals,
pair comparisons, ranks, seed, configuration, method, trial counts, search
statistics and selected move. Match records also retain `decision_estimates`.
A journal failure stops play with a checkpoint rather than silently discarding
the analysis. Selected moves in the log are proposed choices; the game archive
is the record of actions actually applied.

Dashboard results are saved separately in the game library's `analysis/` folder;
practice CLI results are journaled under `saves/analysis/`, including no-trial
results before advice selection fails. The analysis core remains a pure API;
other callers must persist the returned result themselves. No sampled hands or
latent opponent strategy identities enter these logs.

The original 50-match comparison used `paired_monte_carlo_v2` with Tactical self
continuation and did not preserve the per-decision estimates. Those results
remain historical baseline data. Recomputed advice cannot recover the original
estimates and must not be labeled as an original observation. The new method is
`information_set_monte_carlo_v1`; its playing strength has not yet been measured.

`strategy_model` reports the available profiles, intended levels, prior weights,
self continuation and match-level assignment scope. It never reveals a sampled
seat-to-profile assignment or claims to identify any real player's strategy.

The dashboard allows one worker at a time and retains at most eight jobs. Changes
cancel active work. Server and browser suppress old-revision, switched-match and
other-deal results. Settings changes clear old estimates. Reverting a correction
does not make an old analysis current again.

## API

```python
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves

result = analyze_moves(
    match,
    MonteCarloConfig(samples=256, seconds=8, seed=42,
                     policy="mixed_match_v1", objective="point_difference"),
    expected_revision=match.revision,
    # Optional: cancelled=cancel_event.is_set
)
```

HTTP endpoints retain the existing local Host/Origin and revision checks:

- `POST /api/analysis/start`: expected match/revision plus `config` with all five fields.
- `GET /api/analysis?id=<job-id>`: job status and, when finished, its result.
- `POST /api/analysis/cancel`: current expected match/revision plus `job_id`.

Job states are `running`, `cancelling`, `finished`, `failed` or `stale`. Stale
responses contain no result. Busy/stale starts return 409, invalid requests or
unavailable turns 422, and unknown jobs 404.

## Verification

The [learn-then-evaluate mode](LEARN_THEN_EVALUATE.md) freezes learned future
values and uses independent evaluation trials for reported probabilities. It
is selectable as `self_policy="learn_then_evaluate_v2"`; `learning_samples`
optionally sets its learning cap. The HTTP configuration accepts the existing
five required fields plus optional `self_policy` and `learning_samples`.
Learning adds computation, is reported separately, and never enters the
evaluation denominator. Existing advice defaults remain unchanged.
Version 2 uses a Cautious/Card-counting/Tactical mixture for unseen or incomplete
self positions; the original random-fallback version remains available as v1.
Learned values and the five-profile opponent mixture are unchanged.

The offline [exact endgame reference](ENDGAME_REFERENCE.md) now tests known-card
positions against the same fixed-profile opponent mixture. It separates
like-for-like estimator checks from optimal-continuation root-choice regret.
The initial diagnostic found a reproducible future-exploration planning miss
even with all remaining cards known; current tree intervals do not claim to
cover optimal-continuation values. Live advice and its defaults are unchanged.

An experimental shared-context continuation search is available explicitly as
`self_policy="shared_information_set_tree_v2"`. It borrows a bounded prior from
other simulated public contexts while retaining exact-history nodes. This adds
generalization bias and remains separate from the default exact-history model.
See [experiment design and promotion criteria](SEARCH_EXPERIMENT.md).

Tests compare random-policy estimates with exact rational enumeration of a known
two-trick endgame. They also cover legal play and observation invariance, seeds,
paired denominators, objectives, cancellation, forced moves, worker limits,
stale results, read-only HTTP analysis and browser response ordering.

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests
node app/tests/test_web_advice.cjs
python app/benchmarks/monte_carlo.py --samples 128 --seconds 8
```

One mixed-strategy opening benchmark with eight legal moves completed 128 paired
trials in about 1.5 seconds on the development machine. This is a position-specific
measurement, not a universal speed guarantee or playing-strength claim.
Direct competent Monte Carlo is also available as an experimental self policy,
without a learning stage. The [three-way runtime comparison](RUNTIME_COMPARISON.md)
documents its assumptions and the 48-match half-second comparison. That study
did not justify replacing the current default.

Later improvements include stronger policies, tighter justified uncertainty
bounds, exact endgame evaluation and information-set tree search.
