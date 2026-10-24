"""Measure paired move analysis on a fresh no-meld deal, without saving games."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.policies import ANALYSIS_POLICIES, MIXED_POLICY
from bela.domain.cards import Card, Suit
from bela.domain.game import Seat
from bela.gameplay.tracking import AddEvent, DealSetup, FinishDeclarations, UserMatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--policy", choices=ANALYSIS_POLICIES, default=MIXED_POLICY)
    args = parser.parse_args()
    setup = DealSetup(Seat.ZERO, tuple(Card.parse(c) for c in
                      "H_Q H_K S_9 S_10 S_A D_K C_8 C_9".split()), Seat.THREE, Seat.ZERO, Suit.HEARTS)
    match = UserMatch.start(setup).perform(AddEvent(FinishDeclarations(None)))
    # Match identity seeds latent lineups. Fix it only in this synthetic
    # benchmark so repeating the command reproduces the same virtual matches.
    match = replace(match, id="00000000-0000-4000-8000-000000000042")
    result = analyze_moves(match, MonteCarloConfig(args.samples, args.seconds, 42, args.policy))
    print(json.dumps({"status": result["status"], "completed_samples": result["completed_samples"],
                      "sampling_attempts": result["sampling_attempts"], "elapsed_seconds": result["elapsed_seconds"],
                      "moves": [{"card": row["card"], "point_difference": row["expected_point_difference"],
                                 "success_probability": row["success_probability"]} for row in result["moves"]]}, indent=2))


if __name__ == "__main__":
    main()
