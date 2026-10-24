"""Reproducible development demo, not a strategic card-playing policy."""

import argparse
import random
import sys
from pathlib import Path

from bela.analysis.advisor import analyze
from bela.domain.cards import Card, Rank, Suit, deck
from bela.domain.game import Phase, Seat
from bela.domain.melds import BelotResult
from bela.storage.persistence import InvalidSaveError, load_match, save_match
from bela.rules.melds import has_belot
from bela.gameplay.session import MatchSession
from bela.gameplay.simulation import (declare_belot, observe, play_card, resolve_declarations,
                             settle_play, start_play)


def _hands(seed: int):
    cards = list(deck())
    random.Random(seed).shuffle(cards)
    return [cards[i:i + 8] for i in range(0, 32, 8)]


def _run(args) -> None:
    if args.load is not None:
        session = load_match(args.load)
        if args.next_deal:
            session = session.next_deal(_hands(args.seed), trump=Suit.HEARTS, caller=Seat.ZERO)
    else:
        if args.next_deal:
            raise ValueError("--next-deal requires --load")
        state = start_play(_hands(args.seed), trump=Suit.HEARTS,
                           dealer=Seat.THREE, caller=Seat.ZERO)
        session = MatchSession.start(state, name=args.name)
    state = session.current
    print("Bela Engine — development demo with melds")
    print(f"Match: {session.name} | Deal: {len(session.deals)}")
    # Zero moves is a checkpoint of exactly the loaded/created phase.
    if args.moves != 0 and state.phase == Phase.DECLARATIONS:
        for player in Seat:
            if has_belot(state.hands[player]):
                state = declare_belot(state, player)
                break
        else:
            state = resolve_declarations(state)
    view = observe(state, Seat.ZERO)
    print(f"Trump: {state.trump.value} | Dealer: {state.dealer.value} | Caller: {state.caller.value}")
    if state.meld_contest is not None:
        print("Ordinary meld points:", state.meld_contest.awarded_points)
    print("My hand:", " ".join(map(str, sorted(view.hand, key=lambda c: c.id))))
    if state.next_player == Seat.ZERO:
        print("Legal cards:", " ".join(map(str, analyze(view).legal_actions)))
    print("Card order is not a recommendation; statistics are not implemented yet.")
    played = 0
    while state.next_player is not None and (args.moves is None or played < args.moves):
        player = state.next_player
        actions = analyze(observe(state, player)).legal_actions
        action = actions[0]
        pair = {Card(state.trump, Rank.KING), Card(state.trump, Rank.QUEEN)}
        call_bela = action in pair and pair.issubset(state.hands[player])
        state = play_card(state, player, action, announce_bela=call_bela)
        played += 1
    session = session.with_current(state)
    if state.finished:
        result = settle_play(state)
        if isinstance(result, BelotResult):
            print(f"Belot: player {result.winner.value}, winning team {result.winning_team}")
        else:
            print("Played eight tricks by choosing the first legal card.")
            print("Earned:", result.earned, "| Recorded:", result.recorded)
            print("Calling team:", "passed" if result.caller_passed else "failed")
    else:
        print(f"Checkpoint: {len(state.completed_tricks)} completed tricks, "
              f"{len(state.current_trick.cards)} cards in the current trick.")
    print("Total score:", session.score, "| Match winner:", session.winner)
    if args.save is not None:
        target = save_match(session, args.save)
        print("Match saved:", target)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "dashboard":
        from bela.interfaces.dashboard import main as dashboard_main
        dashboard_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "track":
        from bela.interfaces.player_cli import main as track_main
        track_main(sys.argv[2:])
        return
    # Windows terminals and redirected streams may otherwise use a code page
    # that cannot encode Croatian characters.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Bela Engine development demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save", type=Path, help="Save the match as JSON")
    parser.add_argument("--load", type=Path, help="Load a saved match")
    parser.add_argument("--name", default="Bela match", help="New match name")
    parser.add_argument("--moves", type=int, help="Additional moves; 0 only loads or saves")
    parser.add_argument("--next-deal", action="store_true", help="Start the next development deal")
    args = parser.parse_args()
    if args.moves is not None and args.moves < 0:
        parser.error("--moves must be nonnegative")
    try:
        _run(args)
    except (InvalidSaveError, ValueError, OSError) as error:
        parser.error(f"Cannot process the match: {error}")
