# What we know

Open a match in the dashboard, then select **What we know** (◎). This view covers the current deal and distinguishes public facts, logical deductions and possible ownership. It supports English/Croatian and the existing day/night themes.

## Reading the panel

- **Public facts** lists spoken declarations, revealed cards, the ordinary meld result and bela/belot announcements. Spoken details remain public after losing the meld contest. When the engine makes your winning meld cards public at declaration completion, they appear here too.
- **Player deductions** shows void suits, absence of stronger cards and ownership implied by bela or 150/200-point quad announcements. Claims about a void suit or stronger cards concern what remains in the player's hand. Bela and quads explicitly refer to the initial hand.
- **Card ownership** covers unplayed cards outside your remaining hand. Owner chips identify players, using the existing seat numbers 0–3. A single remaining owner is proven; multiple owners indicate alternatives. Revealed ownership is labeled separately from deduced ownership. Filter by suit and open **Why these owners?** to inspect exclusions and their sources.
- **Sources** open the corresponding active event in Event history and focus its row. Starting-hand sources open the existing setup dialog. Sources for a conclusion based on combined evidence include the starting hand and recorded events; they are a sufficient context, not a claimed minimal explanation.

Possible does not mean likely. No probabilities or sampled hidden hands appear in this view. Your initial cards are private information available to you, even when used to eliminate an opposing owner.

## Corrections and unfinished checks

Every accepted edit, insertion, deletion, setup correction, loaded match or next deal produces knowledge for that match identity, revision and deal number. The browser rejects stale results. Source indexes are rebuilt from the corrected active history, not the original archived positions.

Ownership is checked by asking whether the validated initial deal can still exist with that card assigned to each candidate player. Proven impossibility removes an owner; a successful check confirms that at least one supporting deal exists. Internal supporting hands are never exposed.

A single owner check has a 50 ms / 8,000-operation budget. A response normally spends at most about 750 ms on these extra checks. If a check is unfinished, its owner stays in the candidate list with a question mark. An unfinished check cannot create an exclusion or a false proven owner. **Refresh knowledge** retries checks; completed proofs are cached by their exact ownership domains and meld constraints. If only one owner survives proven exclusions, the already validated base deal proves that owner without needing another successful search.

Knowledge is fetched separately from normal state updates. The HTTP adapter analyzes an immutable match snapshot without holding the input lock throughout the extra checks. Refreshing knowledge does not change the match or write its save file. Some very complex cases may remain unfinished after retries.

## Implementation

`tracking.py` records explanations at the same points where its existing replay forces ownership or excludes cards under the play rules. It attaches immutable `KnowledgeEvidence` to the reconstructed state. `knowledge.py` performs bounded support checks, derives additional void suits from the supported remaining-card owners, and returns only permitted knowledge. It does not maintain a second implementation of legal-play rules.

`GET /api/knowledge` returns:

```text
match_id, revision, deal_number, player
facts: active event index, public event, newly public winning-meld cards
deductions: reason kind, player, active event sources and relevant suit/cards
cards: card, candidate owners, confirmed possible owners, exclusions and reasons,
       ownership origin, revealed status, check completeness
own_hand, played_count, revealed_count, complete, pending_checks
```

Reason kinds are structured identifiers, localized in `interfaces/web/knowledge.js` through the shared Croatian catalog. Full initial ownership domains, private validator witnesses and hypothetical opposing hands are not part of the response. Evidence is rebuilt on replay and is not added to the archive schema.

Tests cover initial possibilities, hidden-witness privacy, discarding/trumping/heading deductions, following after a cut, spoken quads versus actual reveals, compound meld clues, hand-capacity deductions, losing spoken facts, own winning reveals, source-index corrections, save/load, unfinished checks, read-only HTTP access and browser request races. Browser checks also verify source navigation, a corrected earlier move, both languages and both themes.
