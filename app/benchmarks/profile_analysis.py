"""Profile frozen advice inputs, separately from unprofiled runtime measurements.

Every measurement runs in a fresh Python process. No complete games are played.
"""

import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


MODELS = {"tree": "information_set_tree_v1", "tactical": "tactical_v1"}


def category(filename, function):
    path = filename.replace("\\", "/").lower()
    if "/analysis/sampling.py" in path or "/analysis/validation.py" in path:
        return "hidden_hand_sampling_and_constraints"
    if "/analysis/self_search.py" in path:
        return "future_self_search"
    if "/analysis/policies.py" in path:
        return "simulated_player_policies"
    if "/rules/play.py" in path or "/domain/cards.py" in path:
        return "card_rules_and_card_helpers"
    if "/rules/scoring.py" in path or ("/gameplay/simulation.py" in path and function == "settle_play"):
        return "settlement"
    if "/gameplay/simulation.py" in path or "/domain/game.py" in path or "/domain/players.py" in path:
        return "simulation_state_updates_and_observations"
    if "/analysis/simulation_bridge.py" in path:
        return "sampled_world_resume"
    if "/analysis/monte_carlo.py" in path:
        return "analysis_orchestration"
    if path.endswith("/dataclasses.py"):
        return "dataclass_utilities"
    if path.endswith("/random.py") or "_random.Random" in function or "Random.seed" in function:
        return "random_number_generation"
    if path.endswith("/enum.py"):
        return "enum_utilities"
    if function == "__hash__" or "builtins.hash" in function:
        return "object_hashing"
    return "other_python_and_runtime"


def worker(args):
    from bela.analysis.monte_carlo import MonteCarloConfig, analyze_moves
    from bela.storage.analysis_log import analysis_record, append_analysis
    from bela.storage.user_storage import loads_user_match

    source = args.inputs / f"case-{args.case}-original.json"
    original = json.loads(source.read_text(encoding="utf-8"))
    started = perf_counter()
    match = loads_user_match(json.dumps(original["input"]))
    input_seconds = perf_counter() - started
    config = MonteCarloConfig(**(original["advice"]["config"] |
                              {"samples": args.samples, "seconds": 60, "self_policy": MODELS[args.model]}))
    name = f"case-{args.case}-{args.model}-{args.kind}-{args.repeat}"
    profiler = cProfile.Profile() if args.kind == "profile" else None
    started = perf_counter()
    if profiler:
        result = profiler.runcall(analyze_moves, match, config)
    else:
        result = analyze_moves(match, config)
    elapsed = perf_counter() - started
    if profiler:
        profiler.dump_stats(str(args.output / (name + ".prof")))
    started = perf_counter()
    record = analysis_record(match, result, source="frozen_position_profiling",
                             original_record_id=original["record_id"], case=args.case)
    record["provenance"] = "profiling_reanalysis"
    append_analysis(args.output / (name + "-advice.jsonl"), record)
    log_seconds = perf_counter() - started
    estimates = {key: result[key] for key in ("moves", "comparisons")}
    digest = hashlib.sha256(json.dumps(estimates, sort_keys=True).encode()).hexdigest()
    payload = {"case": args.case, "model": args.model, "kind": args.kind, "repeat": args.repeat,
               "samples": args.samples, "completed_samples": result["completed_samples"],
               "status": result["status"], "elapsed_seconds": elapsed,
               "input_restore_seconds": input_seconds, "journal_seconds": log_seconds,
               "estimates_sha256": digest, "candidate_count": len(result["moves"]),
               "selected_card": result["moves"][0]["card"],
               "search": result["strategy_model"]["self_search"]}
    (args.output / (name + ".json")).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if result["status"] != "complete" or result["completed_samples"] != args.samples:
        raise RuntimeError(f"Incomplete measurement: {payload}")


def profile_summary(path):
    stats = pstats.Stats(str(path))
    groups, functions = {}, []
    for (filename, line, function), (primitive, total, own, cumulative, callers) in stats.stats.items():
        group = category(filename, function)
        groups[group] = groups.get(group, 0.0) + own
        functions.append({"file": filename, "line": line, "function": function,
                          "primitive_calls": primitive, "calls": total,
                          "self_seconds": own, "cumulative_seconds": cumulative,
                          "category": group})
    # Exclusive times can be summed. Cumulative times overlap and cannot.
    assert abs(sum(groups.values()) - stats.total_tt) < 1e-5
    return {"profile_self_seconds": stats.total_tt, "groups": groups,
            "top_self_functions": sorted(functions, key=lambda row: row["self_seconds"], reverse=True)[:30],
            "top_cumulative_functions": sorted(functions, key=lambda row: row["cumulative_seconds"], reverse=True)[:20]}


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    args.output = args.output.resolve()
    args.inputs = args.inputs.resolve()
    config = {"inputs": str(args.inputs), "cases": args.cases, "samples": args.samples,
              "repeats": args.repeats, "models": MODELS, "python": platform.python_version(),
              "platform": platform.platform(), "sequential_fresh_processes": True,
              "source_sha256": {str(path.relative_to(Path(__file__).resolve().parents[2])):
                  hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (Path(__file__).resolve().parents[1]/"src"/"bela").rglob("*.py")}}
    (args.output / "config.json").write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
    print(f"Profiling folder: {args.output}", flush=True)
    measurements, cases = [], []
    for case in args.cases:
        for model in MODELS:
            rows = []
            for kind, repeats in (("timing", args.repeats), ("profile", 1)):
                for repeat in range(repeats):
                    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
                               "--inputs", str(args.inputs), "--output", str(args.output),
                               "--case", str(case), "--model", model, "--kind", kind,
                               "--repeat", str(repeat), "--samples", str(args.samples)]
                    subprocess.run(command, check=True)
                    name = f"case-{case}-{model}-{kind}-{repeat}"
                    row = json.loads((args.output / (name+".json")).read_text())
                    measurements.append(row)
                    rows.append(row)
            hashes = {row["estimates_sha256"] for row in rows}
            if len(hashes) != 1:
                raise RuntimeError(f"Profiling changed estimates or timed runs were not reproducible: case {case}, {model}")
            timings = [row["elapsed_seconds"] for row in rows if row["kind"] == "timing"]
            profile = profile_summary(args.output / f"case-{case}-{model}-profile-0.prof")
            case_result = {"case": case, "model": model, "median_unprofiled_seconds": statistics.median(timings),
                           "min_unprofiled_seconds": min(timings), "max_unprofiled_seconds": max(timings),
                           "median_journal_seconds": statistics.median(row["journal_seconds"] for row in rows if row["kind"]=="timing"),
                           "same_estimates_in_all_runs": True, **profile}
            cases.append(case_result)
            print(f"Case {case}, {model}: {statistics.median(timings):.3f}s normal; "
                  f"{rows[-1]['elapsed_seconds']:.3f}s profiled", flush=True)
    summaries = {}
    for model in MODELS:
        selected = [row for row in cases if row["model"] == model]
        total = sum(row["profile_self_seconds"] for row in selected)
        groups = {}
        for row in selected:
            for group, seconds in row["groups"].items():
                groups[group] = groups.get(group, 0.0) + seconds
        summaries[model] = {"sum_case_median_unprofiled_seconds": sum(row["median_unprofiled_seconds"] for row in selected),
                            "exclusive_profile_group_shares": {key: value/total for key,value in sorted(groups.items(), key=lambda kv:kv[1],reverse=True)}}
    report = {"config": config, "cases": cases, "model_summaries": summaries,
              "all_measurements_completed": True, "all_estimates_reproduced": True,
              "limits": ["Six diagnostic positions are not a population latency benchmark.",
                         "Profiler proportions are instrumented costs; use unprofiled wall times for speed comparisons.",
                         "Core advice timings exclude restoring an input and writing its journal, measured separately.",
                         "No C++ speedup is inferred from these measurements."]}
    (args.output / "measurements.json").write_text(json.dumps(measurements,indent=2)+"\n",encoding="utf-8")
    (args.output / "report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summaries,indent=2),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases", type=int, nargs="+", default=[1,2,3,4,5,6])
    parser.add_argument("--case", type=int)
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--kind", choices=("timing","profile"))
    parser.add_argument("--repeat", type=int, default=0)
    options = parser.parse_args()
    if not 1 <= options.samples <= 10000 or not 1 <= options.repeats <= 20:
        parser.error("Samples must be 1–10000 and repeats 1–20.")
    if options.worker:
        if options.output is None or options.case is None or options.model is None or options.kind is None:
            parser.error("Worker requires output, case, model and kind.")
        worker(options)
    else:
        options.output = options.output or Path("saves/profiles")/("analysis-"+uuid4().hex[:8])
        main(options)
