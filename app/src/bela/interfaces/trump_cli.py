"""Local trump advice; JSON output is available for a future browser adapter."""

import argparse
import json

from bela.analysis.trump import CALLING_POLICIES, POLICY, advise_trump
from bela.domain.cards import Card
from bela.domain.players import Seat
from bela.gameplay.calling import CallingObservation, CallingState


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rank trump suits from six visible cards. No network or API.")
    parser.add_argument("cards", nargs=6, help="Six cards, e.g. C_9 C_J C_K H_A S_Q D_A")
    parser.add_argument("--dealer", type=int, choices=range(4), default=3)
    parser.add_argument("--player", type=int, choices=range(4), default=0)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--policy", choices=CALLING_POLICIES, default=POLICY)
    args = parser.parse_args(argv)
    try:
        state = CallingState(Seat(args.dealer))
        player = Seat(args.player)
        # This command explicitly represents the player's turn after all earlier
        # seats passed. It does not infer actual online events.
        while state.next_player != player:
            state = state.pass_turn(state.next_player)
        advice = advise_trump(CallingObservation(player, tuple(Card.parse(c) for c in args.cards), state), args.policy)
    except ValueError as error:
        parser.error(str(error))
    data = {
        "policy": advice.policy, "score_kind": "heuristic_not_probability",
        "assumed_prior_passes": [int(s) for s in state.passes],
        "action": "pass" if advice.action is None else "call",
        "trump": None if advice.action is None else advice.action.value,
        "forced": advice.forced, "threshold": advice.threshold,
        "calling_position": advice.position, "first_leader": advice.first_leader,
        "rankings": [{"suit": row.suit.value, "score": row.score,
                      "trump_count": row.trump_count, "qualifies": row.qualifies,
                      "components": dict(row.components)} for row in advice.rankings],
    }
    if args.json:
        print(json.dumps(data, allow_nan=False))
        return
    print(f"Trump advice ({advice.policy}) - heuristic scores, not success probabilities")
    print("Earlier seats assumed to have passed:", ", ".join(map(str, state.passes)) or "none")
    print(f"Calling position: {advice.position}; first lead: {advice.first_leader}")
    print("Recommendation:", "PASS" if advice.action is None else f"CALL {advice.action.value}",
          "(dealer must call)" if advice.forced else f"(call threshold {advice.threshold}; at least two trumps)")
    for row in advice.rankings:
        print(f"  {row.suit.value}: {row.score} | {row.trump_count} trumps")
        print("    " + "; ".join(f"{name} {value:+d}" for name, value in row.components if value))


if __name__ == "__main__":
    main()
