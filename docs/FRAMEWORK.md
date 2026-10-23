# Bela engine architecture

The eventual app accepts your cards, total score and public observations, then ranks legal plays with explicit estimates and uncertainty. The engine must remain usable independently of the interface. [RULES.md](RULES.md) defines the agreed game. The original, longer Croatian design discussion is preserved in [translations/FRAMEWORK.hr.md](translations/FRAMEWORK.hr.md).

## Layers and information boundaries

| Layer | Responsibility |
| --- | --- |
| Domain and rules | Immutable cards, seats, legal actions, melds, settlement and victory |
| Session and events | Initial setup, public facts, ordered actions, corrections and revisions |
| Knowledge | Proven constraints, ownership possibilities and the reason for each deduction |
| Belief | Sample hidden deals under an explicit probability model |
| Policies | Decisions from each simulated player's permitted observation |
| Search and evaluation | Compare all legal candidates using shared sampled situations |
| Application | Input, rendering, persistence, asynchronous analysis and explanations |

Full simulator state may contain all hands. A player observation contains only their hand, public facts and justified deductions. Advisor and policy APIs must enforce that boundary. Passing at trump selection is behavioral evidence, not a hard absence constraint. No external AI service is needed for the rules or statistics.

## State and events

Model card identity separately from trump-dependent strength and points. Track seats in play order with team parity, dealer, caller, phase, trick, completed tricks, match totals and the versioned ruleset. Bela and belot have explicit events and timing.

Keep meld presence, spoken strongest value, sequence high card and actual card reveals as separate public events. A losing meld still leaves its spoken constraints. The winning team must reveal all scoring ordinary melds. Constraints concern the hand at the time of the event, including cards played later.

Store setup and an ordered command history. Add, replace, insert, delete and setup corrections create revisions and replay the active history. Preserve earlier versions for audit. Reject inconsistent changes atomically. Starting a later deal carries settled scores and the next dealer. Current archives support resuming mid-trick; player and full-simulator archives have distinct formats.

There are three outcomes of validation: consistent, proven inconsistent, and budget exhausted. Never describe the last as illegal. Player tracking currently checks feasibility of a jointly consistent hidden allocation; this does not sample its probability distribution.

## Knowledge and hidden-card sampling

Derive hard constraints from following, heading, trumping, overtrumping, public ownership and declarations. Attach a reason and event reference to deductions. Rebuild them after corrections. Following after a cut does not prove absence of a higher plain-suit card. Constraints from multiple players and declarations must hold jointly.

Begin with a documented uniform model over all complete allocations satisfying the evidence. A generator must preserve hand capacities and meld combinations, not independently assign cards. Use exhaustive enumeration in small endgames to verify coverage and sampling frequencies. Rejection, backtracking or weighted sampling must report failures, bias and effective sample size where relevant.

Later behavioral likelihoods can weight deals according to observed passes or plays. Separate these assumptions from logical constraints. Record model version and support alternative opponent policies to measure sensitivity.

## First advisor

For each legal move, simulate the rest of the deal over the same sampled hidden deals. Use paired seeds and common random numbers for fair comparisons. Start with random legal and simple heuristic continuation policies, each receiving only its own observation. Avoid giving simulated actors the full deal. A forced legal move can return immediately.

Report expected settled points and our contract success or defensive success. Keep these separate from the probability of taking the current trick. A future match-continuation model incorporates current score, next dealer and future calling policies; until implemented, do not label deal success as match-win probability.

Later evaluate ISMCTS or another justified search method. Plain determinization can suffer from strategy fusion and information-set inconsistency; more samples alone do not remove that bias. Exact full-information endgame search is useful as a diagnostic, not a replacement for information-aware decisions. CFR-style research has limited direct guarantees in this four-player team setting and needs separate validation.

## Ranking and uncertainty

Every result records session/revision, ruleset, objective, method, policy/model versions, seed, sample count, elapsed time and input completeness. Distinguish:

- Probability our team takes this trick, when meaningful.
- Probability the caller succeeds, presented as our success or defensive success.
- Expected settled points per team and their difference after failure and bonuses.
- Match-winning probability only when a verified continuation model exists.

Compare candidates using paired differences. Treat close estimates such as 63% versus 62% as potentially indistinguishable. Define practical tolerance and statistical uncertainty before tagging near-equal choices; overlapping individual intervals alone are insufficient.

Wilson intervals suit independent binary trials. Weighted, adaptive or dependent samples need appropriate methods. Sampling intervals do not capture an incorrect player model or bad input. Validate leading candidates on held-out samples to limit selection bias, and use suitable procedures for repeated interim checking. Explain only facts or measured effects, not invented strategic narratives.

## Application contracts

The following analysis contracts are proposed; the current dashboard API is in [DASHBOARD.md](DASHBOARD.md).

```text
create_session(config) -> session_id, revision, observation
append_event(session_id, expected_revision, event) -> revision, observation, validation
revise_event(session_id, expected_revision, correction) -> revision, validation
get_knowledge(session_id, revision) -> facts, deductions, assumptions
analyze(session_id, revision, objective, time_budget, seed) -> analysis_id
get_analysis(analysis_id) -> status, revision, ranked_actions, diagnostics
cancel_analysis(analysis_id)
export_session(session_id) -> versioned JSON
import_session(versioned_json) -> validation, session_id
```

Analysis must support cancellation, partial results and stale-revision rejection. Distinguish bad format, impossible state, incomplete input, stale state and exhausted computation budget. Later browser, phone, voice or image interfaces should produce the same structured events.

## Technology and project structure

Python provides the rules, replay, simulation and statistical foundation with typed models and tests. The current dashboard is buildless HTML/CSS/JavaScript over a loopback HTTP adapter. TypeScript/React and FastAPI can replace adapters after contracts stabilize. Profile before moving expensive search to a faster implementation. SQLite is an option when JSON sessions become insufficient.

```text
START_BELA.cmd
app/
  run.py
  src/bela/
    domain/ rules/ web/
    tracking.py dashboard.py user_storage.py
    # Later: knowledge/, belief/, policies/, search/
  tests/
docs/
examples/
saves/
```

The first useful statistical version begins with eight cards after talon, full current-deal public history, trump/caller/dealer and match score. It compares legal moves under explicitly stated initial policies. It does not guarantee optimality. Trump advice on six cards, partial-history starts, accounts, online multiplayer, voice, photographs and learned opponent models are later features.

Research directions: Cowling, Powley and Whitehouse, [Information Set Monte Carlo Tree Search](https://eprints.whiterose.ac.uk/id/eprint/75048/), 2012; Lanctot et al., [Monte Carlo Sampling for Regret Minimization in Extensive Games](https://papers.nips.cc/paper_files/paper/2009/hash/00411460f7c92d2124a67ea0f4cb5f85-Abstract.html), 2009. These guide experiments; they do not establish the quality of this Bela implementation.
