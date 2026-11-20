"""Offline advice bridge for one externally observed practice deal.

No browser control, credentials, network access or paid services. The caller
must supply complete public history and a fresh visible hand/trick snapshot.
"""

import argparse
import json
from pathlib import Path

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.domain.cards import Card, Suit
from bela.domain.game import Seat, Trick
from bela.gameplay.tracking import AddEvent, UserMatch
from bela.rules.play import legal_cards
from bela.storage.user_storage import _event, _setup, dumps_user_match


def restore_snapshot(data):
    if not isinstance(data, dict) or set(data) != {"match_id", "setup", "events", "visible_hand", "visible_trick"}:
        raise ValueError("Expected match_id, setup, events, visible_hand and visible_trick.")
    if not isinstance(data["events"], list) or len(data["events"]) > 96:
        raise ValueError("Expected one deal's complete public event history.")
    setup = _setup(data["setup"])
    match = UserMatch(data["match_id"], "Bela.fun single practice deal", setup, ())
    for event in data["events"]:
        match = match.perform(AddEvent(_event(event)))
    # Validate identity and serialized history before using the snapshot.
    dumps_user_match(match)
    return match


def inspect_snapshot(data):
    """Derive public state from recorded events without choosing a move."""
    match = restore_snapshot(data)
    state = match.state
    return {"phase": state.phase.value, "hand": sorted(map(str, state.hand)),
            "leader": int(state.current_trick.leader),
            "next_player": None if state.next_player is None else int(state.next_player),
            "trick": [{"player": int(state.current_trick.seat_at(i)), "card": str(c)}
                      for i, c in enumerate(state.current_trick.cards)],
            "completed_tricks": len(state.completed_tricks), "score": list(state.score),
            "awarded_melds": list(state.awarded_melds),
            "trick_points": list(state.trick_points), "trick_counts": list(state.trick_counts)}


def evaluate_snapshot(data, config=None, *, on_analysis=None):
    match = restore_snapshot(data)
    visible = data["visible_hand"]
    if not isinstance(visible, list) or len(visible) > 8:
        raise ValueError("Expected the current visible hand.")
    cards = tuple(Card.parse(c) for c in visible)
    if len(set(cards)) != len(cards) or frozenset(cards) != match.state.hand:
        raise ValueError("Visible hand disagrees with recorded history; stop and resynchronize.")
    expected = [{"player": int(match.state.current_trick.seat_at(i)), "card": str(c)}
                for i, c in enumerate(match.state.current_trick.cards)]
    if data["visible_trick"] != expected:
        raise ValueError("Visible trick disagrees with recorded history; stop and resynchronize.")
    result = analyze_moves(match, config)
    if on_analysis is not None:
        on_analysis(match, result)
    rows = result["moves"]
    if result["status"] == "forced_move":
        choice = rows[0]
    elif result["completed_samples"]:
        choice = min(rows, key=lambda row: row["rank"])
    else:
        raise ValueError("No completed Monte Carlo trials; no move will be selected.")
    return {"card": choice["card"], "bela": choice["bela"],
            "match_id": match.id, "revision": match.revision,
            "deal_limit": 1, "analysis": result}


def forced_visible_move(data):
    """Only a uniquely legal card; no inferred history or statistical estimate.

    Useful after a capture gap. More than one legal action requires stopping,
    rather than quietly replacing Monte Carlo with an arbitrary fallback.
    """
    if not isinstance(data, dict) or set(data) != {"player", "hand", "trump", "leader", "trick"}:
        raise ValueError("Expected player, hand, trump, leader and trick.")
    if any(type(data[k]) is not int or not 0 <= data[k] <= 3 for k in ("player", "leader")):
        raise ValueError("Expected player seats 0-3.")
    if (not isinstance(data["hand"], list) or not 1 <= len(data["hand"]) <= 8
            or not isinstance(data["trick"], list) or len(data["trick"]) > 3):
        raise ValueError("Expected a visible hand and an unfinished trick.")
    hand = tuple(Card.parse(c) for c in data["hand"])
    trick = Trick(Seat(data["leader"]), tuple(Card.parse(c) for c in data["trick"]))
    if trick.next_player != Seat(data["player"]):
        raise ValueError("It is not our turn.")
    legal = legal_cards(hand, trick, Suit(data["trump"]))
    if len(legal) != 1:
        raise ValueError("More than one legal move: complete history is required for advice.")
    return {"card": str(legal[0]), "status": "forced_visible_only", "deal_limit": 1,
            "success_probability": None, "complete_history": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--forced-visible", action="store_true",
                        help="Select only a uniquely legal move from immediate visible cards")
    parser.add_argument("--inspect", action="store_true", help="Validate history and report public state only")
    args = parser.parse_args(argv)
    try:
        if args.snapshot.stat().st_size > 128_000:
            raise ValueError("Practice snapshot is too large.")
        data = json.loads(args.snapshot.read_text(encoding="utf-8"))
        if args.forced_visible and args.inspect:
            raise ValueError("Choose either inspection or visible-only forced advice.")
        diagnostic_paths = []
        def preserve(match, advice):
            from bela.storage.analysis_log import save_analysis
            diagnostic_paths.append(save_analysis(match, advice, source="online_practice"))
        result = (inspect_snapshot(data) if args.inspect else forced_visible_move(data) if args.forced_visible else
                  evaluate_snapshot(data, MonteCarloConfig(args.samples, args.seconds, args.seed),
                                    on_analysis=preserve))
        if diagnostic_paths:
            result["analysis_log"] = str(diagnostic_paths[-1])
        if args.output:
            args.output.write_text(json.dumps(result, allow_nan=False, indent=2) + "\n", encoding="utf-8")
        summary = {k: v for k, v in result.items() if k != "analysis"}
        if "analysis" in result:
            summary |= {
            "status": result["analysis"]["status"],
            "completed_samples": result["analysis"]["completed_samples"],
            "elapsed_seconds": result["analysis"]["elapsed_seconds"]}
        print(json.dumps(summary))
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
