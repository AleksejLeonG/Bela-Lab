# Hidden-hand sampler

The sampler generates transient hypothetical initial deals from the tracked
player's permitted evidence. It does not discover the actual hidden cards, rank
moves or simulate future play. This is the input layer for Monte Carlo analysis.
It uses Python's standard library and requires no service or account.

## Probability model

Every complete initial allocation consistent with the hard evidence has equal
probability. Evidence includes the player's original eight cards, revealed cards,
spoken declarations (including their absence), meld contest results and ownership
restrictions inferred from every recorded legal play. The existing tracker is the
source of those restrictions; sampling does not implement a second set of Bela
rules. Initial hands include cards already played, because declarations concern
the original eight cards.

This is a declared baseline model. It does not weight hands by how likely a human
would be to choose a particular trump or play. The current match score does not
change this distribution; it will matter when evaluating the value of a move.

## Algorithm and correctness

1. Apply sound capacity and structured meld propagation until stable. This only
   removes impossible ownership choices.
2. Count all capacity-correct completions of the resulting domains using dynamic
   programming over card index and four remaining hand sizes.
3. Assign each card using integer random weights equal to its possible completion
   counts. The product of branch probabilities telescopes to `1 / proposal_count`
   for each proposed deal. Randomly choosing among available owners without these
   weights would generally be biased.
4. Reject complete deals that fail any remaining exact declaration constraint.
   Accepted draws therefore have the uniform conditional distribution over valid
   deals. Draws are with replacement; duplicates must not be removed.

`proposal_count` counts deals after propagation and capacity checks, **before**
the final declaration rejection. It is not generally the number of valid deals.
No validator witness, random greedy matching or previously selected hidden deal
is used as a probability sample.

## API

```python
from bela.analysis.sampling import HandSampler

# match is an existing UserMatch; nothing changes or is saved.
state = match.state
sampler = HandSampler(state.evidence, seconds=3.0, max_states=200_000)
batch = sampler.sample(1000, seed=42, seconds=1.0, max_attempts=100_000)

print(len(batch.deals), batch.attempts, batch.stop_reason)
if batch.deals:
    counts = batch.ownership_counts()
    # Counts concern initial ownership. Exclude already played cards in a UI.
    probability = counts[card.id][player] / len(batch.deals)
```

`SampledDeal.masks` holds four initial-hand bit masks. `.hands` converts them into
four frozen sets of cards. `.remaining_hands(played_cards)` removes public played
cards for future simulation. Samples are hypothetical internal analysis data;
never add them to game archives, public observations or the knowledge panel as
facts. The dashboard and save formats are unchanged.

Build a new sampler when the evidence changes, including corrections or a new
deal. A prepared instance stays tied to its original immutable snapshot and can
be reused for additional batches. A fixed seed reproduces a batch when the time
budget permits the same number of attempts. Different seeds give new draws;
reusing one seed restarts the same stream. Parallel callers use separate random
generators, but future aggregation must assign distinct seeds.

## Limits and interpretation

Preparation has separate time and state limits. `SamplingLimit` means preparation
was unfinished, not that the observations were inconsistent. `NoConsistentDeals`
is raised only when impossibility is proved during preparation. Unresolved meld
conditions may make every proposal invalid without preparation proving that.

Sampling stops with `requested_count`, `time_limit` or `attempt_limit`.
`batch.complete` reports whether the requested count was reached. A partial or
empty result never proves a card impossible. `acceptance_rate` reports accepted
deals divided by attempts; it is `None` without attempts. It is an efficiency
diagnostic, not a probability of winning. Time is checked between attempts, so
one in-progress draw may finish after the deadline.

Tight declarations can still make rejection inefficient. The implementation
reports this rather than silently changing the distribution. Future improvements
can count meld-aware completions or enumerate small valid spaces exactly. The
current sampler does not claim a speed guarantee for arbitrary positions.

Ownership frequencies are Monte Carlo estimates under this model. Fixed-count
batches have the usual independent-draw interpretation; time-limited batches
have a runtime-dependent stopping count. Neither removes model uncertainty.
No confidence intervals or move-success percentages are displayed yet.

## Verification and performance

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests -p test_sampling.py
python app/benchmarks/sampling.py --samples 1000 --seconds 2
```

Tests independently enumerate small allocation spaces, compare declaration
eligibility with the object-based rules, check asymmetric-space frequencies and
verify preservation of private hands, public play deductions, evidence corrections,
budgets and save contents. The opening with only one eight-card hand known has
exactly `24! / (8! * 8! * 8!) = 9,465,511,770` possible initial deals.

The benchmark prints preparation cost, attempted/accepted draws and stop reasons
for six evidence scenarios. It does not print hidden hands or alter saves. Its
timings exclude tracked-history replay and future game simulations.

## Foundation audit before Monte Carlo

`test_foundation_audit.py` adds exact checks beyond sampled frequencies:

- Enumerate small original ownership spaces before propagation. Compare every
  surviving valid world with the object-based declaration rules, detecting both
  false inclusions and accidentally excluded legal deals.
- Traverse every positive sampler path in those spaces using rational arithmetic.
  Check equal proposal probability and equal conditional probability after meld
  rejection, without relying on a noisy histogram.
- Across all four trump suits and all four tracked seats, compare the tracker's
  permitted worlds with exhaustive simulator replay of the same public records
  and legal moves. This is a separate inference path, but shares the underlying
  rules functions; it is not an independent implementation of every Bela rule.

These are finite regression checks, not a proof of every arbitrary input. Tight
rejection performance and the uniform model's behavioral limitations remain.

The [simulation bridge](SIMULATION_BRIDGE.md) now connects a tracked revision and
a synthetic deal to a resumable simulation, with checks for exact recorded public
facts, current and previous tricks, bela timing and scoring state. It does not
call `resolve_declarations` on synthetic hands to manufacture missing public
records. Observation tests check invariance when other unrevealed cards change.
New simulated policies must receive only their own observation.

Then establish the rollout policy, evaluation objective and uncertainty reporting
before displaying success percentages. This audit does not certify playing
strength, exact optimality or match-win estimates.
