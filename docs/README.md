# Documentation index

Start with [Current project status](PROJECT_STATUS.md): one recommended setup, what has been checked, and what remains uncertain.

The guides are grouped here by what you want to do. English is the current
source; original Croatian references are in `translations/`.

## Use the app

- [DASHBOARD.md](DASHBOARD.md): launch, enter cards, record moves and manage saves.
- [USER_GUIDE.md](USER_GUIDE.md): use the player console.
- [RULES.md](RULES.md): the agreed Croatian Bela variant.
- [TRUMP_CALLING.md](TRUMP_CALLING.md): six-card trump/pass policy and local commands.
- [LOCAL_BATCH.md](LOCAL_BATCH.md): local fast and Monte Carlo batches, dry runs and reports.
- [ONLINE_PRACTICE.md](ONLINE_PRACTICE.md): one online bot deal, observed result and connector limitations.

## Understand and develop the project

- [Application file map](../app/README.md): where each part of the code lives.
- [WORKFLOW.md](WORKFLOW.md): development stages and next steps.
- [FRAMEWORK.md](FRAMEWORK.md): architecture and information boundaries.
- [DEVELOPMENT.md](DEVELOPMENT.md): commands, tests and module responsibilities.

## Check the analysis foundation

Read these in order when working toward Monte Carlo advice:

1. [VALIDATION.md](VALIDATION.md): jointly consistent hidden hands and resource limits.
2. [KNOWLEDGE.md](KNOWLEDGE.md): facts, deductions and the dashboard knowledge panel.
3. [SAMPLING.md](SAMPLING.md): probability model, fair sampling and exhaustive checks.
4. [SIMULATION_BRIDGE.md](SIMULATION_BRIDGE.md): resume a tracked revision without exposing hidden information.
5. [MONTE_CARLO.md](MONTE_CARLO.md): compare legal moves under explicit policies and inspect uncertainty.
6. [STRATEGIES.md](STRATEGIES.md): five hidden strategy profiles and their lifetime across simulated matches.
