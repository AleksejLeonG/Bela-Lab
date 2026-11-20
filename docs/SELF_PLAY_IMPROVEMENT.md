# Preserve trumps when the trick is certainly lost

## Evidence and scope

The three-way runtime comparison retained original public inputs and estimates.
A review grouped identical visible hands and public play histories within the
same scheduled deal, ignoring accumulated match score because the objective
was current-deal points. It found 544 shared nonforced positions and 165 root
disagreements. Large differences are diagnostic leads, not evidence that one
mode is correct; short-budget estimates can be noisy.

Six of the largest disagreements involving the current tree were replayed at
128 paired trials using their original seeds. Four exhibited a specific
future-self pattern: throwing an expensive, stronger trump into a trick already
lost while a cheaper, weaker legal trump was available. There were 202 such
simulated selections across candidate branches; these are not 202 actual moves
or a representative error rate. An example discards the trump nine (14 points)
under an opponent's jack while retaining an eight (zero points).

## One focused change

`analysis/self_search.py:losing_trump_discard` uses only the acting player's
observation and the already verified legal cards. It prefers the lowest-point,
weakest trump only when all of the following hold:

- There are at least two legal cards, all trumps.
- An opponent currently wins with a trump, and every legal card loses to it.
- The opponent's trick is certain: we act fourth, or their trump jack is
  unbeatable even before fourth seat.

It does not activate on a lead, a plain-suit discard, a forced move, a winnable
trick, a partner's winning trick, or an earlier-seat trick where a later partner
could still beat the opposing trump. It prefers keeping a useful trump rather
than donating extra points and strength to a certain loss.

This is a deliberately narrow whole-deal heuristic, not a mathematical proof
that preserving the stronger card is always optimal. Future compulsory play
can make card values context dependent. It adds some policy bias in exchange
for avoiding a demonstrated weakness of sparse random exploration.

The preference applies to future self choices in the default tree and its
shared variants. It is consistent across learning and frozen evaluation in
both learn-then-evaluate modes. The existing three competent direct profiles
already make this cheap-trump choice; their code is unchanged.

Every legal root card is still evaluated. Tree nodes retain all legal actions;
unselected actions receive no invented visits or rewards. Rewards still commit
only after all candidates finish a paired trial. Frozen values remain immutable.
The other three seats retain their unchanged five-profile mixture. Rules,
hand sampling, trump calling and actual player strategies are unchanged.

## Reporting

Search and frozen-evaluation statistics include
`attempted_losing_trump_selections`, separate from forced, exploration and learned
value selections, and `self_play_heuristics: ["certain_losing_trump_v1"]`.
Attempt counts may include a subsequently discarded partial trial. They are
not claims of committed coverage or improved points. Existing policy IDs remain
selectable; the heuristic metadata and source snapshots distinguish this change
from the historical experiments using those IDs.

## Before/after checks

The same 20 known-card endgames, including four challenge cases, were evaluated
at 128 and 512 paired trials with seeds 7, 42 and 119. Exact optimal references
and all opponent policies were unchanged.

| Trials | Before | After | New worse root choices |
| --- | ---: | ---: | ---: |
| 128 | 57/60 optimal | 60/60 optimal | 0 |
| 512 | 57/60 optimal | 60/60 optimal | 0 |

The six improved runs concern the same planning fixture across seeds/budgets:
hearts trump, our remaining cards H9, HQ, S8. The old search preferred HQ;
the new search correctly selects S8 because its later continuation preserves
H9 instead of wasting it under the opponent's HJ. Exact root regret falls from
1.8713 points to zero. This is one repaired decision, not six independent gains.

The preference activated in four of the six saved game positions. One selected
root card changed at 128 trials (H9 to C7 in match 13, deal 5); these hidden-card
positions have no exact optimal reference, so that change is not labelled a
confirmed improvement. Diagnostic and challenge selection make this a
development regression check, not fresh playing-strength evidence. Several
known-card cases have tied root actions.

Artifacts are local under `saves/diagnostics/future-play-review-20261025/`:
original disagreements, traced baseline selections, baseline/candidate source
snapshots, original advice journals, exact-regret summaries and saved-position
results. No large match batch was run for this change.

Eight targeted unit tests cover losing versus winnable tricks, partner support,
fourth-seat certainty, hidden-hand invariance, consistent frozen evaluation,
completed-reward accounting and retention of every legal root action.

## Reproduction

`app/benchmarks/check_trump_discards.py` compares fixed-trial root choices with
the stored exact references and the six traced public inputs. Its output label
must be a fresh subfolder. Baseline results must be captured with the historical
source before applying the change; the original baseline source is retained.

```powershell
$env:PYTHONPATH = "$PWD/app/src;$PWD/app/tests"
python -m unittest test_losing_trump test_self_search test_learned_policy test_competent_fallback
python app/benchmarks/check_trump_discards.py --output saves/diagnostics/future-play-review-20261025 --reference saves/concurrency/runtime-architecture-20261025 --label NEW-CHECK
```
