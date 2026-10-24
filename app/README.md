# Application file map

Launch the app with **START_BELA.cmd** in the folder above this one. `run.py`
selects the browser dashboard, player console or development simulator.

```text
app/
  run.py                    Application entry point used by the root launcher
  pyproject.toml            Python package and installed commands
  src/bela/
    domain/                 Cards, seats, game states and declaration records
    rules/                  Legal moves, meld comparison and scoring
    gameplay/
      tracking.py           Your hand, public events, corrections and revisions
      simulation.py         Full game simulation and player observations
      session.py            Full-simulator match sessions
    analysis/
      knowledge.py          Facts and explainable deductions
      validation.py         Check whether observations are jointly possible
      sampling.py           Generate hypothetical hidden hands fairly
      simulation_bridge.py  Resume a sample using the recorded game history
      advisor.py            Legal-action advisor; future move rankings
    storage/
      user_storage.py       Player saves containing supplied information
      persistence.py        Full-simulator saves and shared archive utilities
    interfaces/
      dashboard.py          Local browser server and dashboard API
      web/                  HTML, CSS, JavaScript and Croatian translations
      player_cli.py         Console for entering your real game
      simulator_cli.py      Development simulator and command dispatch
      localization.py       Shared Croatian message translations
    paths.py                Shared project, examples and save locations
    __main__.py             python -m bela entry point
    __init__.py             Application and ruleset versions
  tests/                    Engine, archive, dashboard and foundation checks
  benchmarks/               Reproducible validation and sampling measurements
```

For interface changes, start in `src/bela/interfaces/web/`. For how the game
works, start with `domain/`, `rules/` and `gameplay/`. For future Monte Carlo
development, start with `analysis/`.

Your actual games stay in `../saves/`; example archives are in `../examples/`.
Neither contains application source. The source reorganization does not change
saved-game formats.

See [development commands](../docs/DEVELOPMENT.md) for tests and launch options,
and the [documentation index](../docs/README.md) for detailed engine references.
