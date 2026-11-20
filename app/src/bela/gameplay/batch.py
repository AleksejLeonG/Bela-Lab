"""Reproducible local matches: fixed policies or the existing Monte Carlo advisor.

No network, browser or model service is used. Full hands belong to the match
controller; calling and card policies receive only their permitted observation.
"""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from random import Random
from time import perf_counter
from uuid import UUID

from bela.analysis.lineups import StrategyLineup
from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.policies import MIXED_POLICY, choose_move
from bela.analysis.trump import POLICY, advise_trump
from bela.analysis.trump_monte_carlo import (LOCAL_CALLING_POLICIES, MONTE_CARLO_CALL_POLICY,
    TrumpMonteCarloConfig, analyze_trumps)
from bela.analysis.self_search import SELF_SEARCH
from bela.domain.cards import Card, Suit, deck
from bela.domain.game import Seat
from bela.domain.melds import BelotResult
from bela.gameplay.calling import CallingObservation, CallingState
from bela.gameplay.session import MatchSession
from bela.gameplay.simulation import (declare_belot, observe, play_card,
                                      resolve_declarations, settle_play, start_play)
from bela.gameplay.tracking import (AddEvent, DealSetup, FinishDeclarations,
                                    Play, Presence, Reveal, UserMatch)
from bela.rules.melds import has_belot
from bela.rules.play import card_points, trick_winner
from bela.storage.analysis_log import analysis_record


MODES = ("fast", "monte-carlo")


def trick_point_history(state):
    """Completed trick snapshots; declarations and contracts settle separately.

    Play points include the last-trick and sweep bonuses only when earned.
    Match scores remain unchanged until final deal settlement.
    """
    points, counts = [0, 0], [0, 0]
    history = []
    for index, trick in enumerate(state.completed_tricks):
        winner = trick_winner(trick, state.trump)
        value = sum(card_points(card, state.trump) for card in trick.cards)
        points[winner.team] += value
        counts[winner.team] += 1
        last_bonus = [0, 0]
        sweep_bonus = [0, 0]
        if index == 7:
            last_bonus[winner.team] = 10
            if counts[winner.team] == 8:
                sweep_bonus[winner.team] = 90
        history.append({"trick_number": index + 1, "leader": int(trick.leader),
                        "plays": [{"player": int(trick.seat_at(i)), "card": str(card)}
                                  for i, card in enumerate(trick.cards)],
                        "winner": int(winner), "winning_team": winner.team,
                        "card_points": value, "cumulative_card_points": points.copy(),
                        "trick_counts": counts.copy(), "last_trick_bonus": last_bonus,
                        "sweep_bonus": sweep_bonus,
                        "cumulative_play_points": [points[t] + last_bonus[t] + sweep_bonus[t]
                                                   for t in (0, 1)],
                        "match_score_before_settlement": list(state.match_score)})
    return history


@dataclass(frozen=True)
class BatchConfig:
    mode: str
    matches: int = 10
    seed: int = 42
    start_index: int = 0
    calling_policy: str = POLICY
    samples: int = 128
    seconds: float = 8.0
    max_deals: int = 100
    self_policy: str = SELF_SEARCH
    calling_samples: int = 128
    calling_seconds: float = 2.0
    condition_on_passes: bool = False

    def __post_init__(self):
        if self.mode not in MODES or self.calling_policy not in LOCAL_CALLING_POLICIES:
            raise ValueError("Unknown batch mode or calling policy.")
        for name, low, high in (("matches", 1, 100_000), ("seed", 0, 2**64-1),
                                ("start_index", 0, 1_000_000_000), ("max_deals", 1, 1000)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer from {low} to {high}.")
        MonteCarloConfig(self.samples, self.seconds, self.seed, self_policy=self.self_policy)
        TrumpMonteCarloConfig(self.calling_samples, self.calling_seconds, self.seed, self.condition_on_passes)
        if self.calling_seconds <= 0:
            raise ValueError('Calling seconds must be positive.')
        if not isfinite(self.seconds) or self.seconds <= 0:
            raise ValueError("Monte Carlo seconds must be positive.")


def derived_seed(seed, *parts):
    """Independent named streams; changing policy RNG use cannot change deals."""
    raw = ":".join(map(str, ("local-batch-v1", seed, *parts)))
    return int.from_bytes(sha256(raw.encode("utf-8")).digest()[:8], "big")


def dealt_hands(seed, deal_index):
    cards = list(deck())
    Random(derived_seed(seed, "cards", deal_index)).shuffle(cards)
    # First allocate six cards per player; the last eight form four two-card
    # talons. Policies below can only receive hand[:6] until a call is final.
    return tuple(tuple(cards[seat*6:seat*6+6] + cards[24+seat*2:26+seat*2]) for seat in range(4))


class CallingCancelled(Exception):
    pass


def call_deal(hands, dealer, policy=POLICY, *, advisor_player=None, calling_config=None,
              cancelled=None, on_calling=None):
    if (not isinstance(hands, tuple) or len(hands) != 4
            or any(len(hand) != 8 for hand in hands)
            or any(not isinstance(c, Card) for hand in hands for c in hand)
            or len({c for hand in hands for c in hand}) != 32):
        raise ValueError("Expected four disjoint eight-card hands.")
    if policy not in LOCAL_CALLING_POLICIES:
        raise ValueError('Unknown calling policy.')
    if policy == MONTE_CARLO_CALL_POLICY and not isinstance(advisor_player, Seat):
        raise ValueError('Monte Carlo calling requires the evaluated player seat.')
    calling = CallingState(dealer)
    records = []
    while calling.next_player is not None:
        player = calling.next_player
        if policy == MONTE_CARLO_CALL_POLICY and player == advisor_player:
            view = CallingObservation(player, tuple(hands[player][:6]), calling)
            result = analyze_trumps(view, calling_config, cancelled=cancelled)
            if on_calling is not None:
                on_calling(result)
            if result['status'] == 'cancelled' or (cancelled is not None and cancelled()):
                raise CallingCancelled()
            rec = result['recommendation']
            suit = None if rec['action']=='pass' else Suit(rec['suit'])
            records.append({'player':int(player), 'position':len(calling.passes)+1,
                'trump':rec['suit'], 'forced':calling.forced, 'threshold':None,
                'policy':MONTE_CARLO_CALL_POLICY, 'analysis':result})
            calling = calling.pass_turn(player) if suit is None else calling.call_trump(player, suit)
            continue
        advice = advise_trump(CallingObservation(player, tuple(hands[player][:6]), calling),
                              POLICY if policy == MONTE_CARLO_CALL_POLICY else policy)
        records.append({"player": int(player), "position": advice.position,
                        "trump": None if advice.action is None else advice.action.value,
                        "forced": advice.forced, "threshold": advice.threshold,
                        "rankings": [{"suit": row.suit.value, "score": row.score} for row in advice.rankings]})
        calling = (calling.pass_turn(player) if advice.action is None else
                   calling.call_trump(player, advice.action))
    return calling, records


def tracked_observation(state, player, hand, match_id):
    """Create the advisor's record from its own initial eight and public melds.

    Losing hands and their unspoken meld details never enter this record.
    The simulator's truthful contest exposes presence and winning-team cards.
    """
    setup = DealSetup(player, tuple(hand), state.dealer, state.caller, state.trump, state.match_score)
    match = replace(UserMatch.start(setup, name="Local batch advisor"), id=match_id)
    contest = state.meld_contest
    for seat, present in contest.presence:
        match = match.perform(AddEvent(Presence(seat, present)))
    for reveal in contest.revealed:
        if reveal.player != player:
            match = match.perform(AddEvent(Reveal(reveal.player, tuple(sorted(reveal.cards, key=lambda c:c.id)))))
    return match.perform(AddEvent(FinishDeclarations(contest.winning_team)))


@dataclass
class MatchRun:
    record: dict
    session: MatchSession | None


def run_match(config, index, *, cancelled=None, on_analysis=None):
    """One complete match, or an explicitly incomplete/cancelled result.

    In Monte Carlo mode only the evaluated player uses analysis. All other
    seats use hidden fixed profiles. No profile is passed to the advisor.
    """
    if not isinstance(config, BatchConfig) or type(index) is not int or index < 0:
        raise ValueError("Expected a batch config and nonnegative match index.")
    cancelled = cancelled or (lambda: False)
    started = perf_counter()
    seed = derived_seed(config.seed, "match", index)
    player = Seat(index % 4)
    dealer = Seat((index // 4) % 4)
    lineup = StrategyLineup.assign(player, derived_seed(seed, "actual-profiles"))
    match_id = str(UUID(int=(derived_seed(seed, "id-high") << 64) | derived_seed(seed, "id-low")))
    analysis_seed = derived_seed(seed, "analysis")
    record = {"match_index": index, "match_seed": seed, "match_id": match_id,
              "mode": config.mode, "player": int(player), "team": player.team,
              "initial_dealer": int(dealer), "profiles": list(lineup.policies),
              "evaluated_policy": "monte_carlo" if config.mode == "monte-carlo" else "tactical_v1",
              "self_continuation": config.self_policy if config.mode == "monte-carlo" else "tactical_v1",
              "calling_policy": config.calling_policy, "status": "deal_limit",
              "winner": None, "our_win": None, "score": [0, 0], "deals": [],
              "decisions": 0, "mc_decisions": 0, "forced_decisions": 0,
              "completed_trials": 0, "analysis_seconds": 0.0,
              "completed_learning_trials": 0, "total_completed_trials": 0,
              "decision_estimates": [], "calling_estimates": []}
    session = None
    stop = False
    for deal_index in range(config.max_deals):
        if cancelled():
            record["status"] = "cancelled"
            break
        hands = dealt_hands(seed, deal_index)
        if config.calling_policy == MONTE_CARLO_CALL_POLICY:
            def preserve_calling(result):
                entry = {'format':'bela-trump-analysis-record', 'schema_version':1,
                    'provenance':'original_analysis',
                    'context':{'match_index':index, 'deal_index':deal_index, 'phase':'calling'},
                    'input':result['input'], 'advice':result}
                record['calling_estimates'].append(entry)
                if on_analysis is not None:
                    on_analysis(entry)
            try:
                calling, bids = call_deal(hands, dealer, config.calling_policy, advisor_player=player,
                    calling_config=TrumpMonteCarloConfig(config.calling_samples, config.calling_seconds,
                        derived_seed(seed,'calling',deal_index), config.condition_on_passes),
                    cancelled=cancelled, on_calling=preserve_calling)
            except CallingCancelled:
                record['status'] = 'cancelled'
                break
        else:
            calling, bids = call_deal(hands, dealer, config.calling_policy)
        score = (0, 0) if session is None else session.score
        if session is None:
            session = MatchSession.start(start_play(hands, trump=calling.trump, dealer=dealer,
                                                    caller=calling.caller), name="Local batch match")
            session = replace(session, id=match_id)
        else:
            session = session.next_deal(hands, trump=calling.trump, caller=calling.caller)
        state = session.current
        belot = next((Seat((int(dealer)+i)%4) for i in range(1,5)
                      if has_belot(hands[Seat((int(dealer)+i)%4)])), None)
        state = declare_belot(state, belot) if belot is not None else resolve_declarations(state)
        tracked = None
        if config.mode == "monte-carlo" and not state.finished:
            tracked = tracked_observation(state, player, hands[player], match_id)
        while not state.finished:
            if cancelled():
                record["status"] = "cancelled"
                stop = True
                break
            actor = state.next_player
            ply = len(state.completed_tricks)*4 + len(state.current_trick.cards)
            if config.mode == "monte-carlo" and actor == player:
                advice = analyze_moves(tracked, MonteCarloConfig(config.samples, config.seconds,
                                       analysis_seed, MIXED_POLICY, self_policy=config.self_policy), cancelled=cancelled)
                record["analysis_seconds"] += advice["elapsed_seconds"]
                selected = (advice["moves"][0] if advice["status"] == "forced_move" else
                            min(advice["moves"], key=lambda row: row["rank"]) if advice["completed_samples"] else None)
                entry = analysis_record(tracked, advice, match_index=index, deal_index=deal_index,
                                        ply=ply, selected_move=None if selected is None else
                                        {"card": selected["card"], "bela": selected["bela"]})
                record["decision_estimates"].append(entry)
                try:
                    if on_analysis is not None:
                        on_analysis(entry)
                except (OSError, ValueError) as error:
                    record.update(status="diagnostic_write_error", error=str(error))
                    stop = True
                    break
                if cancelled():
                    record["status"] = "cancelled"
                    stop = True
                    break
                if advice["status"] == "forced_move":
                    choice = advice["moves"][0]
                    record["forced_decisions"] += 1
                elif advice["completed_samples"]:
                    choice = min(advice["moves"], key=lambda row:row["rank"])
                    record["mc_decisions"] += 1
                    record["completed_trials"] += advice["completed_samples"]
                    record["completed_learning_trials"] += advice.get("completed_learning_samples", 0)
                    record["total_completed_trials"] += advice.get("total_completed_trials", advice["completed_samples"])
                else:
                    record["status"] = "cancelled" if cancelled() else "analysis_unavailable"
                    stop = True
                    break
                card, bela = Card.parse(choice["card"]), choice["bela"]
            else:
                move = choose_move(observe(state, actor), Random(derived_seed(seed, "play", deal_index, ply)),
                                   lineup.for_player(actor))
                card, bela = move.card, move.bela
            state = play_card(state, actor, card, announce_bela=bela)
            if actor == player:
                record["decisions"] += 1
            if tracked is not None:
                tracked = tracked.perform(AddEvent(Play(actor, card, bela)))
        session = session.with_current(state)
        record["score"] = list(session.score)
        if stop:
            break
        result = settle_play(state)
        deal = {"deal_index": deal_index, "dealer": int(dealer), "caller": int(calling.caller),
                "trump": calling.trump.value, "calling": bids,
                "tricks": trick_point_history(state), "score_before": list(score),
                "score_after": list(session.score), "belot": isinstance(result, BelotResult)}
        if not isinstance(result, BelotResult):
            deal.update(recorded=list(result.recorded), caller_passed=result.caller_passed,
                        our_contract_success=(result.caller_passed if calling.caller.team==player.team
                                              else not result.caller_passed))
        record["deals"].append(deal)
        if session.winner is not None:
            record.update(status="complete", winner=session.winner, our_win=session.winner==player.team)
            break
        dealer = dealer.next
    record["elapsed_seconds"] = perf_counter()-started
    return MatchRun(record, session)


class BatchSummary:
    """Constant-size totals; large batches do not retain every match in RAM."""

    def __init__(self):
        self.statuses = Counter()
        self.wins = 0
        self.totals = Counter()
        self.positions = {str(p): dict.fromkeys(("turns", "calls", "passes", "contracts_made", "contracts_failed"), 0)
                          for p in range(1,5)}

    def add(self, row):
        self.statuses[row["status"]] += 1
        if row["status"] == "complete":
            self.wins += int(row["our_win"])
        for key in ("decisions", "mc_decisions", "completed_trials", "completed_learning_trials",
                    "total_completed_trials", "analysis_seconds"):
            self.totals[key] += row.get(key, 0)
        for deal in row["deals"]:
            for bid in deal["calling"]:
                counts = self.positions[str(bid["position"])]
                counts["turns"] += 1
                counts["passes" if bid["trump"] is None else "calls"] += 1
            if "caller_passed" in deal:
                counts = self.positions[str(deal["calling"][-1]["position"])]
                counts["contracts_made" if deal["caller_passed"] else "contracts_failed"] += 1

    def result(self):
        complete = self.statuses["complete"]
        total = sum(self.statuses.values())
        return {"matches_recorded": total, "complete_matches": complete,
                "incomplete_matches": total-complete, "statuses": dict(self.statuses),
                "our_wins": self.wins, "our_losses": complete-self.wins,
                "our_win_rate": self.wins/complete if complete else None,
                "calling_by_position": {p:dict(v) for p,v in self.positions.items()},
                **{key:self.totals[key] for key in ("decisions", "mc_decisions", "completed_trials",
                    "completed_learning_trials", "total_completed_trials", "analysis_seconds")}}


def summarize(records):
    """Incomplete matches never enter the win-rate denominator."""
    summary = BatchSummary()
    for row in records:
        summary.add(row)
    return summary.result()
