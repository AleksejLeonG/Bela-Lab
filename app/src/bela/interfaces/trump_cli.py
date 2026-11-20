"""Local trump advice; JSON output is available for a future browser adapter."""

import argparse
import json

from bela.analysis.trump import POLICY, advise_trump
from bela.analysis.trump_monte_carlo import (LOCAL_CALLING_POLICIES, MONTE_CARLO_CALL_POLICY,
    TrumpMonteCarloConfig, analyze_trumps)
from bela.domain.cards import Card
from bela.domain.players import Seat
from bela.gameplay.calling import CallingObservation, CallingState


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rank trump suits from six visible cards. No network or API.")
    parser.add_argument("cards", nargs=6, help="Six cards, e.g. C_9 C_J C_K H_A S_Q D_A")
    parser.add_argument("--dealer", type=int, choices=range(4), default=3)
    parser.add_argument("--player", type=int, choices=range(4), default=0)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--policy", choices=LOCAL_CALLING_POLICIES, default=POLICY)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--condition-on-passes", action="store_true",
                        help="Assume earlier passers used position_control_v2; otherwise passes give no card deductions")
    args = parser.parse_args(argv)
    try:
        state = CallingState(Seat(args.dealer))
        player = Seat(args.player)
        # This command explicitly represents the player's turn after all earlier
        # seats passed. It does not infer actual online events.
        while state.next_player != player:
            state = state.pass_turn(state.next_player)
        view = CallingObservation(player, tuple(Card.parse(c) for c in args.cards), state)
        if args.policy == MONTE_CARLO_CALL_POLICY:
            data = analyze_trumps(view, TrumpMonteCarloConfig(args.samples, args.seconds, args.seed,
                                                            args.condition_on_passes))
            data['score_kind'] = 'monte_carlo_estimate'
            data['assumed_prior_passes'] = [int(s) for s in state.passes]
            if args.json:
                print(json.dumps(data, allow_nan=False))
            else:
                print(f"Experimental Monte Carlo trump advice: {data['status']}, {data['completed_samples']} paired trials")
                rec = data['recommendation']
                print('Recommendation:', rec['action'].upper(), rec['suit'] or '', f"({data['recommendation_source']})")
                print('Earlier pass inference:', data['model']['past_pass_inference'])
                for row in data['rankings']:
                    value, success = row['expected_point_difference'], row['success_probability']
                    print(f"  {row['suit'] or 'PASS'}: " + ('no estimate' if value is None else
                          f"{value:+.2f} net points; team success {success:.1%}"))
            return
        advice = advise_trump(view, args.policy)
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
