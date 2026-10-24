# Trump calling from six cards

The current calling policy is `position_control_v2`; the original
`six_card_control_v1` remains available as a frozen comparison. Both run with the
Python standard library: no model API, account, hosting or paid service.
One supervised [online practice deal](ONLINE_PRACTICE.md) has since been
completed. The standalone online connector and ten-match run remain unfinished.

## Calling rules and information

`gameplay/calling.py` models one calling round. The seat to the dealer's right
starts, then seats advance in the same direction as play. The first three
players may pass or select one of four suits. After three passes the dealer
must call. A call ends the round; further calls and passes are rejected.

`CallingObservation` contains only the acting player's six distinct visible
cards and the public calling state. Supplying eight cards is rejected. The two
cards picked up after calling, other hands and private simulator state cannot
be supplied to the policy. Earlier passes determine whose turn it is; they
are not treated as proof of missing cards or used to infer player strength.

## Baseline decision

`analysis/trump.py` scores every suit and returns all four rankings with their
individual contributions. These are **heuristic scores**, not expected game
points, success percentages, or a claim of optimal play.

| Visible feature | Contribution |
| --- | ---: |
| Each trump | +6 |
| Trump jack | +18 |
| Trump nine | +12 |
| Trump ace | +6 |
| Trump ten | +3 |
| Each trump beyond two | +5 |
| Missing jack with at least one trump | -8 |
| Missing nine with at least one trump | -4 |
| No visible trumps | -40 |
| Each ace outside trump | +8 |
| Each outside ten accompanied by its ace | +3 |
| Trump king and queen both visible | +6 |
| Strongest ordinary meld visible in the six cards | Points divided by ten, capped at +20 |

The jack and nine provide trump control; length provides staying power; side
aces offer possible tricks outside trump. Bela and ordinary meld bonuses are
discounted support: they are not guaranteed awarded points. Detection uses
the existing meld rules and does not invent a meld from unseen talon cards.

The original v1 policy uses the highest score, at least two visible trumps,
and a threshold of 45 for every optional caller. The forced dealer selects
the highest-ranked suit. Exact ties use the fixed order C, D, H, S.

## Calling position in v2

Position means order relative to the dealer, not absolute seat number.

| Position | First lead belongs to | Policy adjustment |
| --- | --- | --- |
| First | Caller | Threshold 45; base scoring |
| Second | Opponent | Threshold 49, requiring more support without the lead |
| Third | Partner | Threshold 45; +8 with the candidate trump jack, -8 without it |
| Fourth (dealer) | Opponent | Must call; -12 when the candidate suit has just one visible card |

Optional calls still require at least two visible trumps. The third-position
preference reflects the partner-leading convention: a trump ace lead may draw
out an opposing nine for the caller's jack to capture. A sufficiently strong
hand can still call third without the jack. This is not a hard game rule or
proof that a third-position caller holds it.

The forced-dealer adjustment reduces the old policy's tendency to prefer a
lone jack over a more substantial holding. For the observed six-card hand
`C_J H_9 H_A S_8 S_10 S_Q`, v1 selects clubs, while v2 selects hearts when
forced. This example demonstrates a policy change, not proven superiority.

The numerical adjustments and thresholds are provisional judgments, not
measured improvements. Move sampling and tactical play do not yet condition
their decisions on these bidding signals. In particular, partner play does
not yet deliberately execute the ace/jack convention.

These weights and thresholds are explicit engineering choices,
not fitted or validated strength estimates. We can review concrete hands
before replacing this baseline with a statistical calling policy. Passing
is currently a threshold decision: it does not simulate subsequent callers.
Match-score strategy remains deferred as agreed.

## Try it through the existing launcher

```powershell
.\START_BELA.cmd --trump C_9 C_J C_K H_A S_Q D_A
.\START_BELA.cmd --trump C_7 C_8 H_7 H_8 S_Q D_K
.\START_BELA.cmd --trump C_7 C_8 H_7 H_8 S_Q D_K --dealer 0 --player 0
.\START_BELA.cmd --trump C_J C_10 H_A S_A D_Q D_K --dealer 1 --player 0
.\START_BELA.cmd --trump C_J H_9 H_A S_8 S_10 S_Q --dealer 0 --player 0 --policy six_card_control_v1
```

The first calls clubs, the second passes, and the third chooses a suit because
seat 0 is the forced dealer. Seats are 0–3 in play order. The default player is
0 and dealer is 3, so player 0 speaks first. Choosing another player/dealer
pair explicitly assumes that every earlier seat passed; the command prints
those assumed passes. It does not read an online game or infer that history.

Append `--json` for machine-readable output for a future connector. The normal
dashboard and existing saved-game formats remain unchanged; pre-calling UI
and persistence are not integrated yet. Existing move Monte Carlo begins
after calling and does not invoke this policy during its current-deal rollouts.

Tests cover calling order for all dealers, early calls, mandatory dealer
calling, invalid histories, strict six-card input, representative strong/weak
hands, all 720 input orders of a reference hand, random-hand legality, and CLI
output. They establish correctness and determinism, not measured playing strength.
