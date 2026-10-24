# Tracked game to simulation bridge

`simulation_bridge.py` prepares a resumable synthetic game from an immutable
tracked revision and a hypothetical initial deal. It is the connection between
the [hand sampler](SAMPLING.md) and future Monte Carlo rollouts. It does not rank
moves or estimate success probabilities.

## API

```python
from bela.analysis.advisor import analyze
from bela.analysis.sampling import HandSampler
from bela.gameplay.simulation import observe, play_card
from bela.analysis.simulation_bridge import SimulationBridge

# match is the current tracked UserMatch. Prepare once per analysis revision.
bridge = SimulationBridge.from_match(match, expected_revision=match.revision)
sampler = HandSampler(match.state.evidence)
batch = sampler.sample(100, seed=42, seconds=1.0)

for deal in batch.deals:
    state = bridge.resume(deal)
    if not state.finished:
        actor = state.next_player
        view = observe(state, actor)
        # Demonstration only: first legal card is not a strategic policy.
        action = analyze(view).legal_actions[0]
        state = play_card(state, actor, action)
```

`bridge.match_id`, `.revision` and `.deal_number` identify the source snapshot.
The bridge stays fixed when the user edits the match. A future analysis service
must compare this identity with the live match before displaying results. Passing
an old expected revision to `from_match` raises `StaleSimulation`; the bridge does
not monitor live application changes automatically.

Ordinary declarations must be finished before preparing play analysis. Incomplete
declarations raise `IncompleteSimulation`. Finished deals and explicit belot wins
can be reconstructed for verification, but cannot accept further moves.

## Resumption guarantees

For each supplied `SampledDeal`, the bridge:

1. Checks four disjoint eight-card initial hands cover the deck, and verifies all
   ownership domains and structured declaration constraints for this snapshot.
2. Starts a private full simulation using those hypothetical hands and the actual
   trump, caller, dealer and previous match score.
3. Attaches only declaration records obtained from the tracked history. It never
   resolves declarations from hypothetical hidden hands.
4. Replays every recorded move with the existing simulator, including timely bela
   calls. This independently checks that the allocation supports actual play.
5. Checks the current trick, completed tricks, phase, tracked player's hand,
   remaining hand sizes, trick points/counts and bela records against tracking.
   For completed games, it also compares settlement or the belot result.

Bad allocations raise `InvalidSimulationDeal`. Disagreement between simulator
replay and tracked state raises `SimulationMismatch`; this is an implementation
problem that must be investigated, not a probability estimate.

The returned `PlayState` supports the existing `play_card`, `observe` and
`settle_play` functions. Settlement preserves strict contract thresholds, eligible
melds/bela, last-trick points and sweep bonuses through the existing rules.
`match_score` remains the total before this deal; use settled recorded points to
compute the following total, as the existing match session does.

## Public information boundary

The new `declaration_history` field on simulation states and player observations
contains immutable records in the entered order:

- `MeldPresenceAnnouncement`: only explicitly recorded yes/no statements.
- `MeldValueAnnouncement`, `SequenceHighAnnouncement`: actual spoken comparisons,
  including the losing team's claims.
- `CardsRevealedAnnouncement`: exactly the entered public cards, including
  arbitrary reveals that do not themselves form melds.
- `MeldsFinishedAnnouncement`: the recorded winning team and any winning meld
  cards made public implicitly by finishing declarations. This can include the
  tracked player's own winning melds, but never their other private cards.

The existing `meld_contest` summary uses only the public winning-team melds and
recorded presence, which can be partial. Its winning-player tiebreak follows
dealer order. `meld_announcements` preserves spoken values and endpoints. A belot
claim remains available through its public `BelotResult`.

Legacy full simulator setup retains its existing public declaration summaries;
its new history field defaults to empty. The bridge does not pretend that a
missing recorded presence is a spoken "no". A future policy may derive justified
facts from the available records, but must not manufacture announcements.

Full states and bridges contain private information. Policies must receive only
`observe(state, actor)`, which exposes that actor's own remaining hand and public
information. Policies must not close over the bridge, full state, sample or
tracked user's evidence. Tests verify that changing other hidden hands does not
change an actor's observation when their own hand and public information stay
the same. Continuing a simulated game retains its public declaration history.

## Persistence and corrections

Bridged states carry `analysis_only=True`, retained by simulated moves. The full
simulator archive writer rejects them, including belot states without ordinary
declaration history. They contain hypotheses, not actual game hands. Saving the
original `UserMatch` is unchanged and retains only supplied information.

Build a new bridge after an event correction, setup correction or new deal. A
sample from an older snapshot is rejected if it contradicts current evidence;
it may still be a valid hypothesis if it satisfies everything now known. This
does not authorize reusing old move statistics. New-deal reconstruction uses
only the current deal's events and its carried score/dealer.

## Verification and next work

Tests cover partial tricks, recorded losing claims, absent presence records,
arbitrary and implicit reveals, all tracked seats and trump suits, hidden-world
observation invariance, malformed/contradictory samples, stale revisions,
corrections, save/load, next-deal score carry, full 32-card continuations with and
without bela, missed-bela timing, terminal belot and archive isolation.

```powershell
$env:PYTHONPATH = "$PWD/app/src"
python -m unittest discover -s app/tests -p test_simulation_bridge.py
```

Next establish explicit continuation policies, evaluation objectives and
uncertainty reporting, then use this bridge to compare legal moves across shared
sampled deals. These tests establish finite regression evidence, not a proof of
optimal play or empirical playing strength.
