# Bela Engine

Double-click **START_BELA.cmd** to open the dashboard. Keep its window open while using the app; press Ctrl+C there to stop it.

Choose **Try demo** to explore an example, or **New match** to enter your own hand. English is the default. The **English / Hrvatski** selector and **Night mode / Day mode** button are at the top. Both choices are remembered in your browser.

On your turn, open **Move advice** to compare legal cards with Monte Carlo
estimates and uncertainty ranges. These estimates depend on the selected
simulated-player strategy; see the [advisor guide](docs/MONTE_CARLO.md).

```text
Bela Engine/
  START_BELA.cmd       Main launcher
  README.md            Quick start
  app/                 Application code, interface and tests
  docs/                Rules, guides and plans
  examples/            Demo match archives
  saves/               Your saved matches
```

The launcher remains one level above the application code. Existing matches are preserved in `saves/dashboard`, including their original names and contents.

Start with the [code map](app/README.md) to find application files, or the
[documentation index](docs/README.md) to choose a guide.

- [Dashboard guide](docs/DASHBOARD.md)
- [Agreed rules](docs/RULES.md)
- [Project workflow](docs/WORKFLOW.md)
- [Development and test commands](docs/DEVELOPMENT.md)

```powershell
.\START_BELA.cmd --text
.\START_BELA.cmd --simulator --seed 42
.\START_BELA.cmd --port 8766
.\START_BELA.cmd --trump C_9 C_J C_K H_A S_Q D_A
```

Alternatively run `python app/run.py`. Python 3.11 or newer is required. The launcher checks the project's virtual environment, the bundled Codex runtime, then system Python. No extra runtime packages or external account are needed.

Six-card [trump advice](docs/TRUMP_CALLING.md) is available through `--trump`.
It ranks suits using explained heuristic scores, passes with weak hands, and
requires the dealer to call after three passes. It runs entirely locally.

[Local batch modes](docs/LOCAL_BATCH.md) are available through `--batch --mode fast`
or `--batch --mode monte-carlo`. Calling now accounts for position. Add
`--dry-run` to check settings without playing any games.
