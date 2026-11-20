# Experimental Monte Carlo trump advice

`analysis/trump_monte_carlo.py:analyze_trumps` ranks four calls and, unless the
dealer is forced, passing. The existing `position_control_v2` remains the
default and the explicit fallback when no complete estimate is available.
Everything runs locally with the Python standard library.

## Model and information

The input is a `CallingObservation`: exactly six distinct visible cards, our
seat, dealer and ordered public passes. It cannot contain actual talons, other
hands or actual player identities. Each paired trial uniformly allocates the
26 unseen cards to the other initial sixes and all four two-card talons.
Card input order cannot change fixed-seed estimates.

All four suits and pass share that trial's cards, unknown five-profile lineup,
one Cautious/Counting/Tactical style for our later moves, and per-ply tie-break
draws. Each profile remains fixed throughout the trial and across actions.
The objective is expected team recorded-point difference for the current deal.
Opening lead, caller, partnerships, declarations and settlement follow the
actual rules; position therefore affects the simulated outcomes directly.

After our simulated pass, later seats use the existing position-aware heuristic,
each seeing only their initial six cards. The dealer must call. Declarations
are simulated truthfully, exposing only the winning team's required reveals
to subsequent observation-only card policies. No nested Monte Carlo searches
are performed for future calls or moves.

Earlier passes are **uninformative about cards by default**. Optional
`condition_on_passes=True` rejects sampled worlds where a previous passer would
have called under `position_control_v2`. This is an explicit deterministic
calling-model assumption, not a deduction about a human's cards. Future callers
use that heuristic in either setting. Their behavior is not a calibrated human
calling model. Match-score strategy remains deferred.

## Estimates and limits

Commit only complete paired trials. Interrupted partial trials update no
action's denominator. `TrumpMonteCarloConfig` defaults to 128 trials, eight
seconds, seed 42, no past-pass conditioning and 100,000 sampling attempts.
API/CLI limits are 10,000 trials/60 seconds; dashboard limits are 1,000/15.
Time/attempt limits do not prove that an allocation is impossible.

Rank by expected point difference; report expected team scores, team success,
paired differences and conservative simultaneous time-uniform 95% intervals.
`not_separated_from_leader` identifies alternatives not clearly worse. Intervals
cover sampling uncertainty under this model, not optimal play or human-game
calibration. Before declarations are known, the safe score bound is deliberately
loose (base/sweep/Bela plus all possible quads and at most two runs per hand),
so the intervals may be very wide.

`success_probability` means our side makes its contract or defeats theirs.
After passing the caller can change across samples. Report
`our_team_calls_probability` and `calling_team_make_probability` separately;
the latter concerns whichever side calls and is conditional on non-belot deals.
The point objective need not agree with the largest success probability.

Belot ends the match without an invented deal-point award. Belot points are
zero for every action in that shared world, and therefore do not create a suit
preference. Terminal team wins count toward success; separate belot and
winning-belot probabilities are exposed. No zero-sample probability is shown:
all estimates/ranks remain null and `recommendation_source` identifies the
heuristic fallback. A cancelled result is never applied in a local match.

## Use and persistence

For this experimental mode, open **Trump advice**, expand **Experimental
settings**, and check **Use Monte Carlo trump advice**. Select six cards, your
seat and dealer, then **Compare calls and pass**. The normal default uses the
position-aware heuristic with **Get trump advice**. Earlier seats are assumed to have
passed to reach your turn. This is separate from the open eight-card match and
does not record a call. Editing inputs invalidates old results. English,
Croatian and night mode are supported.

`POST /api/trump` accepts `player`, `dealer`, `hand`, `passes`, `config`, and an
optional `method` (`position_control_v2` or `monte_carlo_call_v1`). Existing
clients that omit `method` retain the previous Monte Carlo API behavior; the
dashboard explicitly sends the recommended heuristic unless the experiment is enabled.
The server validates the actual ordered pass history. A single trump request
runs at a time without holding the game lock. The original input, configuration
and full result are saved under `saves/dashboard/trump-analysis/` before being
returned. Sampled hands and latent player identities are not journalled.

```powershell
.\START_BELA.cmd --trump C_9 C_J C_K H_A S_Q D_A --policy monte_carlo_call_v1 --samples 128 --seconds 5 --json
.\START_BELA.cmd --trump C_7 C_8 H_7 H_8 S_Q D_K --dealer 0 --player 0 --policy monte_carlo_call_v1
.\START_BELA.cmd --batch --mode fast --calling-policy monte_carlo_call_v1 --calling-samples 128 --calling-seconds 2 --dry-run
```

Add `--condition-on-passes` only to assume earlier callers followed our
heuristic. Without the new policy flag, existing defaults remain unchanged.
In local matches only the evaluated player uses Monte Carlo calling; the
other seats keep `position_control_v2`. Calling budgets are separate from
card-play budgets and work with either fast or Monte Carlo card play.
Deal seeds are independent of the calling-analysis seeds.

Local-match original pre-call results are flushed to `analyses.jsonl` before
applying the recommendation and retained in `calling_estimates` and the deal's
calling record. These journals can contain `bela-trump-analysis-record` as well
as `bela-analysis-record`; consumers must distinguish the two formats.

## Validation

Tests cover six-card privacy, real pass evaluation, all positions/forced calls,
shared samples/styles/randomness, conditioning, cancellation/partial rollback,
fallback, belot, HTTP/CLI/journals, one single-deal batch integration and stale
browser responses. A small known-card continuation is checked against an exact
rational profile-mixture reference; this validates rollout accounting rather
than global optimality of trump selection.

Four 128-trial examples completed in 0.51–0.66 seconds on the development machine:
strong clubs called clubs; a weak optional hand passed; the same forced dealer
called clubs; a marginal third-position hand passed where the heuristic calls.
Original results are in `saves/diagnostics/trump-monte-carlo-20261025/smoke.json`.
These are diagnostic examples, not evidence of improved match strength. No large
match comparison was included in that smoke check. The default caller has not changed.

## Initial matched comparison — 2026-10-25

The subsequent comparison completed **20 matched pairs / 40 full matches** in
196.3 seconds. Both variants used fast card play: Tactical for the evaluated
seat and the same fixed hidden five-profile lineup for the other three seats.
Only the evaluated player's calling differed. The other callers retained
`position_control_v2`. Seed 2026102511 and indices 0–19 were fixed before play;
the first 16 cover all initial player/dealer combinations. Each pair shared
the same card/dealer schedule and actual strategy assignments.

The experiment used one worker, alternating model order, 128 calling trials
and a two-second cap, with no inference from previous passes. No engine source
or settings changed during collection. Source snapshots, original pre-call
journals and full game archives were retained. Games with different lengths
were compared over their common prefix: **188 shared deals**. This prefix
selection is censored by match endings; it is not an uncensored deal sample.

| Metric | Existing heuristic | Monte Carlo |
| --- | ---: | ---: |
| Match wins | 11/20 | 8/20 |
| Net recorded points / shared deal | +6.73 | +3.35 |
| Evaluated-player calls / opportunities | 53/138 (38.4%) | 71/138 (51.4%) |
| Optional calls (excluding forced dealer) | 31/116 (26.7%) | 49/116 (42.2%) |
| Evaluated-player contracts made | 44/53 (83.0%) | 56/71 (78.9%) |
| Team contracts made, including partner calls | 76/91 (83.5%) | 82/101 (81.2%) |

Monte Carlo minus heuristic was **-3.38 net points per shared deal**. The
exploratory 95% matched-pair cluster-bootstrap interval was **[-14.45, +7.41]**
(12,000 resamples, seed 2026102512). It includes both loss and gain: this small
comparison does not establish superiority or inferiority. Match wins are
secondary, not an independent validation of the point metric.

### Position and action differences

All following calling/contract counts use the same shared deals.

| Calling position | Opportunities | Heuristic calls; made | MC calls; made | MC net point change, summed |
| --- | ---: | ---: | ---: | ---: |
| First | 48 | 11; 8 | 20; 13 | -878 |
| Second | 38 | 7; 7 | 21; 19 | +368 |
| Third | 30 | 13; 12 | 8; 7 | -112 |
| Forced dealer | 22 | 22; 17 | 22; 17 | -14 |

The callers agreed in 101/138 observed opportunities. Their identical
decisions produced exactly identical fast-play outcomes, as did deals where
another seat called before the evaluated player. The other 37 decisions were:

| Change | Decisions | Observed MC net point change, summed |
| --- | ---: | ---: |
| MC calls where heuristic passes | 26 | -50 |
| MC passes where heuristic calls | 8 | -572 |
| Both call, different suit | 3 | -14 |

The largest observed loss came from the eight extra MC passes, rather than
from its extra calls as a group. Those passes did better twice and worse six
times in the paired realized deals. This is a useful diagnostic lead, not
proof that passing is wrong in expectation or a justification for fitting a
new threshold to these eight outcomes. Position subgroups are descriptive,
small and not independent significance tests.

### Runtime, audit and decision

All **143 original MC calling analyses** across full matches completed all 128
trials: 18,304 paired trials total, **zero timeouts or fallbacks**. Mean analysis
time was **1.334 seconds**, maximum **1.863 seconds**. The heuristic's full fast
matches, including all card play, each took less than 0.06 seconds; its calling
time was not separately instrumented. Of the 143 MC records, 138 belonged to
the common deal prefixes used for calling and point comparisons.

All 40 game archives, trick histories, calling orders, six-card inputs,
configurations, original estimates and applied recommendations passed audit.
The first audit attempt compared sorted card tuples with sets; the auditor
was corrected to compare sorted tuples. The actual hands matched, no game
data changed and no games were rerun. The original runner and corrected
auditor are both preserved.

**Decision:** keep the heuristic as default and Monte Carlo experimental.
Before another large test or model change, inspect the eight additional
passes and their original forecasts to distinguish sampling noise from
continuation/calling-model assumptions. This comparison provides no human-game
calibration and does not justify a default replacement.

Artifacts: `saves/concurrency/calling-comparison-20261025/`, including
`comparison.json`, `disagreements.json`, every original journal and full archive,
source snapshot, protocol, runtime summary and audit repair note. The reusable
runner is `app/benchmarks/compare_callers.py`; fresh output paths are mandatory.

```powershell
python app/benchmarks/compare_callers.py --output saves/concurrency/NEW-CALLING-COMPARISON
python app/benchmarks/compare_callers.py --output saves/concurrency/calling-comparison-20261025 --audit
```
