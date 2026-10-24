# Build workflow

Use [RULES.md](RULES.md) for game behavior and [FRAMEWORK.md](FRAMEWORK.md) for architecture. Work in small playable increments with reproducible examples and acceptance checks. The original Croatian plan is preserved in [translations/WORKFLOW.hr.md](translations/WORKFLOW.hr.md).

## Current status

Implemented: rule library, complete simulator, melds/bela/belot, scoring, versioned simulator and player sessions, own-hand/public-event tracking, consistent-hidden-allocation validation, history corrections, autosave, text input and local dashboard. The dashboard supports English/Croatian and persistent light/dark preferences.

Uniform hidden-hand sampling, a verified simulation bridge and the first paired [Monte Carlo advisor](MONTE_CARLO.md) are implemented. Move advice is available in the dashboard with explicit policies, settled-point/contract objectives and conservative uncertainty. Stronger playing policies, search and match strategy remain to be validated.

Current scope: keep the uniform hidden-deal model and defer learning individual
player behavior. The default advisor samples a [hidden five-strategy mix](STRATEGIES.md),
with a profile fixed for each other player throughout each hypothetical match.
These assignments are unknown to our simulated player. Score-aware
match strategy is deferred; revisit it especially when either team approaches
roughly 800 points or more. This is a development priority, not a change to the
agreed victory rules or a fixed mathematical cutoff for score relevance.

Validation performance has been improved with early meld/capacity pruning and rechecked private witness reuse. [VALIDATION.md](VALIDATION.md) records the method, benchmarks and independent correctness checks; the original computation budget is unchanged.

## Milestones

| Step | Build | Demonstration and acceptance |
| --- | --- | --- |
| 1. Rules | Cards, seats, legal play, melds, trick and match settlement | Eight-trick play; failure at 81:81, success at 82:80, sweep 252, bela without a trick zero; required overtrumping over partners, following after a cut, overlap, belot and target ties |
| 2. Sessions | Own hand, public events, JSON replay, corrections and revisions | Resume mid-trick; replay preserves state; edits rebuild deductions; duplicates and wrong order fail without corrupting saves |
| 3. Knowledge and belief | Explainable constraints and a hidden-deal generator | Every sample fits the full history; small exhaustive cases verify support, hand capacity and sample frequencies; impossible evidence differs from budget exhaustion |
| 4. First advice | Legal random/heuristic policies, deal continuation and paired candidate comparison | Ranked legal cards with settled points and contract estimates; reproducible seeds; no hidden-data leakage; exact small-endgame checks; uncertainty and model assumptions visible |
| 5. Stronger search | Better time allocation, ISMCTS or justified alternative, multiple policies and independent final validation | Measure improvement against a frozen baseline on held-out deals with seat/team swaps and paired intervals; identify close choices; complexity alone is not success |
| 6. Match strategy | Future deals, total score, next dealer and calling policies | Compare identical hands at different scores; test when risk preferences should change; verify terminal outcomes and calibration on independent simulated matches |
| 7. App integration | Input, knowledge and revision-linked advice in the dashboard | Enter an entire deal without development tools; correct early mistakes, resume saves and reject stale analysis; readable phone layout; latency budgets established by measurement |
| 8. Trump advice | Local six-card heuristic baseline implemented; statistical calling remains future work | Baseline rejects talon input and enforces dealer calling. Future statistical advice must also simulate later callers when evaluating pass |
| 9. Advanced input | Partial histories, text/voice, confirmed image recognition, retrospective analysis and opponent models | Prioritize demonstrated benefit; retain the same event/rules boundary; measure data requirements and information leakage |

Calibration in the simulator is separate from quality against humans. A model predicting around 70% should win about that often under its stated continuation model. Real match archives provide a later independent validation source.

## Per-change cycle

1. Record a concrete problem example and expected outcome.
2. Identify the affected layer and permitted player information.
3. Implement the smallest complete change.
4. Run relevant rule/replay/boundary checks.
5. For strategy/statistics changes, compare on held-out scenarios under matched conditions.
6. Save reproducibility metadata: rules/model versions, state, seed and computation budget.
7. Review the result as a user and update affected documentation.

Keep development and evaluation scenarios separate. Do not silently tune against the final evaluation set. Retain minimal anonymized real-game examples sufficient to reproduce issues. Profile actual bottlenecks before optimizing.

## Next implementation

Review the [single online practice test](ONLINE_PRACTICE.md), especially its
capture gap, before another online deal. Calling uses the explained six-card
heuristic, while move advice uses the sampler and paired Monte Carlo. A
standalone online connector and ten-game test remain unfinished. Keep the
engine and connection local without paid model services. Add statistical calling only with explicit models
for unseen talon cards and subsequent callers; keep deal and match outcomes
distinct.
