# Hidden-card validation

Implemented on 24 October 2026. The validator answers one question: **does at least one complete initial deal explain the recorded history?** It does not assign probabilities or recommend a move.

## What changed

The previous search enumerated whole eight-card hands and repeatedly constructed card/meld objects before rejecting them. The replacement in `app/src/bela/analysis/validation.py` combines:

- **Compact hand checks.** Bit masks detect the same maximal sequences, four-of-a-kind strengths and belot exception as the object-based rules.
- **Early meld pruning.** Structured constraints capture spoken presence/value/high card, exact winning melds, losing-team strength ceilings and turn-order ties. Incomplete hands can be rejected before enumeration finishes. A forbidden meld missing only one card excludes that card from its potential owner; a uniquely possible required combination forces its cards.
- **Capacity propagation.** Each player needs exactly eight initial cards, including cards already played. Saturated hands and every subset of players constrain ownership. This catches jointly impossible allocations even when each player's constraints look individually possible.
- **Fast witness attempts and exact fallback.** A few deterministic, varied matchings can prove existence quickly. Failed attempts never prove impossibility: bounded exhaustive branching follows, choosing a card with the fewest possible owners. Repeated failed domain states are skipped within that search.
- **Safe reuse.** A process-local cache holds at most 32 successful witness allocations. Every hint must satisfy all current ownership domains and declarations again. It may accelerate a later move, but cannot bypass a correction. Existing immutable replay/session caches remain in place.

Witnesses are internal implementation details. They are not included in tracked state, saves, exports, dashboard responses or benchmark output. The cache is not a sampled belief distribution; no probability can be inferred from its contents or hit rate.

## Preserved behavior

Replay still derives temporal exclusions from following, heading, trumping and overtrumping rules, using **initial** ownership and excluding only cards not already played at that moment. Corrections replay their affected history rather than carrying over old deductions. Own-hand legality, announcement timing, settlement and archive formats are unchanged.

Meld comparison still favors aces among 100-point fours of a kind, compares equal-value sequences by high card rather than length, and resolves equal strengths by seat priority. Exact winning melds include overlap and maximal-run rules. Belot is distinct from an ordinary sequence; before declarations finish, a no-ordinary-meld claim can still be consistent with belot.

The normal budget remains **100,000 search operations and three seconds per allocation check**. Very difficult inputs can still exhaust it. The result remains explicitly unconfirmed, never falsely reported as impossible. Exceptions are not cached as contradictions. Zero budgets also apply to cached hints.

## Reproduce measurements

From the project root:

```powershell
python app/benchmarks/validation.py --runs 10
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests
```

The benchmark includes four reproducible public histories. Cold runs clear replay, witness, compiled-meld and hand-signature caches. The reused-hint measurement clears replay only, so the hint still has to be revalidated. No hidden witness is printed.

Observed locally on 24 October 2026:

| Public history | Previous validator, one cold run | New validator, median of 10 cold runs |
| --- | ---: | ---: |
| No melds, opening bela | 934 ms | 0.43 ms |
| No melds, opponent cuts with trump | 198 ms | 3.13 ms |
| Revealed winning sequence | 413 ms | 0.68 ms |
| Spoken 50-point sequence to ace | 216 ms | 0.37 ms |

These are illustrative measurements on this machine, not universal latency guarantees or statistically matched benchmark campaigns. None of these runs reached the unchanged budget. Earlier full-suite runs encountered validation limits; the existing suite passed after this change.

## Correctness checks

`app/tests/test_validation.py` provides independent comparisons against the object-based rules:

- 1,200 seeded random hands, every sequence length/endpoint, and all four belots.
- Complete-hand meld signatures and declaration constraints.
- Partial-hand pruning checked against every eight-card completion of small available-card sets: no valid completion may be excluded or forced incorrectly.
- Twelve nearly known deals, enumerating all 70 distributions of eight ambiguous cards for each pair of constraints.
- Joint capacity conflicts and mutually impossible 200-point quad claims.
- Stale witness ownership/declarations, legal alternative witnesses, resource-limit retries and exact fallback when fast attempts fail.
- Eight full random legal games across suits/seats, with truthful public presence, values, sequence highs and winning reveals, compared to the simulator after every move.

The existing tests additionally cover event replacement/insertion/deletion, save/load, HTTP rollback and legal-play deductions. This validates the feasibility layer; probability sampling remains a separate next stage.
