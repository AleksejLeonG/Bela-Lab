"""Run local policy or Monte Carlo matches, with incremental reports."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
from threading import Event
from time import perf_counter
from uuid import uuid4

from bela import RULESET_VERSION
from bela.analysis.trump import CALLING_POLICIES, POLICY
from bela.gameplay.batch import BatchConfig, BatchSummary, MODES, run_match
from bela.paths import SAVES_ROOT
from bela.storage.persistence import save_match


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--mode", required=True, choices=MODES)
    result.add_argument("--matches", type=int, default=10)
    result.add_argument("--seed", type=int, default=42)
    result.add_argument("--start-index", type=int, default=0,
                        help="Replay a match index or continue a seed schedule in a new result folder")
    result.add_argument("--calling-policy", choices=CALLING_POLICIES, default=POLICY)
    result.add_argument("--samples", type=int, default=128, help="Monte Carlo trials per decision")
    result.add_argument("--seconds", type=float, default=8, help="Monte Carlo time budget per decision")
    result.add_argument("--max-deals", type=int, default=100, help="Safety limit per match, not a victory rule")
    result.add_argument("--output", type=Path, help="New result directory; existing directories are never overwritten")
    result.add_argument("--save-games", action="store_true", help="Save full synthetic game archives for replay")
    result.add_argument("--dry-run", action="store_true", help="Validate settings and print the plan without playing or creating files")
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        config = BatchConfig(args.mode, args.matches, args.seed, args.start_index,
                             args.calling_policy, args.samples, args.seconds, args.max_deals)
    except ValueError as error:
        cli.error(str(error))
    metadata = {"format": "bela-local-batch", "schema_version": 1,
                "ruleset_version": RULESET_VERSION, "config": asdict(config),
                "self_policy": "tactical_v1", "other_profiles": "independent_uniform_fixed_per_match",
                "automatic_learning": False, "paid_api_required": False,
                "save_games": args.save_games,
                "advisor_objective": "point_difference", "advisor_scope": "current_deal",
                "calling_inference_in_move_advice": False}
    if args.dry_run:
        print(json.dumps({"dry_run": True, **metadata}, indent=2))
        return 0
    output = args.output or SAVES_ROOT / "batches" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        cli.error(f"Cannot create a fresh output directory: {error}")
    totals = BatchSummary()
    status, exit_code = "complete", 0
    stopped = Event()
    previous_handler = signal.getsignal(signal.SIGINT)

    def stop_requested(signum, frame):
        if stopped.is_set():
            raise KeyboardInterrupt
        stopped.set()
        print("Stopping; saving the current checkpoint...", flush=True)

    signal.signal(signal.SIGINT, stop_requested)
    started = perf_counter()
    print(f"Local {config.mode} batch. Results: {output.resolve()}", flush=True)
    try:
        (output / "config.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        with (output / "matches.jsonl").open("x", encoding="utf-8") as stream:
            for index in range(config.start_index, config.start_index + config.matches):
                if stopped.is_set():
                    status, exit_code = "cancelled", 130
                    break
                run = None
                try:
                    run = run_match(config, index, cancelled=stopped.is_set)
                    row = run.record
                except KeyboardInterrupt:
                    row = {"match_index": index, "status": "cancelled", "winner": None,
                           "our_win": None, "score": None, "deals": []}
                    stopped.set()
                except Exception as error:
                    row = {"match_index": index, "status": "error", "winner": None,
                           "our_win": None, "score": None, "deals": [],
                           "error_type": type(error).__name__, "error": str(error)}
                totals.add(row)
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                stream.flush()
                if args.save_games and run is not None and run.session is not None:
                    games = output / "games"
                    games.mkdir(exist_ok=True)
                    save_match(run.session, games / f"match-{index:06d}.sim.json")
                print(f"Match {index}: {row['status']} | score {row['score']} | "
                      f"{len(row['deals'])} completed deals", flush=True)
                if row["status"] != "complete":
                    status = "cancelled" if row["status"] == "cancelled" else "incomplete"
                    exit_code = 130 if status == "cancelled" else 1
                    break
    except KeyboardInterrupt:
        status, exit_code = "cancelled", 130
    except (OSError, ValueError) as error:
        status, exit_code = "output_error", 1
        print(f"Cannot save batch output: {error}", flush=True)
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        summary = {**metadata, **totals.result(), "status": status,
                   "elapsed_seconds": perf_counter()-started}
        try:
            temporary = output / "summary.tmp"
            temporary.write_text(json.dumps(summary, allow_nan=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(output / "summary.json")
        except OSError as error:
            status, exit_code = "output_error", 1
            print(f"Summary could not be saved: {error}", flush=True)
        print(f"Completed matches: {summary['complete_matches']}; our wins: {summary['our_wins']}; "
              f"status: {status}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
