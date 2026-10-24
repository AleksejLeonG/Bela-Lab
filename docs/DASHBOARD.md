# Local Bela dashboard

The browser dashboard tests the existing Python engine on your computer. No external account, service or extra runtime package is required. Double-click **START_BELA.cmd**, or run `python app/run.py`. The default address is `http://127.0.0.1:8765`. Keep the launcher window open; Ctrl+C stops it. Use `--port 8766` if needed or `--no-browser` to suppress automatic opening.

## Language and appearance

English is the default. Select **Hrvatski** for Croatian. The **Night mode** button switches to a dark theme and becomes **Day mode**. Both preferences persist in browser local storage and are independent of matches. Switching preserves selected cards and entered form values. Match names, card identifiers and saved event data are not translated.

The interface, dialogs, event descriptions, rules reference and engine validation messages support Croatian. English source strings and the Croatian catalog live in `app/src/bela/interfaces/web`; `hr.json` is shared by the browser and server. Unknown technical errors retain their original detail.

## Try a match

1. Choose **Try demo**. This creates a separate copy; the source example is unchanged.
2. Select the legal heart king in your hand or the card picker, then **Record move**. Bela was already announced on the earlier queen in this example.
3. Open **Event history** to edit, insert before, or delete an event. Every correction revalidates subsequent events.
4. Open **My matches** and continue a saved match.

## Record your game

**New match** asks for a name, your seat, dealer, caller, trump, current team scores and exactly eight distinct cards after the talon. Seats 0–3 follow play order; teams are 0+2 and 1+3. Your partner appears opposite you.

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

Statistical advice, hidden-card sampling and trump-selection advice remain future work. The dashboard deliberately shows no invented probabilities.
