# Local match batches

Both modes are implemented as local Python programs using the existing rules,
calling policy, declarations and scoring. They require no browser, account,
network connection, paid API or ongoing assistant interaction. They produce
test results; neither mode automatically trains or updates model weights.

Initial implementation was checked without running matches. Subsequent
authorized checks completed 51 fast matches and seven Monte Carlo matches,
including four concurrent Monte Carlo matches. Saved histories, scores and
per-trick reports were replay-validated. These are integration checks, not
evidence of calibrated playing strength. Match-level automated batch tests
remain opt-in.

A five-process concurrency probe was stopped when one decision completed only
117 of 128 trials within eight seconds. A four-process retry completed all
four matches in 92.3 seconds; every analysed decision completed 128 trials.
This is a local observation, not a guaranteed worker limit on other machines.
Concurrency probes and detailed results are local files under ignored `saves/`;
the public batch command still runs matches sequentially.

## Modes

| Mode | Evaluated player | Other three players | Purpose |
| --- | --- | --- | --- |
| `fast` | Fixed `tactical_v1` card policy | Independent uniform selection from the five profiles | Check calling behavior, whole-match rules and a baseline cheaply |
| `monte-carlo` | Current Monte Carlo advisor on every decision | Same fixed-profile model | Evaluate the actual advisor over complete matches |

Each other player's profile is selected once per match and retained across
deals. The evaluated player's seat rotates through all four positions across
match indices; the initial dealer rotates across groups of four. Absolute
seat is not a strength advantage deliberately assigned to the evaluated team.

All four seats use the configured calling policy, currently
`position_control_v2`. Card-play profiles do not have separate calling
policies yet. Calls use only the six initially dealt cards. The final two are
not supplied to calling, despite being known to the simulation controller.

All ordinary declarations are truthful: presence is public and winning-team
melds are shown. Players declare eligible bela; an eight-card belot is claimed.
Normal matches finish under the agreed **strictly above 1000** rule, including
ties requiring another deal. Belot is an immediate match victory.

Monte Carlo receives only the evaluated player's initial hand, public
declarations and observed plays. It never receives other players' actual hands
or assigned strategy identities. Each candidate still shares sampled hidden
worlds and hypothetical lineups, using the existing paired advisor. Actual
opponent profiles and hypothetical analysis lineups use separate seed streams.
Hypothetical lineup identities remain stable across deals in a match.

The advisor still optimizes current-deal settled point difference, not full
match-win probability. Match-score tactics and inference from bidding remain
deferred. The new third-position calling preference does not yet teach the
partner to lead an ace deliberately to capture a nine.

## Commands for when runs are authorized

Use the existing root launcher. These commands actually play matches:

```powershell
.\START_BELA.cmd --batch --mode fast --matches 100 --seed 42
.\START_BELA.cmd --batch --mode monte-carlo --matches 10 --seed 42 --samples 128 --seconds 8
```

`--seconds` is a Monte Carlo budget **per decision**, not per match or batch.
`--samples` is the maximum paired-trial count per decision. Completed partial
analysis can be used at the deadline. A forced card needs no trials. If no
trial finishes for a non-forced move, the match is marked incomplete and the
batch stops; the runner does not silently replace advice with an arbitrary
card. Fast mode does not invoke Monte Carlo; its samples/seconds settings are
unused.

Validate configuration without generating hands, playing or creating files:

```powershell
.\START_BELA.cmd --batch --mode fast --matches 100 --dry-run
.\START_BELA.cmd --batch --mode monte-carlo --matches 10 --dry-run
```

The first implementation runs matches sequentially and keeps aggregate
statistics in constant space. Future parallel processing should be driven by
measured runtime rather than assumed to be necessary.

## Results and stopping

A new folder is created under `saves/batches/` for every actual run:

- `config.json`: modes, policies, rules version, seed and budgets.
- `matches.jsonl`: a flushed record per match, with scores, call rankings,
  contract results, fixed strategy profiles and analysis totals.
  Each completed deal includes `tricks`: ordered cards and players, winner,
  trick card points, cumulative card points, trick counts, last-trick/sweep
  bonuses and cumulative play points after each trick. Declarations and failed
  contracts are applied separately in the deal's final `recorded` and
  `score_after` fields. `match_score_before_settlement` stays at the previous
  deal's score throughout play. Belot has an empty trick history.
- `summary.json`: completed/incomplete counts, raw win rate, calling and
  contract outcomes by calling position, trials and timing totals.
- `games/`: full synthetic simulator archives when `--save-games` is supplied.

Existing result folders are never overwritten. These files are local and
ignored by Git. Optional full archives contain all four synthetic hands for
replay; those hands are not passed to player decision policies.

Press Ctrl+C once for a graceful stop, including a checkpoint of an
interrupted match when game saving is enabled. A second interrupt stops
immediately; already flushed match rows remain available. Incomplete matches
are excluded from win rates. Failures are recorded and stop the batch.

`--max-deals` is a safety limit, default 100. Reaching it does not invent a
winner. `--start-index N` restarts a chosen match index under the same seed
schedule; it does not resume from a saved mid-match checkpoint.

## Comparisons and reproducibility

Use the same seed and match indices to compare modes or calling policies.
Card shuffles and actual profile assignments use separate named seed streams,
so changing policy randomness does not change the deal schedule. V1 calling
remains selectable with `--calling-policy six_card_control_v1` for a baseline.

Fixed seeds reproduce cards and profile assignments with the same code.
Wall-clock Monte Carlo limits can change completed trial counts and choices
between runs. Save game archives to retain the exact moves actually played.
Summary win rates are raw simulated outcomes, not calibrated human win
probabilities or proof that a change is stronger.

## Verification without running matches

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests -p test_batch.py
```

The default batch tests use mocked match results or cancel before dealing.
The two match-level tests are skipped unless explicitly enabled with
`BELA_RUN_SIMULATIONS=1`. Enabling them runs complete fast and Monte Carlo
matches, so do not enable that flag while simulation runs are on hold.
