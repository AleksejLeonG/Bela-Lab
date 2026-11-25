"""Replay three decisions from the 18 November 2026 match at live advice budgets."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))

from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
from bela.analysis.self_search import DIRECT_COMPETENT_SELF_POLICY
from bela.gameplay.tracking import Play
from bela.interfaces.review import historical_match, position_key
from bela.storage.user_storage import dumps_user_match, load_user_match, loads_user_match


# Deal and trick numbers are one-based. The event index is zero-based in Review.
CASES = {
    "opening-lead": (1, 1, 6, "S_9"),
    "exact-tie": (5, 7, 29, "H_8"),
    "points-and-contract": (6, 5, 22, "S_K"),
}
DEPTHS = {"quick": (128, 8), "deep": (512, 15)}
SEEDS = (42, 43, 44, 45, 46)
FORMAT = "bela-saved-match-decisions-v1"
LOCAL_DIR = ROOT / "saves" / "benchmarks"


def write_new(path, data):
    encoded = json.dumps(data, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(encoded)


def validate_position(name, match):
    deal, trick, index, _ = CASES[name]
    state = match.state
    if (len(match.deals) != deal or len(match.deals[-1].events) != index
            or len(state.completed_tricks) + 1 != trick
            or state.next_player != state.setup.player or len(state.legal_actions) < 2):
        raise ValueError(f"{name}: the archive does not match the benchmark position.")


def freeze_positions(path, archive):
    match = load_user_match(archive)
    deals = match.deals
    snapshots = {}
    for name, (deal, _, index, played) in CASES.items():
        if deal > len(deals) or index >= len(deals[deal - 1].events):
            raise ValueError(f"{name}: the recorded decision is missing from the archive.")
        event = deals[deal - 1].events[index]
        if not isinstance(event, Play) or str(event.card) != played:
            raise ValueError(f"{name}: the recorded move differs from the benchmark.")
        snapshot = historical_match(match, position_key(deals, deal - 1, index))
        validate_position(name, snapshot)
        snapshots[name] = json.loads(dumps_user_match(snapshot))
    write_new(path, {"format": FORMAT, "snapshots": snapshots})


def check_exact_tie(result, *, auction_weighting):
    rows = {row["card"]: row for row in result["moves"]}
    if (result["status"] != "exact_endgame" or result["exact_layouts"] != 12
            or rows.keys() != {"H_7", "H_8"}):
        return False
    first, second = rows.values()
    return (first["rank"] == second["rank"] == 1
            and first["success_probability"] == second["success_probability"]
            and first["expected_point_difference"] == second["expected_point_difference"]
            and any(row.get("proven_tie_with_leader") for row in rows.values())
            and (auction_weighting or (isclose(first["success_probability"], 1 / 3)
                                       and isclose(first["expected_point_difference"], 89 / 3))))


def summarize(name, runs):
    summary = {}
    for depth, results in runs.items():
        leaders = ["/".join(row["card"] for row in r["moves"] if row["rank"] == 1) for r in results]
        stats = {
            "leader_counts": dict(Counter(leader or "no estimate" for leader in leaders)),
            "unresolved_runs": sum(any(row["rank"] not in (None, 1)
                                      and row["not_separated_from_leader"] for row in r["moves"])
                                   for r in results),
            "partial_runs": sum(r["status"] != "exact_endgame"
                                and r["completed_samples"] != DEPTHS[depth][0] for r in results),
            "median_seconds": median(r["elapsed_seconds"] for r in results),
        }
        if name == "points-and-contract":
            gaps = []
            for result in results:
                if not result["completed_samples"] and not result["exact_layouts"]:
                    continue
                rows = {row["card"]: row for row in result["moves"]}
                king, jack = rows["S_K"], rows["C_J"]
                gaps.append({
                    "seed": result["config"]["seed"],
                    "point_gap": king["expected_point_difference"] - jack["expected_point_difference"],
                    "contract_gap_percentage_points": 100 * (king["success_probability"] - jack["success_probability"]),
                })
            stats["spade_king_minus_club_jack"] = gaps
        summary[depth] = stats
    return summary


def benchmark(snapshots, *, auction_weighting):
    cases = {}
    for name, (deal, trick, _, played) in CASES.items():
        match = loads_user_match(json.dumps(snapshots[name]))
        validate_position(name, match)
        runs = {}
        print(f"Deal {deal}, trick {trick} ({name})", flush=True)
        for depth, (samples, seconds) in DEPTHS.items():
            runs[depth] = [analyze_moves(match, MonteCarloConfig(
                samples=samples, seconds=seconds, seed=seed, objective="point_difference",
                self_policy=DIRECT_COMPETENT_SELF_POLICY, exact_endgame=True, auction_weighting=auction_weighting,
            )) for seed in SEEDS]
        summary = summarize(name, runs)
        case = {"deal": deal, "trick": trick, "played": played, "summary": summary, "runs": runs}
        if name == "exact-tie":
            case["exact_regression_passed"] = all(check_exact_tie(r, auction_weighting=auction_weighting)
                                                   for results in runs.values() for r in results)
        cases[name] = case
        for depth, stats in summary.items():
            print(f"  {depth:<5} {stats['leader_counts']}  "
                  f"unresolved {stats['unresolved_runs']}/{len(SEEDS)}  "
                  f"partial {stats['partial_runs']}  median {stats['median_seconds']:.3f}s", flush=True)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match", type=Path, help="Player archive to freeze on the first run")
    parser.add_argument("--positions", type=Path, default=LOCAL_DIR / "saved-match-positions.json",
                        help="Local frozen positions, created only when --match is supplied")
    parser.add_argument("--output", type=Path, required=True, help="New JSON report to write")
    parser.add_argument("--auction-weighting", action="store_true", help="Reweight layouts using public calls and passes")
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("The report already exists. Pick a new output path.")
        if args.match is not None:
            freeze_positions(args.positions, args.match)
        raw = args.positions.read_bytes()
        data = json.loads(raw)
        if data.get("format") != FORMAT or set(data.get("snapshots", {})) != CASES.keys():
            raise ValueError("Expected a frozen saved-match benchmark file.")
        cases = benchmark(data["snapshots"], auction_weighting=args.auction_weighting)
        report = {"format": FORMAT, "positions_sha256": sha256(raw).hexdigest(),
                  "seeds": SEEDS, "budgets": DEPTHS, "auction_weighting": args.auction_weighting, "cases": cases}
        write_new(args.output, report)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Report saved to {args.output}")
    passed = cases["exact-tie"]["exact_regression_passed"]
    print(f"Exact tie regression: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
