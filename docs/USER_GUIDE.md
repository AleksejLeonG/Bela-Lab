# Track a real game from one player's perspective

Run `START_BELA.cmd --text` or `python app/run.py --text`. To continue the included example:

```powershell
python app/run.py --text --load examples/player_match.json
```

The setup wizard asks for a name, your seat, dealer, team scores, caller, trump and your eight cards after the talon. Use `H` hearts, `S` spades, `D` diamonds, `C` clubs; ranks are `7 8 9 10 J Q K A`. Enter cards separated by spaces, for example `H_Q H_K S_9 S_10 S_A D_K C_8 C_9`. Seats follow play order; teams are 0+2 and 1+3. Scores are always team 0:team 1.

## Commands

| Command | Meaning |
| --- | --- |
| `status`, `hand`, `legal` | State and your legal cards |
| `presence 1 yes` | Publicly announced meld presence (`no` for none) |
| `meld 1 50` | Player 1's spoken strongest meld value |
| `high 1 K` | Spoken sequence high card |
| `reveal 1 S_7 S_8 S_9` | Actually revealed cards and owner |
| `melds none` | No ordinary melds; start play |
| `melds 0` | Team 0 wins the meld contest (`1` for team 1) |
| `move 1 H_7` | Record a specific player's card |
| `play S_A` | Record the current player's card |
| `move 0 H_Q bela` | Timely bela with the first trump K/Q |
| `belot 1 <eight cards>` | Claim and reveal belot; omit cards for your own hand |
| `history` | Active events with 1-based indexes |
| `replace 3 move 1 H_8` | Replace event 3 and revalidate its continuation |
| `insert 3 reveal 1 S_7 S_8 S_9` | Insert before event 3 |
| `delete 3`, `undo` | Remove an event or the last active event |
| `setup` | Correct current initial setup |
| `next` | Next deal after settlement, if the match continues |
| `save [path]`, `load path` | Manual save or load |
| `help`, `quit` | Help or save and exit |

Reveal all winning ordinary melds before `melds 0/1`. The engine can infer your own winning melds from your known hand. Losing teams need not reveal. Record spoken details faithfully without inventing additional cards.

Use explicit `move <player>` when correcting history; the current actor may differ from the actor at the edited event. Invalid corrections preserve the existing match. Prior revisions remain in the archive; the active event list is reconstructed by replay.

Every valid input is saved automatically, normally under `saves/<id>.player.json`; `--save <path>` selects a destination. The user archive records your starting hand and public information, not invented opposing hands. Full simulator saves are a different format. Quote paths containing spaces.

The engine tests whether a jointly legal hidden distribution exists across the full history. An impossible input is rejected. Computation-limit errors mean unconfirmed, not proven wrong; provide additional revealed cards or more specific declarations. Legal-card ordering is not a recommendation. English commands are preferred; legacy Croatian commands remain accepted.
