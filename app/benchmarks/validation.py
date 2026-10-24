"""Reproducible cold/warm validation examples; no private witness is printed.

Run from the project root: python app/benchmarks/validation.py --runs 3
"""

import argparse
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bela.domain.cards import Card, Rank, Suit
from bela.domain.game import Seat
from bela.gameplay.tracking import (DealSetup, FinishDeclarations, MeldValue, Play, Reveal,
                           SequenceHigh, ValidationLimit, replay_deal)


def cases():
    cards = lambda text: tuple(Card.parse(c) for c in text.split())
    setup = DealSetup(Seat.ZERO, cards("H_Q H_K S_9 S_10 S_A D_K C_8 C_9"),
                      Seat.THREE, Seat.ZERO, Suit.HEARTS)
    return setup, {
        "no_melds_opening_bela": (FinishDeclarations(None), Play(Seat.ZERO, Card.parse("H_Q"), True)),
        "no_melds_trump_cut": (FinishDeclarations(None), Play(Seat.ZERO, Card.parse("S_9")),
                               Play(Seat.ONE, Card.parse("H_7"))),
        "revealed_winning_sequence": (Reveal(Seat.TWO, cards("H_8 H_9 H_10")), FinishDeclarations(0)),
        "spoken_fifty_to_ace": (MeldValue(Seat.ONE, 50), SequenceHigh(Seat.ONE, Rank.ACE)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    setup, scenarios = cases()
    result = {}
    for name, events in scenarios.items():
        timings, limits, failures = [], 0, []
        for _ in range(args.runs):
            replay_deal.cache_clear()
            try:
                from bela.analysis.validation import clear_witness_cache, meld_signature, MeldConstraint
                clear_witness_cache()
                meld_signature.cache_clear()
                MeldConstraint.rules.cache_clear()
            except ImportError:
                pass  # Allows comparison with the original validator.
            start = perf_counter()
            try:
                replay_deal(setup, events)
            except ValidationLimit:
                limits += 1
            except ValueError as error:
                failures.append(str(error))
            timings.append(perf_counter() - start)
        replay_deal.cache_clear()
        warm_start = perf_counter()
        try:
            replay_deal(setup, events)
            warm = round(perf_counter() - warm_start, 6)
        except ValueError:
            warm = None
        result[name] = {"cold_median_seconds": round(median(timings), 6),
                        "cold_max_seconds": round(max(timings), 6), "limits": limits,
                        "errors": failures, "runs": args.runs, "revalidated_hint_seconds": warm}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
