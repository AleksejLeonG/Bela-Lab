# Online practice connection

One private, bot-only deal was completed using a guest profile.
The site displayed **144 points for our team and 18 for the opponents**.
No action was taken by us in the following deal; the site automatically began
it, and the browser tab was closed. No ten-match run was started.

## What was connected

- The six-card calling policy chose clubs, scoring 69 for the visible hand
  `C_9 C_J C_K H_A S_Q D_A`. We were the forced dealer.
- After pickup our eight cards were `C_9 C_J C_K H_K H_A S_10 S_Q D_A`.
- The site's declaration popup confirmed there were no ordinary declarations.
- Our first six plays used the existing local Monte Carlo engine: `H_K`, `D_A`,
  `C_J`, `C_9`, `H_A`, `S_Q`. Each analysis completed 128 paired trials.
- A capture-file write failed during trick six and interrupted the original
  observation loop. That trick's other three cards were not recorded reliably.
  They were not reconstructed or supplied as hard facts.
- The remaining plays were uniquely legal from the visible hand and current
  trick: `S_10`, then `C_K`. The engine's legal-move function checked them;
  no statistical estimate was produced from the incomplete history.

This is a **partially successful supervised integration test**, not a verified
unattended connector or a playing-strength benchmark. A strong starting hand
and one deal cannot establish the advisor's quality.

## Local components

The read-only table probe observes the desktop game page. It reads rendered card faces, immediate turn text and visible seat
positions. It does not inspect internal application stores, sockets or private
hands. Card collection animations briefly distort seat positions.

The capture coordinator provides observation buffering for an authorized
browser controller. It requires three stationary table observations and four
distinct seats/cards before accepting a complete public trick. Logging occurs
after observation; a disk failure leaves all captured frames in memory and
returns a warning. It never clicks cards. Capture limits or browser failures
require stopping and resynchronizing, rather than guessing.

`interfaces/practice_advice.py` reconstructs one deal from observed public
events, checks that the current visible hand and ordered trick agree with it,
and invokes Monte Carlo. Stale or incomplete snapshots are rejected. If no
trials finish, no fallback card is selected.

```powershell
.\START_BELA.cmd --practice-advice saves/online-practice/position.json --output saves/online-practice/advice.json
```

For an incomplete-history position, `--forced-visible` accepts only an
immediate snapshot with `player`, `hand`, `trump`, `leader` and `trick`. It
returns a card only when exactly one play is legal. It reports missing history
and no success probability. Otherwise it stops.

The practice was operated through the assistant's browser controller, with
local Python decisions. These components do **not** yet provide a standalone
"play online" launcher. No paid model API, cloud hosting, package installation
or platform purchase was used. Assistant interaction still uses the normal
Codex allowance.

## Evidence and remaining checks

Local test artifacts are in `saves/online-practice/` (ignored by Git): the
verified five-trick prefix, six analysis results, two visible-only forced
decisions, DOM captures, the score screenshot and a report explicitly marking
the trick-six gap. The report does not present the record as a complete replay.

Tests cover legal recommendations from valid snapshots, stale/partial-history
rejection, absence of fake advice with zero trials, forced-only recovery,
animated seat corruption and disk-write failures. The revised capture loop
passed those tests after the online deal; it has **not** been validated in
another live deal. Another single supervised deal with uninterrupted capture
is required before considering a longer run. Broader layout support and
standalone browser transport also remain unfinished.
