# Bela Engine

## Desktop app

Open **Bela Lab** from the desktop or Start menu, or use `START_BELA.cmd`. The Windows app uses the Python engine with a native WebView2 window and a responsive HTML/CSS/JavaScript interface. Build/install instructions and saved-game locations: [Desktop app](docs/DESKTOP_APP.md). The development browser dashboard remains available through `python app/run.py`.

**[Current project status and recommended setup](docs/PROJECT_STATUS.md)** — the
single starting point for what is active, checked and still experimental.

Double-click **START_BELA.cmd** to open the desktop app. Close its window to quit. To work on the browser dashboard, run `python app/run.py`.

Choose **Try demo** to explore an example, or **New match** to enter your own hand. English is the default. The **English / Hrvatski** selector and **Night mode / Day mode** button are at the top. Both choices are remembered in the app.

On your turn, open **Move advice** to compare legal cards with Monte Carlo
estimates and uncertainty ranges. These estimates depend on the selected
simulated-player strategy; see the [advisor guide](docs/MONTE_CARLO.md).

The dashboard opens with the recommended configuration. Alternative strategies
are inside **Experimental settings**. Trump advice normally uses the existing
position-aware assessment; Monte Carlo calling is opt-in.

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
The dashboard's **Trump advice** tool adds experimental
[Monte Carlo calling](docs/MONTE_CARLO_CALLING.md): rank suits and passing with
expected points, success rates and uncertainty. The existing heuristic remains
the default caller and fallback. Both run entirely locally.

[Local batch modes](docs/LOCAL_BATCH.md) are available through `--batch --mode fast`
or `--batch --mode monte-carlo`. Calling now accounts for position. Add
`--dry-run` to check settings without playing any games.
