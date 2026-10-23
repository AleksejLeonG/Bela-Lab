"""Interactive English text interface for a real game from one perspective."""

import argparse
from pathlib import Path
import shlex
import sys

from bela.domain.cards import Card, Rank, Suit
from bela.domain.game import Phase, Seat
from bela.domain.melds import BelotResult
from bela.paths import SAVES_ROOT
from bela.tracking import (AddEvent, Belot, DealSetup, DeleteEvent, FinishDeclarations, InsertEvent,
                           MeldValue, NextDeal, Play, Presence, ReplaceEvent, ReplaceSetup,
                           Reveal, SequenceHigh, UserMatch)
from bela.user_storage import load_user_match, save_user_match


HELP = """Commands
  status / hand / legal         Show the game and your legal cards
  presence 1 yes                Player 1 has melds (or: no)
  meld 1 50                     Strongest announced meld value
  high 1 K                      Announced sequence high card
  reveal 1 S_7 S_8 S_9 S_10     Revealed cards and their owner
  melds none                    No ordinary melds; start play
  melds 0                       Team 0 wins the meld contest (or: 1)
  move 1 H_7                    Record a player's card
  play S_A                      Record the current player's card
  move 0 H_Q bela               Announce bela with the first trump K/Q
  belot 1 <eight cards>         Reveal belot; own hand: belot 0
  history                       List active events with 1-based indexes
  replace 3 move 1 H_8          Replace an event and revalidate
  insert 3 reveal 1 S_7 S_8 S_9 Insert before event 3
  delete 3 / undo               Delete an event / the last event
  setup                         Correct the starting setup
  next                          Start the next deal after scoring
  save [path]                   Save manually; valid changes also autosave
  load path                     Open another player match
  help / quit                   Help / save and close

Cards: H=hearts, S=spades, D=diamonds, C=clubs; ranks 7 8 9 10 J Q K A.
Seats 0–3 follow play order. Teams are 0+2 and 1+3.
Reveal all winning melds before 'melds 0/1'. Your own winning melds
can be inferred from your hand. Do not invent unspoken losing meld details.
Legacy Croatian commands are also accepted.
"""

COMMAND_ALIASES = {'presence': 'ima', 'meld': 'zvanje', 'high': 'vrh', 'reveal': 'pokazi', 'melds': 'zvanja', 'move': 'potez', 'play': 'igraj', 'history': 'povijest', 'replace': 'ispravi', 'insert': 'umetni', 'delete': 'obrisi', 'undo': 'nazad', 'setup': 'postavke', 'next': 'dalje', 'save': 'spremi', 'load': 'ucitaj', 'help': 'pomoc', 'quit': 'izlaz', 'status': 'stanje', 'hand': 'ruka', 'legal': 'legalno'}


def parse_suit(value):
    value = value.strip().lower()
    aliases = {"hearts": Suit.HEARTS, "spades": Suit.SPADES, "diamonds": Suit.DIAMONDS, "clubs": Suit.CLUBS, "h": Suit.HEARTS, "herc": Suit.HEARTS, "srce": Suit.HEARTS, "crvena": Suit.HEARTS,
               "s": Suit.SPADES, "pik": Suit.SPADES, "list": Suit.SPADES, "zelena": Suit.SPADES,
               "d": Suit.DIAMONDS, "karo": Suit.DIAMONDS, "bundeva": Suit.DIAMONDS,
               "c": Suit.CLUBS, "tref": Suit.CLUBS, "zir": Suit.CLUBS, "žir": Suit.CLUBS}
    if value not in aliases:
        raise ValueError("Trump: H/herc, S/pik, D/karo ili C/tref.")
    return aliases[value]


def _ask(prompt, parser, default=None):
    while True:
        text = input(prompt + (f" [{default}]" if default is not None else "") + ": ").strip()
        if not text and default is not None:
            text = str(default)
        try:
            return parser(text)
        except ValueError as error:
            print(f"Check your input: {error}")


def _hand(text):
    hand = tuple(Card.parse(v) for v in text.replace(",", " ").split())
    if len(hand) != 8 or len(set(hand)) != 8:
        raise ValueError("Enter eight distinct cards separated by spaces.")
    return hand


def _score(text):
    numbers = tuple(int(n) for n in text.replace(":", " ").split())
    if len(numbers) != 2 or any(n < 0 for n in numbers):
        raise ValueError("Unesi rezultat parova 0 i 1, examplesce 250:310.")
    return numbers


def wizard(*, previous=None, setup=None):
    if previous is not None:
        player = previous.setup.player
        dealer, score = previous.setup.dealer.next, previous.score
        print(f"New deal: dealer {int(dealer)}, score {score[0]}:{score[1]}.")
    else:
        player = setup.player if setup else _ask("Your seat 0–3", lambda t: Seat(int(t)), 0)
        dealer = _ask("Dealer 0–3", lambda t: Seat(int(t)), int(setup.dealer) if setup else 3)
        score = _ask("Team score 0:1", _score,
                     f"{setup.match_score[0]}:{setup.match_score[1]}" if setup else "0:0")
    caller = _ask("Caller adut 0–3", lambda t: Seat(int(t)), int(setup.caller) if setup else None)
    trump = _ask("Trump H/S/D/C or name", parse_suit, setup.trump.value if setup else None)
    hand = _ask("Your starting eight cards", _hand,
                " ".join(map(str, setup.hand)) if setup else None)
    return DealSetup(player, hand, dealer, caller, trump, score)


def parse_event(words, state):
    if not words:
        raise ValueError("Missing command.")
    command, args = COMMAND_ALIASES.get(words[0].lower(), words[0].lower()), words[1:]
    try:
        if command == "ima" and len(args) == 2:
            if args[1].lower() not in ("da", "ne", "yes", "no"):
                raise ValueError("Use yes or no.")
            return Presence(Seat(int(args[0])), args[1].lower() in ("da", "yes"))
        if command == "zvanje" and len(args) == 2:
            return MeldValue(Seat(int(args[0])), int(args[1]))
        if command == "vrh" and len(args) == 2:
            return SequenceHigh(Seat(int(args[0])), Rank(args[1].upper()))
        if command == "pokazi" and len(args) >= 2:
            return Reveal(Seat(int(args[0])), tuple(Card.parse(c) for c in args[1:]))
        if command == "zvanja" and len(args) == 1:
            return FinishDeclarations(None if args[0].lower() in ("nema", "none") else int(args[0]))
        if command in ("potez", "igraj"):
            if command == "potez":
                player, rest = Seat(int(args[0])), args[1:]
            else:
                player, rest = state.next_player, args
            if player is None or len(rest) not in (1, 2) or (len(rest) == 2 and rest[1].lower() != "bela"):
                raise ValueError("Use: move 1 H_7 [bela] or play H_7 [bela].")
            return Play(player, Card.parse(rest[0]), len(rest) == 2)
        if command == "belot" and args:
            return Belot(Seat(int(args[0])), tuple(Card.parse(c) for c in args[1:]))
    except (ValueError, IndexError) as error:
        raise ValueError(f"Invalid command: {error}") from error
    raise ValueError("Unknown command or wrong argument count. Type 'help'.")


def describe(match):
    state = match.state
    print(f"\n{match.name} | Deal {len(match.deals)} | Revision {match.revision}")
    print(f"You: {int(state.setup.player)} | Partner: {int(state.setup.player.partner)} | "
          f"Trump: {state.setup.trump.value} | Caller: {int(state.setup.caller)}")
    phases = {Phase.DECLARATIONS: "meld declarations", Phase.PLAYING: "playing",
              Phase.DEAL_FINISHED: "deal finished", Phase.MATCH_FINISHED: "match finished"}
    print(f"Total score for teams 0:1: {state.score[0]}:{state.score[1]} | {phases[state.phase]}")
    print("Your hand:", " ".join(map(str, sorted(state.hand, key=lambda c: c.id))) or "empty")
    table = " ".join(f"{int(state.current_trick.seat_at(i))}:{c}"
                     for i, c in enumerate(state.current_trick.cards))
    print("Current trick:", table or "empty")
    print(f"Tricks won: {state.trick_counts} | Card points from completed tricks: {state.trick_points}")
    print(f"Melds (count if the team wins a trick): {state.awarded_melds}")
    if state.bela_announcements:
        print("Bela announced:", ", ".join(str(int(call.player)) for call in state.bela_announcements))
    if state.next_player is not None:
        print("Next player:", int(state.next_player))
        if state.next_player == state.setup.player:
            print("Your legal cards:", " ".join(map(str, state.legal_actions)))
    elif state.result is None:
        print("Record public declarations and finish them before the first card.")
    if isinstance(state.result, BelotResult):
        print("Belot! Winning team:", state.result.winning_team)
    elif state.result is not None:
        print("Earned including bonuses:", state.result.earned, "| Recorded:", state.result.recorded)
        print("Calling team:", "passed" if state.result.caller_passed else "failed")
        if state.winner is not None:
            print("Match winner: team", state.winner)
    print("Other players' unrevealed cards remain unknown. Statistical advice is not available yet.")


def event_text(event):
    if isinstance(event, Presence):
        return f"presence {int(event.player)} {'yes' if event.has_meld else 'no'}"
    if isinstance(event, MeldValue):
        return f"meld {int(event.player)} {event.points}"
    if isinstance(event, SequenceHigh):
        return f"high {int(event.player)} {event.rank.value}"
    if isinstance(event, FinishDeclarations):
        return f"melds {'none' if event.winning_team is None else event.winning_team}"
    if isinstance(event, Play):
        return f"move {int(event.player)} {event.card}" + (" bela" if event.bela else "")
    if isinstance(event, (Reveal, Belot)):
        return f"{'reveal' if isinstance(event, Reveal) else 'belot'} {int(event.player)} " + " ".join(map(str, event.cards))
    raise ValueError("Unknown event.")


def run_console(match, path):
    print(HELP)
    describe(match)
    while True:
        try:
            line = input("bela> ").strip()
        except (EOFError, KeyboardInterrupt):
            try:
                save_user_match(match, path)
                print(f"\nMatch saved: {path}")
            except (ValueError, OSError) as error:
                print(f"\nSaving failed: {error}")
                return 1
            return 0
        if not line:
            continue
        try:
            # Non-POSIX tokenization preserves Windows backslashes in paths.
            words = shlex.split(line, posix=False)
            words = [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
            command = COMMAND_ALIASES.get(words[0].lower(), words[0].lower())
            if command in ("pomoc", "pomoć"):
                print(HELP)
                continue
            if command in ("stanje", "ruka", "legalno"):
                describe(match)
                continue
            if command == "povijest":
                for index, event in enumerate(match.deals[-1].events, 1):
                    print(index, event_text(event))
                print("Revisions and previous contents remain in the match archive.")
                continue
            if command in ("spremi", "izlaz"):
                if len(words) > 2 or (command == "izlaz" and len(words) > 1):
                    raise ValueError("Use 'save [path]' or 'quit'.")
                candidate_path = Path(words[1]) if len(words) == 2 else path
                save_user_match(match, candidate_path)
                path = candidate_path
                print("Saved:", path)
                if command == "izlaz":
                    return 0
                continue
            if command == "ucitaj" and len(words) == 2:
                candidate = load_user_match(words[1])
                match, path = candidate, Path(words[1])
                describe(match)
                continue
            if command == "dalje" and len(words) == 1:
                if match.state.result is None or match.state.winner is not None:
                    raise ValueError("The current deal must be finished and the match must still be ongoing.")
                change = NextDeal(wizard(previous=match.state))
            elif command == "postavke" and len(words) == 1:
                change = ReplaceSetup(wizard(setup=match.deals[-1].setup))
            elif command in ("obrisi", "obriši") and len(words) == 2:
                change = DeleteEvent(int(words[1]) - 1)
            elif command == "nazad" and len(words) == 1:
                change = DeleteEvent(len(match.deals[-1].events) - 1)
            elif command == "ispravi" and len(words) >= 3:
                if COMMAND_ALIASES.get(words[2].lower(), words[2].lower()) == "igraj":
                    raise ValueError("Specify the player when correcting: replace 3 move 1 H_8.")
                change = ReplaceEvent(int(words[1]) - 1, parse_event(words[2:], match.state))
            elif command == "umetni" and len(words) >= 3:
                if COMMAND_ALIASES.get(words[2].lower(), words[2].lower()) == "igraj":
                    raise ValueError("Specify the player when inserting: insert 3 move 1 H_8.")
                change = InsertEvent(int(words[1]) - 1, parse_event(words[2:], match.state))
            else:
                change = AddEvent(parse_event(words, match.state))
            match = match.perform(change)
            try:
                save_user_match(match, path)
                print("Event accepted and saved.")
            except (ValueError, OSError) as error:
                print(f"Event accepted in memory, but saving failed: {error}. Use 'save'.")
            describe(match)
        except (ValueError, OSError) as error:
            print(f"Event rejected: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nInput cancelled. The existing match remains open.")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Track a real Bela game from your perspective")
    parser.add_argument("--load", type=Path, help="Load a player match")
    parser.add_argument("--save", type=Path, help="Autosave file")
    args = parser.parse_args(argv)
    try:
        if args.load:
            match = load_user_match(args.load)
        else:
            print("New match. Only your hand and public information are known.")
            name = input("Match name [My match]: ").strip() or "My match"
            match = UserMatch.start(wizard(), name)
        path = args.save or args.load or SAVES_ROOT / f"{match.id}.player.json"
        save_user_match(match, path)
        raise SystemExit(run_console(match, path))
    except (EOFError, KeyboardInterrupt):
        print("\nInitial setup cancelled.")
    except (ValueError, OSError) as error:
        parser.error(str(error))
