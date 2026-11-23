"""Paired development screening; --check-only never contacts a model server."""
import argparse
import json
import os
import platform
import signal
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_baseline import PREFIXES, git, reflexion_assets, run_task, sha256
from src.agent.llama_server import LlamaServer
from src.reflection.instructions import reflection_prompt


CONDITIONS = ("A", "B", "S1", "S2", "S3", "S4", "S5")
SEEDS = (4051, 4052)
COST_KEYS = ("model_calls", "input_tokens", "output_tokens", "inference_seconds", "env_actions")
AUDIT_FIELDS = {
    "reset": ("initial_state_sha256", "memory"),
    "model_request": ("kind", "seed", "prompt_sha256"),
    "model_response": ("kind", "seed", "output"),
    "environment_step": ("command", "state_sha256", "won", "done"),
    "thought": ("text",),
    "attempt_end": ("success", "reason", "env_actions", "policy_turns"),
}


def read_frozen(path, expected):
    text = path.read_text(encoding="utf-8")
    if sha256(text.encode()) != expected:
        raise ValueError(f"Frozen file hash mismatch: {path}")
    return text


def load_inputs():
    protocol = json.loads((ROOT / "configs/seven_arm.json").read_bytes())
    if tuple(protocol["conditions"]) != CONDITIONS or tuple(protocol["seeds"]) != SEEDS:
        raise ValueError("Expected all seven conditions and frozen seeds 4051/4052")
    config = json.loads(read_frozen(ROOT / "configs/baseline.json", protocol["baseline_sha256"]))
    registry = json.loads(read_frozen(ROOT / "configs/task_registry.json", protocol["registry_sha256"]))
    if (version("alfworld"), version("textworld")) != (config["alfworld"]["version"], config["alfworld"]["textworld"]):
        raise ValueError("Install the pinned ALFWorld/TextWorld versions")
    tasks = registry["development"]
    if len(tasks) != 10 or len(set(tasks)) != 10 or set(tasks) & set(registry["held_out"]):
        raise ValueError("Expected ten unique development tasks, disjoint from held_out")
    instructions = {condition: read_frozen(ROOT / item["file"], item["sha256"]).strip() if item else None
                    for condition, item in protocol["conditions"].items()}
    assets = reflexion_assets(config)
    original = assets[1]("prefix check", [])
    if not original.startswith(instructions["B"] + " Here are two examples:"):
        raise ValueError("B instruction differs from the upstream prefix")
    for condition in CONDITIONS[2:]:
        reflection_prompt(assets[1], "prefix check", [], instructions[condition])
    games = {}
    for task_id in tasks:
        game = (ROOT / "data/alfworld" / task_id / "game.tw-pddl").resolve()
        if not json.loads(game.read_bytes())["solvable"]:
            raise ValueError(f"Unsolvable task: {task_id}")
        games[task_id] = game
    if {game.parts[-3].split("-")[0] for game in games.values()} != set(PREFIXES):
        raise ValueError("Development tasks must cover all six task types")
    return protocol, config, tasks, instructions, games, assets


def make_schedule(tasks, seeds):
    if not seeds or list(seeds) != [seed for seed in SEEDS if seed in seeds]:
        raise ValueError("Seeds must be a nonempty ordered subset of 4051, 4052")
    schedule = []
    for seed in seeds:
        for index, task_id in enumerate(tasks):
            offset = (index + SEEDS.index(seed)) % len(CONDITIONS)
            for condition in CONDITIONS[offset:] + CONDITIONS[:offset]:
                schedule.append(dict(seed=seed, task_id=task_id, condition=condition))
    return schedule


def summarize(results, seeds, task_count):
    per_seed, paired = {}, {}
    for seed in seeds:
        by_condition = {c: {r["task_id"]: r for r in results if r["seed"] == seed and r["condition"] == c}
                        for c in CONDITIONS}
        per_seed[str(seed)], paired[str(seed)] = {}, {}
        for condition, rows in by_condition.items():
            attempts = {task: row["attempts"] for task, row in rows.items()}
            first = sum(a[0] for a in attempts.values())
            total = sum(any(a) for a in attempts.values())
            failures = len(rows) - first
            recovered = sum(not a[0] and any(a[1:]) for a in attempts.values())
            per_seed[str(seed)][condition] = {
                "completed_tasks": len(rows), "expected_tasks": task_count,
                "first_successes": first, "first_success_rate": first / len(rows) if rows else None,
                "total_successes": total, "cumulative_success_rate": total / len(rows) if rows else None,
                "initial_failures": failures, "recovered": recovered,
                "recovery_rate": recovered / failures if failures else None,
                "attempts": attempts,
                **{key: sum(r.get("cost", {}).get(key, 0) for r in rows.values()) for key in COST_KEYS},
            }
            paired[str(seed)][condition] = {}
            for reference in ("A", "B"):
                common = rows.keys() & by_condition[reference].keys()
                wins = sum(any(rows[t]["attempts"]) and not any(by_condition[reference][t]["attempts"]) for t in common)
                losses = sum(not any(rows[t]["attempts"]) and any(by_condition[reference][t]["attempts"]) for t in common)
                paired[str(seed)][condition][reference] = {
                    "paired_tasks": len(common), "wins": wins, "losses": losses,
                    "ties": len(common) - wins - losses, "net_successes": wins - losses,
                }
    complete = len(results) == len(seeds) * task_count * len(CONDITIONS)
    mean = None
    if complete:
        mean = {c: {"cumulative_success_rate": sum(per_seed[str(s)][c]["cumulative_success_rate"] for s in seeds) / len(seeds),
                    "net_successes_vs_A": sum(paired[str(s)][c]["A"]["net_successes"] for s in seeds) / len(seeds),
                    "net_successes_vs_B": sum(paired[str(s)][c]["B"]["net_successes"] for s in seeds) / len(seeds)}
                for c in CONDITIONS}
    return {"per_seed": per_seed, "paired": paired, "mean_over_requested_seeds": mean,
            "unique_tasks": task_count, "note": "Repeated seeds are not independent tasks; partial rates use completed tasks only."}


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def execute(run, server, seeds, inputs):
    protocol, config, tasks, instructions, games, assets = inputs
    schedule = make_schedule(tasks, seeds)
    run.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    metadata = {
        "run_id": run.name, "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")), "protocol": protocol, "config": config,
        "protocol_sha256": sha256((ROOT / "configs/seven_arm.json").read_text(encoding="utf-8").encode()),
        "instructions": instructions, "schedule": schedule,
        "game_sha256": {t: sha256(g.read_bytes()) for t, g in games.items()},
        "python": sys.version, "platform": platform.platform(), "hostname": platform.node(),
        "alfworld": version("alfworld"), "textworld": version("textworld"),
        "started_utc": datetime.now(timezone.utc).isoformat(), "command": sys.argv, "server": server,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "job_log_dir": os.environ.get("P3_JOB_LOG_DIR"),
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes())
                          for folder in ("scripts", "src") for p in sorted((ROOT / folder).rglob("*.py"))},
    }
    write_json(run / "manifest.json", metadata)
    results, reset_hashes, first_attempts = [], {}, {}
    current, audit = {}, []
    cost = dict.fromkeys(COST_KEYS, 0)
    all_cost = dict.fromkeys(COST_KEYS, 0)
    status, error_text = "running", None
    with (run / "trace.jsonl").open("x", encoding="utf-8", buffering=1) as trace, \
            (run / "task_results.jsonl").open("x", encoding="utf-8", buffering=1) as completed:
        def record(event, **fields):
            trace.write(json.dumps({"event": event, **current, **fields}, ensure_ascii=False) + "\n")
            if event == "model_request":
                for target in (cost, all_cost):
                    target["model_calls"] += 1
            if event == "model_response":
                for target in (cost, all_cost):
                    for key in ("input_tokens", "output_tokens", "inference_seconds"):
                        target[key] += fields[key]
            if event == "environment_step":
                cost["env_actions"] += 1
                all_cost["env_actions"] += 1
            if fields.get("attempt") == 1 and event in AUDIT_FIELDS:
                audit.append([event, {k: fields[k] for k in AUDIT_FIELDS[event]}])

        def save_summary():
            summary = summarize(results, seeds, len(tasks))
            if status != "complete":
                summary["mean_over_requested_seeds"] = None
            summary.update(status=status, error=error_text, completed_units=len(results), expected_units=len(schedule),
                           wall_seconds=time.perf_counter() - start, all_cost_including_incomplete=all_cost,
                           active_unit=current if status != "complete" else None,
                           full_two_seed_screening=status == "complete" and tuple(seeds) == SEEDS)
            write_json(run / "summary.json", summary)

        try:
            save_summary()
            model = LlamaServer(server, config["model"], record)
            for current in schedule:
                audit = []
                cost = dict.fromkeys(COST_KEYS, 0)
                condition = current["condition"]
                record("unit_start")
                outcomes = run_task(games[current["task_id"]], condition, {**config, "seed": current["seed"]},
                                    assets, model, record, reset_hashes,
                                    reflection_instruction=instructions[condition] if condition.startswith("S") else None)
                fingerprint = sha256(json.dumps(audit, sort_keys=True).encode())
                key = (current["seed"], current["task_id"])
                reference = first_attempts.setdefault(key, {"condition": condition, "sha256": fingerprint})
                matched = reference["sha256"] == fingerprint
                record("first_attempt_audit", sha256=fingerprint, reference=reference, matched=matched)
                row = {**current, "attempts": outcomes, "cost": dict(cost), "first_attempt_sha256": fingerprint,
                       "first_attempt_matches": matched}
                results.append(row)
                completed.write(json.dumps(row, ensure_ascii=False) + "\n")
                if not matched:
                    raise RuntimeError("First-attempt mismatch: inspect input/seed/backend determinism before interpreting reflection effects")
                save_summary()
                print(f'{len(results)}/{len(schedule)} seed={current["seed"]} {condition} {current["task_id"]}: {outcomes}', flush=True)
            status = "complete"
        except (Exception, KeyboardInterrupt) as error:
            status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            error_text = f"{type(error).__name__}: {error}"
            record("run_error", error=error_text)
            raise
        finally:
            save_summary()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Check frozen inputs without any model requests")
    parser.add_argument("--run-id", help="New directory under logs/; never overwritten")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS), choices=SEEDS)
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    if not args.check_only and (not args.run_id or not args.run_id.isascii() or
                               not args.run_id.replace("-", "").replace("_", "").isalnum()):
        parser.error("--run-id must contain ASCII letters, digits, hyphens or underscores")
    inputs = load_inputs()
    schedule = make_schedule(inputs[2], args.seeds)
    if args.check_only:
        print(json.dumps({"check": "passed", "conditions": CONDITIONS, "seeds": args.seeds,
                          "tasks": len(inputs[2]), "units": len(schedule), "model_requests": 0}, indent=2))
        return
    if git("status", "--porcelain"):
        raise RuntimeError("Commit all changes before collecting experiment results")

    def terminate(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, terminate)
    execute(ROOT / "logs" / args.run_id, args.server, args.seeds, inputs)


if __name__ == "__main__":
    main()
