# Local Bela dashboard

The browser dashboard runs the existing Python engine on your computer. No external account, service or extra runtime package is required. Double-click **START_BELA.cmd**, or run `python app/run.py`. The default address is `http://127.0.0.1:8766`. Keep the launcher window open; Ctrl+C stops it. Use `--port` to choose another port or `--no-browser` to suppress automatic opening.

## Move advice

Open **Tools → Move advice** on your turn after confirming ordinary declarations, then
choose **Compare moves**. The recommended setup is already selected. Alternate
strategies, objectives and trial settings are in the collapsed **Experimental
settings** section. An active experiment is labelled; **Use recommended setup**
restores defaults. Results show expected settled points, contract/defensive
success and conservative 95% ranges. Analysis runs for up to eight seconds and
can be stopped. Recording or correcting an event cancels outdated work and clears
old estimates. Clicking a result only selects that card at the table.

These estimates depend on the selected policy and a uniform model of consistent
hidden deals. Unresolved choices are not proven equal. Future match victory and
optimal play are not estimated. See [MONTE_CARLO.md](MONTE_CARLO.md).

## Trump advice and project status

**Trump advice** normally uses the existing position-aware six-card assessment.
Select six cards before the talon and choose **Get trump advice**. Scores describe
hand strength, not success probabilities. Monte Carlo calling is opt-in inside
**Experimental settings** and is clearly labelled when active.

**Tools → Rules and help → Project status (English)** opens the single
[current status document](PROJECT_STATUS.md), also linked at the top of the README.

## Language and appearance

English is the default. Select **Hrvatski** for Croatian. The **Night mode** button switches to a dark theme and becomes **Day mode**. Both preferences persist in browser local storage and are independent of matches. Switching preserves selected cards and entered form values. Match names, card identifiers and saved event data are not translated.

The interface, dialogs, event descriptions, rules reference and engine validation messages support Croatian. English source strings and the Croatian catalog live in `app/src/bela/interfaces/web`; `hr.json` is shared by the browser and server. Unknown technical errors retain their original detail.

## Try a match

1. Choose **Tools → Explore demo**. This creates a separate copy; the source example is unchanged.
2. Select the legal heart king in your hand or the card picker, then **Record move**. Bela was already announced on the earlier queen in this example.
3. Open **Event history** to edit, insert before, or delete an event. Every correction revalidates subsequent events.
4. Open **My matches** and continue a saved match.

## Record your game

**New match** starts before trump is set:

1. Enter the match name, your seat, dealer, scores and **first six cards**. No
   caller or trump is required yet. Choose **Get trump advice →**.
2. Review the advice with those six cards. Once a player has actually called,
   choose **Trump has been called →**. Passing recommendations do not invent
   a later caller or suit.
3. Select the actual caller and trump, add the final two cards, and **Open match**.
   The original six stay selected; **Back to trump advice** lets you correct them.

The pre-deal draft is stored in this browser and restored on page refresh while
its source match is unchanged. The full replay-validated match is saved after
the call and eight-card hand are confirmed. **Next deal** follows the same
sequence with the score carried forward and the dealer rotated. Seats 0–3 follow
play order; teams are 0+2 and 1+3. Your partner appears opposite you.

Under **Melds**, record only public information: presence, strongest spoken value, sequence high card, actual revealed cards or belot. Reveal all winning ordinary melds before confirming the contest outcome. The engine can determine your own winning melds from your hand. Do not invent unknown opposing cards.

Under **Record a move**, choose the card actually played by the current actor. On your turn, you can click your hand. Legal highlighting means permitted by the rules; card order is not strategic advice. Check the bela box only for a timely announcement with the first trump K/Q.

Tricks and card points update automatically. Match totals change after settlement, including failure and bonuses. **Next deal** appears after the deal finishes if the match is ongoing; it carries the score forward and advances the dealer.

## What we know

Select **What we know** (◎) for public facts, proven deductions per player and possible owners of unplayed cards outside your hand. Each conclusion links to its source event or starting hand. Revealed cards and deduced owners have separate labels. Suit filters narrow the ownership list; **Refresh knowledge** retries unfinished checks. Corrections rebuild the view automatically. Possibility is not a probability estimate. See [KNOWLEDGE.md](KNOWLEDGE.md) for details.

## Persistence and corrections

Each accepted change saves to `saves/dashboard/<id>.player.json`. **Download archive** exports the active player session. **Import file** validates a player archive and creates a separate copy. Full simulator archives are a different format.

**Edit setup** revises the current deal's initial data. Structured event edits preserve revision history. An inconsistent change is rejected without changing the match. Earlier deals can be viewed but cannot be edited after starting a later one.

There is one active match per server. Browser tabs share that state; stale changes are rejected and refreshed. After restarting, choose a saved match in **My matches**. Validation may reach a computation limit; this is distinct from proving an impossible state, and preserves the prior state.

## Application boundary

```text
Browser: index.html + style.css + preferences.js + i18n.js + app.js
  → local JSON HTTP requests
dashboard.py
  → existing commands
tracking.py → rules and hidden-deal consistency
user_storage.py → archives and revision history
```

The buildless interface contains no copied game-state authority. Python validates every change. A later TypeScript/React interface can use the same API; FastAPI can replace the HTTP adapter if needed.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/state` | Permitted observation and saved matches |
| `GET /api/knowledge` | Revision-linked facts, deductions and ownership support with reasons |
| `POST /api/new` | New match with your own hand |
| `POST /api/demo` | Independent demo copy |
| `POST /api/command` | Add, replace, insert, delete, setup or next deal |
| `POST /api/load` | Open a managed save |
| `POST /api/import` | Validate and import a separate copy |
| `GET /api/export` | Export the active player archive |
| `GET /api/rules?lang=en` | English reference (`hr` for Croatian) |

POST requests include expected match identity and revision. Changes are serialized, persisted, then committed in memory. `Accept-Language: hr` requests translated errors; the default is English. The server binds only to `127.0.0.1` and is a local development tool.

Statistical move advice and six-card [Monte Carlo trump advice](MONTE_CARLO_CALLING.md)
are available. Open **Trump advice** before picking up the talon; the tool is
separate from the current match and does not record a call. Estimates depend
on the stated simulation model, and zero completed trials show an explicit
heuristic fallback without invented probabilities.

## Analysis board and saved feedback

The **Analysis board** replaces Game review. The live table and its entry controls
remain separate. Select a saved match inside the analysis workspace without
replacing the active live game, then choose a deal and a recorded move.

The table, your hand, remaining card counts, trick points and public-event list
show the position **before** that move. The actual recorded move is labelled
separately; final deal totals are explicitly final results. Jump between tricks
or individual moves using the timeline. Selecting an evaluated card highlights it
in the displayed hand; it never records a play or changes the archive.

For your own recorded decisions, **Analyse position** runs the recommended
128-trial / 8-second comparison. **Think longer** starts a fresh 512-trial /
15-second comparison; it does not append trials to the previous result.
The selected position is rebuilt from the current corrected history, excluding
future cards, declarations and edit commands. Earlier deals are included only
as already recorded knowledge. The engine receives the tracked player's hand
and permitted public information, never the other players' hidden hands.
Other seats can be replayed, but cannot be analysed without their private hands.

The evaluation sidebar shows point difference, contract/defensive success,
uncertainty and the played card. The saved-evaluation selector distinguishes
**Advice during game** from **Board analysis**. Each run retains its original
input and estimates in `saves/dashboard/analysis/`. Changing positions or leaving
the board cancels pending work; results cannot populate a different position.
Original advice from an incompatible corrected history is excluded.

Use **Add a review note** to flag a decision, select a legal alternative and
write a note. Click **Save review note** to persist it. Notes survive browser and
server restarts in `saves/dashboard/review/<match-id>.json`. They are separate
from game archives and do not train or change the strategy. Archive export alone
does not include notes or advice journals; an imported copy gets a new identity
and does not inherit the original's separate records. Standalone trump advice
is not currently linked to the card-play timeline.

Analysis requires an already recorded play; a deal with no recorded cards
directs you to the live-entry workflow. Cross-game player profiles and trump
calling grades are not included.

### Stage 2: game coach

The Analysis workspace now keeps the historical table, hand and move navigation
on the left, with **Game review**, **Move analysis**, **Moves**, and **Notes** in a
tabbed right panel. On desktop/laptop the board and controls fit the viewport;
long evaluations scroll inside the sidebar. Left/right arrow keys navigate
recorded moves when focus is outside a form. Tab changes preserve unsaved notes.

### Štilja and the match finish

The 90-point štilja bonus was already included by `settle_play` in all rollout
scores. Advice now also saves and shows each move's probability of **our štilja**
and **their štilja**, with sampling intervals. These are shared-trial frequencies
of taking all eight tricks. If a team has already won a trick, the other team's
štilja probability is structurally zero. Contract success remains a separate
quantity; a contract can be secured while avoiding a sweep is still important.

Recommended advice is now **Automatic**: ordinary positions use expected settled
point difference; if either team could exceed 1000 within the deal's public
upper scoring bound, it switches to `match_outcome`. Each rollout adds the deal's
recorded points to the starting match scores and applies the existing match
winner rule: the higher score wins once it is strictly above 1000; a tie keeps
the match alive. Thus passing a contract can still lose the match—for example,
950–980 plus 90–72 becomes 1040–1052.

The match objective maximises immediate win probability minus immediate loss
probability. Continuing is neutral; expected point difference breaks exact
objective ties. The continuation search uses the same match-focused terminal
reward. **Win match now**, **Lose match now**, and **Continue match** are exhaustive
outcomes at the end of this deal and sum to 100%. They are not predictions of
the eventual winner after unplayed future deals. Štilja, declarations, Bela,
failed contracts and final score ties all feed the existing settlement first.

Historical analysis uses the score and declarations known at that decision.
Game review requests a new match-focused evaluation near the finish when only
old point-focused advice exists. Original estimates remain saved separately.
Match-focused coaching compares the paired win/loss balance instead of grading
the move against a different point-maximising objective.

Trump advice is now always visible on your calling turn, with a suggested call
or pass and four ranked suit cards. These remain six-card, position-aware
hand-strength scores, not match-win probabilities.

**Your game review** summarises your recorded card-play decisions. Click
**Review game** to analyse the remaining choices sequentially. It uses the same
historical information boundary as position analysis, never the final deal or
subsequently played cards. Each completed run is saved immediately in the
existing advice journal. Forced moves require no search and are excluded from
the evaluated-choice denominator.

**Stop review** retains completed results. Start again to analyse the remaining
choices. Review settings offer Standard (128 trials, at most 8 seconds per
decision), Deeper (512 trials, at most 15 seconds), and optional reanalysis of
already evaluated choices. Navigating within the board keeps the queue running;
leaving Analysis or switching/reloading the reviewed match stops it. Closing or
reloading the page queues no further work; the current bounded worker can finish
and save its result. The browser must remain open for an entire queued review.

The sidebar compares **You played** with **Engine choice** and the estimated
gap in settled **team point difference**. A 10-point edge gap is not necessarily
10 card points lost. Gaps between successive decisions must not be added: they
are conditional estimates at overlapping positions, not independent losses.

- **Leading choice:** the played card matches the leader's estimated value
  within 0.05 point. This does not prove optimality.
- **Small estimated difference:** the estimated gap is below 5 points.
- **Uncertain alternative:** a gap of at least 5 points whose paired interval
  still includes zero, or whose paired interval cannot be verified.
- **Review opportunity:** at least 5 points and a strictly positive lower bound
  on the paired 95% interval. At least 15 points marks a major opportunity.

These are transparent presentation thresholds, not learned skill ratings.
Candidate means must come from the same complete paired trial set with the
point-difference objective. Contract-success runs and incomplete/zero-trial
estimates are not used for these grades. The summary uses the latest usable
point-based run per choice; the sidebar can inspect any saved run separately.
Replaying or editing history automatically excludes incompatible advice.

Key decisions link directly to the historical board. **What changes with the
alternative?** describes observable consequences (preserving a trump or stronger
card, committing points, changing the led suit, or partner currently leading).
These facts do not establish the search's causal reason for preferring a move.
**Patterns to explore** counts those situations among clear review opportunities
without claiming they are proven weaknesses.

No overall accuracy percentage, Elo rating or automatic strategy training is
produced. Intervals cover search sampling uncertainty under the selected player
model; they do not cover model errors. Conservative ranges can leave many moves
unresolved, which is preferable to grading noise as a mistake.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/review?match_id=<uuid>` | Replay and feedback for a saved match; omitted identity uses the active match |
| `POST /api/review/feedback` | Save versioned feedback for an exact position |
| `POST /api/review/analysis/start` | Start a bounded job using the selected historical position |
| `GET /api/review/analysis?id=<job-id>` | Poll a job; changed source archives mark results stale |
| `POST /api/review/analysis/cancel` | Cancel a historical analysis job |

POST requests carry the selected match's expected identity and revision.
Historical jobs use a separate bounded worker from live advice. Notes also carry
the expected note version; conflicting edits and stale match requests are rejected.

## Workspace layout

The main navigation is **Live game**, **Analysis** and **My matches**. Expand
**Tools** for move advice, trump advice, knowledge, editable event history, rules,
and the demo. On desktop, Tools opens automatically for its views; the phone menu closes after selection.
Language, theme and New match remain in the page header.

Secondary information is expandable: live recent events, the analysis move list,
and **Analysis details** (saved evaluation selection, budgets and full estimates).
The table and move comparison remain the primary content. On narrow screens,
the evaluation follows the hand, ahead of replay notes and the complete event list.

## Playing against bots

Use **Play against bots** on the live table, then **New match**. Choose a match
name and bot strategy. Mixed styles assign each of the other seats one of the
existing five policies once per match; individual policy choices are also
available. These are local heuristics, not measured skill ratings. No paid API
is used. You play seat 0 with a bot partner in seat 2, against seats 1 and 3.

Calling begins with six cards and the existing position-aware trump assessment
under **Show trump advice**. Choose a suit or pass; after three passes the dealer
must call. The last two cards are exposed only after a call. Declarations,
winning-team reveals and Bela are handled automatically. Public declaration
information remains available in the bot controls.

During play, click a legal card in your hand. Other players act automatically,
using only their own observation and public information. A completed trick stays
on the table briefly before clearing. **Pause bots** stops automatic turns;
leaving the live table also pauses advancement. **Next deal** rotates the dealer
and continues the score until a team wins the match under the agreed rules.

The playable table now includes your larger hand on the felt, with two separate
per-card measures: **Best in trials** (share of paired simulated deals where
that card achieves the best objective, splitting ties) and **Contract** (making
our contract or defeating theirs). The first is not a posterior probability of
optimal play and need not sort in the same order as expected points. Moves are
ranked by average settled team point difference; **Expected score** displays
our average recorded points against theirs. Sampling intervals and unresolved
comparisons remain visible. A zero contract estimate means no successful
sample, unless public information independently establishes the outcome.

Trump calling advances visibly one player at a time, including bots. The table
shows seats, dealer, calling position 1–4, passes and the final call. Each
accepted call is displayed briefly before the final two cards are exposed.
After the call, a **Declarations** screen shows mandatory presence statements
in seat order and the winning team's revealed melds, their value and high card.
Confirm this screen to begin play. Losers' unrevealed meld details remain
private. Bela still announces on the first eligible trump king/queen play.
The completed call and declaration pause both survive reload/restart.

The table header keeps trump, caller, calling position, declaration points,
provisional/recorded deal points and match totals visible. **Trick and deal
scores** gives each trick's winner and cumulative card/play points, including
earned last-trick/sweep bonuses, plus previous settled deal results. Until the
deal settles, ordinary declarations and Bela count only for a team that has
won a trick. A failed contract transfers the settled total to the opponents.

**Move suggestions** appears directly on the table and automatically compares
your legal cards on each human turn (128 shared trials, up to 8 seconds). It
highlights the leading estimated move in blue and ranks all legal alternatives
by settled team point difference. Each row shows contract success and its 95%
range: making your team's contract or defeating the opponents' contract in this
deal, not winning the current trick or the whole match. Close candidates remain
labelled unresolved when the search cannot separate them. Only your hand and
public information enter the advisor; actual bot profiles and private hands are
not supplied. Forced moves have no invented probability. You can play while the
search runs, stop it, or recalculate; old-position results are discarded from
the live display. Completed advice is journalled for the game review.

Each accepted action is saved. Browser refresh and dashboard restart restore
the active mode and checkpoint. **Manual input** retains the separate workflow
for recording an external game, with its own active match. Bot archives cannot
be edited through manual event commands.

Player-visible records are ordinary `.player.json` files and work with the same
Analysis board and game coach. Opponents' unrevealed cards, deal seed and private
strategy assignments never enter public responses, player exports or analysis
inputs. The full controller checkpoint is stored separately in
`saves/dashboard/bots/`; keep these files local while games are unfinished.
Analysis covers your decisions, not the bots' hidden hands.

The root **START_BELA.cmd** launcher uses port **8766** by default and restores
the active game. The dashboard must be running for the local link to work.

## Card appearance

**Hungarian cards** is the default on a new browser profile. Use the card-style
selector in the header to choose **Standard cards**. The browser remembers your
choice across refreshes. Hearts, leaves, bells and acorns map to the engine's
unchanged H, S, D and C card identities; ober maps to Q and unter to J. The same
preference applies to live and analysis tables, hands, suit labels and trump
selection. Switching appearance preserves pending entries and unsaved notes.

The default Hungarian deck uses 32 colorful illustrations in the traditional
Tell pattern, with Roman-numeral pips, mirrored court figures and seasonal aces.
See
[the artwork reference](../app/src/bela/interfaces/web/cards/ATTRIBUTION.md).


### Screen-fitting table and review

On desktop (over 1100px wide), Live game keeps the table, hand, running scores and advice together in the viewport. Detailed Monte Carlo comparisons and trick/deal history open in dialogs. On smaller screens the page stacks vertically. Hands fit without horizontal scrollbars; narrow screens overlap cards while keeping their size. Analysis keeps a bounded table, uses the remaining width for review tools and shows clickable moves for the current trick at the bottom of the sidebar.
