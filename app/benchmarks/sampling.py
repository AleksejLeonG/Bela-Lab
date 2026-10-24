"""Measure hand sampling without printing or saving hypothetical hidden hands.

Run from the project root: python app/benchmarks/sampling.py --samples 1000
"""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bela.domain.cards import Card, Rank, Suit
from bela.domain.game import Seat
from bela.analysis.sampling import HandSampler, SamplingLimit
from bela.gameplay.tracking import (DealSetup, FinishDeclarations, MeldValue, Play, Presence,
                           Reveal, SequenceHigh, replay_deal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.samples < 1 or not 0 < args.seconds < float("inf"):
        parser.error("Samples and finite seconds must be positive.")
    cards = lambda text: tuple(Card.parse(c) for c in text.split())
    setup = DealSetup(Seat.ZERO, cards("H_Q H_K S_9 S_10 S_A D_K C_8 C_9"),
                      Seat.THREE, Seat.ZERO, Suit.HEARTS)
    cases = {
        "opening": (),
        "one_player_no_declarations": (Presence(Seat.ONE, False),),
        "nobody_has_declarations": (FinishDeclarations(None),),
        "spoken_fifty_to_ace": (MeldValue(Seat.ONE, 50), SequenceHigh(Seat.ONE, Rank.ACE)),
        "revealed_winning_sequence": (Reveal(Seat.TWO, cards("H_8 H_9 H_10")), FinishDeclarations(0)),
        "discard_proves_two_void_suits": (FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                                          Play(Seat.ONE, Card.parse("C_7"))),
    }
    results = {}
    for name, events in cases.items():
        # Replay/validation is outside the measured sampling work.
        state = replay_deal(setup, events)
        start = perf_counter()
        try:
            sampler = HandSampler(state.evidence)
        except SamplingLimit as error:
            results[name] = {"preparation_limit": str(error)}
            continue
        preparation = perf_counter() - start
        batch = sampler.sample(args.samples, seed=20261024, seconds=args.seconds)
        results[name] = {
            "preparation_seconds": round(preparation, 6),
            "preparation_states": sampler.preparation_states,
            "proposal_deals_after_propagation": sampler.proposal_count,
            "requested": batch.requested, "accepted": len(batch.deals),
            "attempts": batch.attempts, "acceptance_rate": batch.acceptance_rate,
            "sampling_seconds": round(batch.elapsed_seconds, 6),
            "stop_reason": batch.stop_reason,
        }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
