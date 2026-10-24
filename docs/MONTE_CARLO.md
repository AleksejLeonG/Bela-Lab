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
Our future continuation uses the tactical policy; it cannot see the other profiles.

All candidates share the same cards, latent lineup and trial random seed. Subsequent random
generators are keyed by the absolute card position, so branch-specific tie breaks
cannot shift another branch's random stream. All candidates' outcomes are committed
together. An interrupted trial contributes nothing for any candidate. Different
trials use fresh randomness; duplicate worlds are valid.

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
give coverage because `sum 1/(n*(n+1)) = 1`. Independence is required across trials
under the model, not between candidates within a trial. As usual, pseudorandom
sampling approximates the mathematical random-draw model.

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
Later improvements include stronger policies, tighter justified uncertainty
bounds, exact endgame evaluation and information-set tree search.
