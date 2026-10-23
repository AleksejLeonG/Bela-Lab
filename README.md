# Bela Engine

Double-click **START_BELA.cmd** to open the dashboard. Keep its window open while using the app; press Ctrl+C there to stop it.

Choose **Try demo** to explore an example, or **New match** to enter your own hand. English is the default. The **English / Hrvatski** selector and **Night mode / Day mode** button are at the top. Both choices are remembered in your browser.

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

- [Dashboard guide](docs/DASHBOARD.md)
- [Agreed rules](docs/RULES.md)
- [Text interface](docs/USER_GUIDE.md)
- [Workflow](docs/WORKFLOW.md)
- [Architecture](docs/FRAMEWORK.md)
- [Development commands](docs/DEVELOPMENT.md)

```powershell
.\START_BELA.cmd --text
.\START_BELA.cmd --simulator --seed 42
.\START_BELA.cmd --port 8766
```

Alternatively run `python app/run.py`. Python 3.11 or newer is required. The launcher checks the project's virtual environment, the bundled Codex runtime, then system Python. No extra runtime packages or external account are needed.
