# Croatian four-player Bela — engine reference

Version 1.0, 23 October 2026. This document defines the agreed variant, including the user's clarifications. It takes precedence over other Bela variants. The complete original Croatian specification is retained in [translations/RULES.hr.md](translations/RULES.hr.md).

## 1. Players, teams and objective

Four players form two fixed partnerships seated opposite each other. Seats 0, 1, 2 and 3 follow counterclockwise play order. Team 0 is seats 0+2; team 1 is seats 1+3. Partners share points.

A **trick** contains one card from each player. A **deal** runs from dealing through settlement of eight tricks. A **match** contains successive deals until a team wins. **Calling trump** means choosing its suit; **melds** are scoring card combinations.

## 2. Deck

The deck has 32 unique cards. Suits are hearts (`H`), spades (`S`), diamonds (`D`) and clubs (`C`), each with ranks 7, 8, 9, 10, jack (`J`), queen (`Q`), king (`K`) and ace (`A`). Card codes such as `H_Q` identify individual cards. Croatian names include herc/srce/crvena, pik/list/zelena, karo/bundeva and tref/žir.

## 3. Dealing

The dealer shuffles and offers the player on the left a cut, then deals counterclockwise starting on the right: three cards each, three more each, then two separately reserved talon cards each.

Each player eventually has eight cards. They may inspect their first six when their turn to choose trump arrives. Their two talon cards remain hidden until trump is chosen. After each deal, the dealer advances one seat in play order.

## 4. Choosing trump

The player on the dealer's right decides first. Each player either chooses one of the four suits or passes. A choice immediately ends the process. There is one round and no numerical contract bidding.

If the first three players pass, the dealer must choose: **mus**. The dealer cannot pass again. Mus does not lower the required score. After trump is chosen everyone picks up their talon. The caller's partnership is the calling team; opponents try to defeat its contract.

## 5. Card strength and points

Trump order, strongest first: **J > 9 > A > 10 > K > Q > 8 > 7**.

| Trump rank | J | 9 | A | 10 | K | Q | 8 | 7 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Points | 20 | 14 | 11 | 10 | 4 | 3 | 0 | 0 |

Plain-suit order: **A > 10 > K > Q > J > 9 > 8 > 7**.

| Plain rank | A | 10 | K | Q | J | 9 | 8 | 7 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Points | 11 | 10 | 4 | 3 | 2 | 0 | 0 | 0 |

Every trump beats every non-trump. Without trump in a trick, only the led suit can win. An off-suit non-trump cannot win regardless of its point value.

## 6. Ordinary melds

Determine ordinary melds after picking up the talon and before the first card. Each combination must belong to one player's eight-card hand; partners cannot combine cards. Bela is announced during play instead.

### Four of a kind

Four jacks score 200; four nines score 150. Four aces, tens, kings or queens score 100. Four eights or sevens score nothing. Four sevens do not cancel opposing melds.

### Same-suit sequences

Sequence order is **7–8–9–10–J–Q–K–A**, including trump. Three consecutive cards score 20; four score 50; five, six or seven score 100. Examples: 7–8–9 = 20; 9–10–J–Q = 50; 10–J–Q–K–A = 100.

Count each maximal uninterrupted sequence once. A five-card run does not also score its contained three- and four-card runs. Eight cards of one suit constitute belot.

### Which team scores

Compare the strongest individual meld of each team. The team with the stronger one earns the right to score **all recognized melds held by both partners**. The other team scores no ordinary melds, even if its combined total is larger. Bela is independent of this contest.

### Comparison order

1. Four jacks beat four nines, which beat 100-point melds.
2. A 100-point four of a kind beats a 100-point sequence.
3. Among 100-point fours of a kind: **aces > tens > kings > queens**.
4. Compare sequence points first: **100 > 50 > 20**.
5. Equal-value sequences compare their highest card. Length does not break ties among five-, six- and seven-card runs. Five cards ending at ace beat six ending at king.
6. Equal-value sequences with the same high card favor the earlier player. For completely equal melds use turn order starting on the dealer's right.

A trump sequence has no additional priority.

### Overlap

A card may belong to different meld types: a queen can participate in four queens and a sequence. This does not allow separately scoring subruns of one uninterrupted sequence. Bela can score in addition to other combinations containing its king and queen.

### Announcements and reveals

Starting on the dealer's right, each player states whether they have melds. If opposing teams have melds, ask the earliest announcing player for the value of their strongest individual meld. Opponents announce a higher value if they have one, for example 50.

If opposing sequences have equal value, ask the earliest player for their sequence's high card. An opponent with a stronger meld reveals theirs; otherwise they ask the first player to reveal. Apply every comparison rule above, including four-of-a-kind priority.

The winning team must reveal **all** its scoring ordinary melds. The losing team need not reveal anything. Previously spoken facts remain public even after losing the contest. Record presence, spoken values, spoken high cards, revealed cards and their owners separately. A spoken value does not reveal an entire hand.

## 7. Bela

Bela is the trump king and queen in one player's hand, worth 20. Say “bela” when first playing either card while holding the pair. Either may be first. Saying “of bela” with the second card is optional.

A missed first announcement cannot be claimed late. Bela is independent of the ordinary meld contest and can overlap other combinations. Its team must win at least one trick to receive the points.

## 8. Belot

One player holding all eight cards of a suit has belot. A declared and verified belot wins the **entire match immediately**, regardless of score. It is an exception to normal deal completion, not an ordinary 100-point sequence. Opposing claims require all eight revealed cards; the user's own hand is already known to the engine.

## 9. Flow of play

The player on the dealer's right leads first regardless of the caller. A leader may play any card. Others act counterclockwise and obey legal-play rules. After four cards, the winner collects the trick for their team and leads the next. Play eight tricks.

## 10. Legal play

**Follow suit:** if you have any card of the led suit, you must play that suit. You cannot trump or discard another suit while able to follow.

**Head an untrumped plain-suit trick:** while following a non-trump suit, if no trump has been played, beat the strongest led-suit card currently in the trick if possible. Any higher card suffices; you need not play your highest. Otherwise any card of the led suit is allowed. Example: spade 8 is led; with spade 7, K and A, play K or A.

**Follow after a cut:** after a plain-suit trick has been trumped, still follow the led suit if possible, but no longer head its highest card. Example: hearts are trump; spade 8 then heart 7 are played. With spade 7 and A, either spade is legal.

**Trump when void:** if you lack the led suit but have trump, play trump, even when your partner is winning.

**Overtrump:** whenever required to play trump, beat the strongest trump in the trick if possible. With only lower trumps, play one of them. If trump is led, follow and head it if possible. These obligations apply over a partner too. Following a non-trump led suit still takes precedence.

**Discard:** only with neither the led suit nor trump may you play any card. An off-suit non-trump cannot win. Partner ownership of the current trick does not remove following, heading, trumping or overtrumping obligations.

## 11. Trick winner

The highest trump wins if any trump was played; otherwise the highest led-suit card wins. All four cards' points belong to that player's team.

## 12. Trick points

The deck contains 152 card points. The final, eighth trick adds 10, so an ordinary deal is worth **162 before melds**.

## 13. Sweep (štiglja)

Winning all eight tricks adds another 90: **152 + 10 + 90 = 252 before melds**. Add the winning team's eligible melds. A team without a trick gets no meld points, including bela.

## 14. Meld eligibility

A team must win at least one trick for any meld points to count. Either partner may win it, and the trick need not contain positive-value cards. This includes bela.

## 15. Contract success and failure

The caller must earn **strictly more than half** the deal's total recognized points T. Include card points, last trick, sweep bonus and eligible ordinary melds/bela. Success requires `floor(T / 2) + 1`.

| Total T | Minimum |
| ---: | ---: |
| 162 | 82 |
| 182 | 92 |
| 202 | 102 |
| 212 | 107 |
| 262 | 132 |

A tie means failure. Mus uses the same threshold. On success, each team records its earned points: 100:62 stays 100:62. On failure, the caller records zero and opponents record all T: 80:82 becomes 0:162; 106:106 in a 212-point deal becomes 0:212, from the caller's perspective. A dash on paper represents zero in the engine.

## 16. Match victory

Teams normally start at zero. Add settled points after each deal. Complete all eight tricks; reaching the target during play does not end a regular deal early. Settle contract failure **before** checking victory.

- Neither team above 1000: continue.
- Only one above 1000: that team wins.
- Both above 1000: higher total wins.
- Equal totals above 1000: play another deal, repeating if necessary.

Exactly 1000 is insufficient. Example: 980:970 followed by settled points 90:72 gives 1070:1042; team 0 wins. Points lost through failure cannot cross the target. Belot is the immediate-win exception.

## 17. Irregularities

Violations include failing to follow, head or trump; playing an unheld card; acting out of turn; and viewing concealed cards without permission. The supplied source describes stopping the deal and awarding opponents 162 plus all announced melds for play violations, and separately a 162-point penalty for picking up cards too early.

Normal engine play prevents illegal actions. Penalty settlement is an optional real-game recording feature and is not currently implemented in ordinary simulation.

## 18. Permitted information

During trump selection, a player knows their permitted first six cards, dealer, preceding passes and total score. Their own talon is hidden.

After selection, they know their eight cards, trump/caller, public spoken and revealed meld information, played cards and order, completed trick winners, total score and public deal points. Unrevealed partner/opponent cards remain unknown.

Advice may use only this information and justified deductions. The simulator may contain all hands, but policies must receive only their permitted observations. Hidden talon cards cannot leak into bidding advice.

## 19. Implementation requirements

Settlement order:

1. Count card points and tricks per team.
2. Add 10 for the last trick.
3. Add 90 for a sweep.
4. Recognize ordinary melds only for the contest winner with a trick; recognize timely bela only for its team with a trick.
5. Sum recognized points into T. Excluded melds do not increase it.
6. If the caller has no more than T/2, give it zero and opponents T.
7. Update totals, then check victory. Handle belot separately.

Track constraints over the entire history. Obligatory play can prove a player lacked a suit or stronger card **at that moment**. A pass is behavioral evidence, not proof of a missing card. Keep facts, deductions and statistical assumptions separate.

Advice must evaluate legal actions only and distinguish trick-winning probability, contract success/failure and match-winning probability. The eventual primary objective is our team's match victory, considering the total score. This is an engine objective, not an additional game rule. Estimates depend on hidden-card and player-policy models.

Acceptance examples: 81:81 without melds fails to 0:162; 82:80 succeeds; T=212 requires 107; a sweep without melds records 252:0; bela without a trick adds neither points nor T; five to ace beats six to king; follow a cut plain suit without heading; trump and overtrump when void even over a partner; exactly 1000 does not win; equal scores above 1000 require another deal.

## 20. Provenance

Based on the user's specification and clarifications on 23 October 2026: extra deals for ties above 1000, immediate belot victory, aces first among 100-point fours of a kind, sequence high-card comparison, announcement/reveal procedure and compulsory overtrumping.

The supplied specification cited Croatian Wikipedia's [Belot](https://hr.wikipedia.org/wiki/Belot), [revision 7230117](https://hr.wikipedia.org/w/index.php?title=Belot&oldid=7230117), paraphrased and adapted under CC BY-SA. The agreed project variant takes precedence.
