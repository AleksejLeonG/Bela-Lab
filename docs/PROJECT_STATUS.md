# Bela Engine — current project status

Updated 10 November 2026. Start here; the other experiment reports are historical
reference, not a list of things you need to configure or repeat.

## Recommended setup

| Part | What we use |
| --- | --- |
| Card advice | Current Monte Carlo search, including preservation of valuable trumps in certain losing tricks |
| Ranking | Expected team point difference for the current deal |
| Simulated players | Unknown mixture of five strategies for the other three seats |
| Default budget | 128 paired trials, up to eight seconds |
| Trump advice | Position-aware six-card assessment (`position_control_v2`) |

The dashboard opens with this setup. Changing strategy settings marks the
configuration as experimental; **Use recommended setup** restores card-advice
defaults. Monte Carlo trump advice is an explicit opt-in inside Experimental
settings. Normal trump scores describe hand strength and are not probabilities.

## What works, and what has been checked

| Part | Implemented and checked | What that does not establish |
| --- | --- | --- |
| Rules and scoring | Legal play, mandatory heading, trumps, declarations, Bela/Belot, settlement and match endings | Every possible game has not been exhaustively tested |
| Game tracking and saves | Manual entry, history corrections, replay validation, saving and loading | Automatic reading of a real table is not part of the normal workflow |
| Hidden-hand sampler | Draws deals consistent with the recorded information | It does not learn individual opponents' behavior |
| Card advice | Legal candidates, paired simulations, uncertainty, cancellation and focused endgame checks | Optimal play or calibrated human-game win probabilities |
| Trump assessment | Six-card information boundary, calling position, passing and forced dealer calls | The hand-strength weights are not learned ratings |

**Tests check implementation behavior. Match comparisons check performance
under a particular simulation model. Neither alone proves strategic strength.**

## Experiments — available, not recommended defaults

- Direct competent Monte Carlo and learn-then-evaluate card advice: no clear
  full-match advantage established over the current search.
- Shared-search variants: retained in code for research; not dashboard defaults.
- Monte Carlo trump selection: working, but its initial matched comparison did
  not justify replacing the existing caller.

Original estimates and game archives are retained locally under `saves/`.
Keeping data does not train the model: **matches do not automatically update
strategies or weights**. No new simulation batch is currently required.

## Current priority

**Playable bot table:** Live game now separates **Play against bots** from
**Manual input**. Bot mode automatically deals, runs position-aware trump
calling, handles public declarations and Bela, and advances the three bot seats.
Click your cards to play; complete matches use the same scoring and 1000-point
target as the simulator. Checkpoints resume after reload/restart, while player
archives feed the analysis board without opponents' hidden hands. The five
existing strategies remain unrated; interactive play does not retrain them.

Use one clear application workflow: six-card trump advice, eight-card deal
setup, declarations, moves and advice, corrections, saving and reloading.
**New match** now follows that order: six cards first, advice, then the actual
call and final two cards. A six-card browser draft is not yet a full saved game.
**Analysis board** replaces Game review. It opens saved matches independently of
the live game, shows the table and hand before each recorded move, and combines
replay, public information, notes and ranked evaluations. On your recorded
decisions it can run a fresh 128-trial / 8-second analysis or a 512-trial /
15-second comparison. Original live advice and later board analyses remain
separately labelled and saved. Other players' decisions cannot be evaluated
without their hands. Feedback does not automatically change the strategy.

**Stage 2 game coach** adds played-versus-leading move comparisons, conservative
review-opportunity labels, a saved-game summary, key decisions and factual card
consequences. **Review game** evaluates your remaining recorded choices one at
a time; completed results are saved and can be resumed. Forced moves are
excluded. A review opportunity requires both a material estimated point-edge
gap and a positive paired confidence bound. Close or uncertain estimates are
not called mistakes. There is no overall accuracy rating, cross-game skill
profile or trump-calling grade yet. See [the dashboard guide](DASHBOARD.md#stage-2-game-coach).
Fix practical problems encountered there before reopening strategy research.
Advice currently targets deal points; score-aware end-of-match decisions,
individual player modeling and automatic online play remain future work.

The 26 October browser walkthrough completed one full 32-card deal in a short
match starting at 990–990, including declarations, both advice paths, a history
correction and mid-game/final save reload. Settlement was 1047–1195, team 1 won.
Croatian/night mode and the status link were checked. This uncovered and fixed
a Windows atomic-save access conflict with bounded retries; permanent errors
still preserve the previous archive. This was an interface check, not a new
strategy-strength experiment.

For normal use: [Dashboard guide](DASHBOARD.md). For development only:
[test commands and code notes](DEVELOPMENT.md). Existing experiment reports
are supporting evidence, not additional active development tracks.
