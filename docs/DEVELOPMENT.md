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
```

The root `START_BELA.cmd` accepts the same options and runs one level above `app`. Relative user paths resolve from the project root. The old `--tekst` option remains an alias for `--text`.

## Tests and installation

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests
```

Optional editable installation: `python -m pip install -e ./app`. Installed commands are `bela`, `bela-track` and `bela-dashboard`; `python -m bela dashboard` and `python -m bela track` are also supported. Installing does not create a hosted service.

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
| `analysis/advisor.py` | Legal actions now; statistical move ranking later |
| `storage/user_storage.py` | Versioned player archives and replay |
| `storage/persistence.py` | Full-simulator archives and shared file utilities |
| `interfaces/player_cli.py` | English console, with legacy Croatian command aliases |
| `interfaces/simulator_cli.py` | Simulator console and installed command dispatch |
| `interfaces/dashboard.py` | Loopback HTTP adapter and save library |
| `interfaces/localization.py` | Optional Croatian validation messages |
| `interfaces/web/` | Buildless responsive dashboard and shared Croatian catalog |
| `paths.py` | Paths independent of the caller's working directory |

`examples/simulator_match.json` contains simulator hands. `examples/player_match.json` contains only the tracked player's hand and public events. Never feed simulator-only hidden hands to a player advisor. User saves belong in ignored `saves/`.

## Current capabilities and limits

Implemented: 32-card rules, required heading/overtrumping, trick scoring, ordinary meld detection and contest, bela/belot, settlement and match victory, complete simulator, player tracking, public announcements/reveals, event revisions, replay-validated persistence, text input and visual dashboard.

Player validation searches for at least one jointly consistent hidden allocation. Its witnesses are not probability samples. The separate [hidden-hand sampler](SAMPLING.md) draws uniformly from deals consistent with permitted evidence and reports partial results when budgets run out. No statistical move ranking or guaranteed optimal policy is implemented; the advisor currently exposes legal actions only. Trump selection, photographic/voice input, multiplayer hosting and penalty settlement are future work.

The optimized validator and reproducible performance examples are documented in [VALIDATION.md](VALIDATION.md). Run `python app/benchmarks/validation.py --runs 10` to measure cold validation and rechecked witness reuse.

English is the source language. Update `interfaces/web/hr.json` for Croatian interface/error translations and `docs/translations/RULES.hr.md` alongside rule changes. The server generates `/locale.js` from the same catalog; do not duplicate it in JavaScript. Preferences are browser-local and do not modify archives.
