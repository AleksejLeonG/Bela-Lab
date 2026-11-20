# Development guide

Python 3.11+ is required. The core uses the standard library only. Run commands from the project root.

```powershell
python app/run.py
python app/run.py --no-browser --port 8766
python app/run.py --text
python app/run.py --text --load examples/player_match.json
python app/run.py --simulator --seed 42
python app/run.py --simulator --seed 42 --moves 5 --save saves/demo.json
python app/run.py --simulator --load saves/demo.json --moves 0
python app/run.py --simulator --load saves/demo.json
python app/run.py --batch --mode fast --matches 100 --dry-run
python app/run.py --batch --mode monte-carlo --matches 10 --dry-run
```

The root `START_BELA.cmd` accepts the same options and runs one level above `app`. Relative user paths resolve from the project root. The old `--tekst` option remains an alias for `--text`.

## Tests and installation

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests
```

Optional editable installation: `python -m pip install -e ./app`. Installed commands are `bela`, `bela-track`, `bela-dashboard` and `bela-batch`; `python -m bela dashboard` and `python -m bela track` are also supported. Installing does not create a hosted service.

See [local batch modes](LOCAL_BATCH.md) for fast and Monte Carlo runs. Their
match-level integration tests require `BELA_RUN_SIMULATIONS=1`; default batch
tests only check configuration and mocked report plumbing.

The simulator contains all four hands and uses a deterministic first-legal-card policy for demos. It is not strategic advice. `--seed` reproduces a deal, `--moves 0` preserves the current phase, `--save` writes an archive, and `--next-deal` requires `--load` and a completed ongoing match.

## Modules

| Module | Responsibility |
| --- | --- |
| `domain/` | Cards, seats, immutable game and meld data |
| `rules/` | Legal actions, trick winner, scoring and meld comparison |
| `gameplay/simulation.py` | Full-state development simulator |
| `gameplay/session.py` | Full-simulator match sessions |
| `gameplay/tracking.py` | One-player observations, events, corrections and consistency |
| `analysis/knowledge.py` | Explainable facts, deductions and bounded ownership support checks |
| `analysis/validation.py` | Bounded hidden-deal search, partial meld/capacity propagation and private rechecked witness hints |
| `analysis/sampling.py` | Uniform synthetic deals from permitted evidence, with exact capacity weights and declaration rejection |
| `analysis/simulation_bridge.py` | Resume synthetic deals from a tracked revision, preserving actual public records and checking replay agreement |
| `analysis/advisor.py` | Legal-action API retained for simulator compatibility |
| `analysis/policies.py`, `analysis/monte_carlo.py` | Observation-only policies, paired move evaluation and conservative uncertainty |
| `analysis/lineups.py` | Hidden five-strategy lineups and persistent simulated-match contexts |
| `analysis/endgame_reference.py` | Bounded exact known-card reference for offline search/probability checks |
| `interfaces/analysis_jobs.py` | Background analysis, cancellation and stale-result suppression |
| `storage/user_storage.py` | Versioned player archives and replay |
| `storage/persistence.py` | Full-simulator archives and shared file utilities |
| `interfaces/player_cli.py` | English console, with legacy Croatian command aliases |
| `interfaces/simulator_cli.py` | Simulator console and installed command dispatch |
| `interfaces/dashboard.py` | Loopback HTTP adapter and save library |
| `interfaces/localization.py` | Optional Croatian validation messages |
| `interfaces/web/` | Buildless responsive dashboard and shared Croatian catalog |
| `paths.py` | Paths independent of the caller's working directory |

The [exact endgame benchmark](ENDGAME_REFERENCE.md) provides reproducible
known-card action values, fixed-policy estimator checks and root-choice regret
for the existing continuation models. It is not connected to live dashboard
advice and rejects ordinary hidden-card positions.

The [learn-then-evaluate mode](LEARN_THEN_EVALUATE.md) is selectable in the
dashboard and batch CLI. Its learning and evaluation costs are reported
separately; the default remains the earlier exact-history search.

`examples/simulator_match.json` contains simulator hands. `examples/player_match.json` contains only the tracked player's hand and public events. Never feed simulator-only hidden hands to a player advisor. User saves belong in ignored `saves/`.

## Current capabilities and limits

Implemented: 32-card rules, required heading/overtrumping, trick scoring, ordinary meld detection and contest, bela/belot, settlement and match victory, complete simulator, player tracking, public announcements/reveals, event revisions, replay-validated persistence, text input and visual dashboard.

Player validation searches for at least one jointly consistent hidden allocation. Its witnesses are not probability samples. The separate [hidden-hand sampler](SAMPLING.md) draws uniformly from deals consistent with permitted evidence. The [Monte Carlo advisor](MONTE_CARLO.md) ranks legal moves under explicit policies and reports uncertainty; it does not guarantee optimal play or future match victory. Position-aware six-card trump selection, experimental [Monte Carlo calling](MONTE_CARLO_CALLING.md), and local fast/Monte Carlo match runners are implemented. Photographic/voice input, multiplayer hosting and penalty settlement are future work.

The optimized validator and reproducible performance examples are documented in [VALIDATION.md](VALIDATION.md). Run `python app/benchmarks/validation.py --runs 10` to measure cold validation and rechecked witness reuse.

## Profiling frozen advice inputs

`app/benchmarks/profile_analysis.py` accepts a local folder containing
`case-1-original.json` through `case-6-original.json`, each a preserved analysis
record with replayable `input` and `advice.config`. It compares the current tree
and historical Tactical self continuation on exactly the same positions:

```powershell
python app/benchmarks/profile_analysis.py --inputs saves/diagnostics/self-search-b2ea551b --samples 128 --repeats 3
```

Inputs in `saves/` are local artifacts and are not shipped with the repository.
Select cases with `--cases 1 3 5`, change repetitions with `--repeats`, or specify
a fresh output folder with `--output`. Every measurement uses a fresh sequential
Python process. Core advice timing excludes input restoration and journaling;
both are timed separately. Profiled execution identifies hot functions, while
unprofiled repeats supply latency measurements. Never infer a native-code speedup
from instrumented Python timings. Full candidate results and `.prof` files are
preserved, and profiled/unprofiled estimates must agree exactly.

The initial six-position study, before lookup optimization, completed 48 measurements. Tree-model median
latencies ranged from 0.30 to 1.34 seconds for 128 paired trials; journal writes
including input serialization had a median near 9 milliseconds. Exclusive
profile attribution put card/rule helpers at 26%, simulated player policies at
14%, state/observation helpers at 13%, enum utilities at 11% and random-number
generation at 7%. Hand sampling consumed roughly 1% inclusive of its helpers in
these particular positions. Cumulative function times overlap and must not be
added. These diagnostic cases are not a population or cross-machine benchmark.

Card-ID offsets and plain/trump strength lookups are now precomputed once at
module import. An interleaved, unprofiled A/B check used the exact previous
helpers in isolated subprocesses: 36 measurements, three per version for each
of the six positions. Summed case medians fell from 5.051 to 4.324 seconds,
reducing analysis time by 14.4% (1.17x throughput) on these cases. All 36 runs
completed 128 trials and exactly reproduced pre-optimization candidate estimates
and comparisons. Card IDs and rule behavior remain unchanged.

Four further optimizations were implemented and benchmarked separately in fresh,
interleaved processes on the same six frozen positions:

| Change | Incremental reduction in analysis time |
| --- | --- |
| Reuse exact-state legal-card results | 7.0% |
| Cache immutable completed public facts | 2.9% |
| Reduce temporary state-copy/bela objects | 8.9% |
| Cache exact paired tie-break draws | 13.1% |

Each percentage compares with the immediately preceding version; they must not
be added. Each step used 36 measurements and reproduced all original candidate
estimates and pair comparisons. Public validation, bela timing, transient
analysis metadata, hidden-world invariance and random-draw equivalence have
dedicated regression checks. See [rollout boundaries](MONTE_CARLO.md).

A separate combined A/B measurement compared the final version with the source
from before these four steps (already including precomputed lookups). Summed case
medians fell from 4.300 to 3.085 seconds: 28.3% less time, or 1.39x throughput.
Final case medians ranged from 0.20 to 0.82 seconds for 128 trials. Across the four
individual and one combined comparisons, all 180 runs exactly reproduced the
pre-optimization estimates. These are analysis timings, not full-match timings.

The policy selector also skips strategy scoring when exactly one card is legal.
It still consumes the original `randrange(1)` draw and checks bela, preserving
later random choices and announcements. A separate 36-run A/B check on the same
six positions reduced summed case medians from 4.152 to 3.472 seconds (16.4%).
All runs completed 128 trials with exactly unchanged candidate estimates and
comparisons. Results are saved locally under
`saves/profiles/forced-moves-a857ce0b/comparison.json`. This change leaves future
search-tree bookkeeping unchanged.

The search algorithm was not changed during profiling or these optimizations. Any future
optimization must preserve rule behavior and be timed without the profiler.
Faster execution remains separate from the experimentally observed sparse
future-search coverage described in [MONTE_CARLO.md](MONTE_CARLO.md).

English is the source language. Update `interfaces/web/hr.json` for Croatian interface/error translations and `docs/translations/RULES.hr.md` alongside rule changes. The server generates `/locale.js` from the same catalog; do not duplicate it in JavaScript. Preferences are browser-local and do not modify archives.
