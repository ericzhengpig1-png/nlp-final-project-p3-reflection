import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.llama_server import LlamaServer
from src.environment.alfworld_text import (
    open_game, policy_observation, state_digest, task_instruction, textworld_command,
)


PREFIXES = {
    "pick_and_place_simple": "put",
    "pick_clean_then_place_in_recep": "clean",
    "pick_heat_then_place_in_recep": "heat",
    "pick_cool_then_place_in_recep": "cool",
    "look_at_obj_in_light": "examine",
    "pick_two_obj_and_place": "puttwo",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def reflexion_assets(config):
    upstream = ROOT / "data/reflexion"
    for name, expected in config["reflexion"]["files"].items():
        if sha256((upstream / name).read_bytes()) != expected:
            raise ValueError(f"Unexpected Reflexion file hash: {name}")
    sys.path.insert(0, str(upstream))
    previous = Path.cwd()
    try:
        os.chdir(upstream)
        from env_history import EnvironmentHistory
        from generate_reflections import _generate_reflection_query
    finally:
        os.chdir(previous)
        sys.path.pop(0)
    prompts = json.loads((upstream / "prompts/alfworld_3prompts.json").read_bytes())
    return EnvironmentHistory, _generate_reflection_query, prompts


def run_task(game_file, condition, config, assets, model, record, reset_hashes):
    history_class, reflection_query, prompts = assets
    task_type = game_file.parts[-3].split("-")[0]
    prefix = PREFIXES[task_type]
    base = ("Interact with a household to solve a task. Here are two examples.\n"
            + prompts[f"react_{prefix}_1"] + prompts[f"react_{prefix}_0"])
    memory = []
    results = []
    for attempt in range(1, config["max_attempts"] + 1):
        ctx = {"attempt": attempt}
        env_seed = config["seed"]
        start_seed = env_seed + 1000 * (attempt - 1)
        random.seed(env_seed)
        with open_game(game_file) as env:
            state = env.reset()
            digest = state_digest(state)
            expected = reset_hashes.setdefault(game_file, digest)
            record("reset", observation=state.feedback, task_instruction=task_instruction(state),
                   initial_state_sha256=digest, expected_state_sha256=expected,
                   admissible_commands=state.admissible_commands, env_seed=env_seed,
                   memory=list(memory[-3:]), **ctx)
            if digest != expected or state["extra.gamefile"] != str(game_file):
                raise RuntimeError(f"Environment reset did not restore {game_file}")
            # Reflexion removes the leading welcome banner on the first observation.
            initial = state.feedback.partition("\n\n")
            history = history_class(base, initial[2] if initial[1] else initial[0], memory[-3:], [])
            history.reset()
            actions = 0
            reason = "policy_turn_cap"
            for turn in range(1, config["max_policy_turns"] + 1):
                action = model.generate(str(history) + ">", "action", start_seed + turn,
                                        policy_turn=turn, **ctx).removeprefix(">").strip()
                history.add("action", action)
                if action.startswith("think:"):
                    feedback, done = "OK.", False
                    record("thought", text=action, policy_turn=turn, **ctx)
                else:
                    command = textworld_command(action)
                    state, reward, done = env.step(command)
                    actions += 1
                    feedback = policy_observation(state.feedback)
                    record("environment_step", action=action, command=command, env_action=actions,
                           policy_turn=turn, observation=state.feedback, agent_observation=feedback,
                           reward=reward, done=bool(done), won=bool(state.won),
                           state_sha256=state_digest(state), **ctx)
                history.add("observation", feedback)
                if state.won:
                    reason = "won"
                    break
                if done:
                    reason = "environment_terminal"
                    break
                if actions == config["max_env_actions"]:
                    reason = "env_action_cap"
                    break
                if history.check_is_exhausted():
                    reason = "repeated_action"
                    break
        success = reason == "won"
        record("attempt_end", success=success, reason=reason, env_actions=actions,
               policy_turns=turn, **ctx)
        results.append(success)
        if success:
            break
        if condition == "B" and attempt < config["max_attempts"]:
            scenario = str(history) + "\n\nSTATUS: FAIL\n\n#####"
            reflection = model.generate(reflection_query(scenario, memory[-3:]),
                                        "reflection", start_seed + 999, **ctx)
            memory.append(reflection)
            record("reflection", text=reflection, next_attempt=attempt + 1, **ctx)
    return results


def manual(game_file, commands, record, config):
    with open_game(game_file) as env:
        initial = env.reset()
        record("reset", observation=initial.feedback, task_instruction=task_instruction(initial),
               initial_state_sha256=state_digest(initial), admissible_commands=initial.admissible_commands)
        print(initial.feedback, flush=True)
        for number in range(1, config["max_env_actions"] + 1):
            action = next(commands, None) if commands is not None else input("> ").strip()
            if not action:
                return False
            command = textworld_command(action)
            state, reward, done = env.step(command)
            record("environment_step", action=action, command=command, env_action=number, observation=state.feedback,
                   won=bool(state.won), done=bool(done), reward=reward, state_sha256=state_digest(state))
            print(f"> {action}\n{state.feedback}\nwon={bool(state.won)}", flush=True)
            if state.won or done:
                return bool(state.won)
    return False


def main():
    parser = argparse.ArgumentParser(description="Run the P3 ALFWorld A/B development baseline.")
    parser.add_argument("mode", choices=["manual", "pilot", "dev"])
    parser.add_argument("--run-id", required=True, help="New subdirectory name under logs/")
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    parser.add_argument("--commands", type=Path, help="One manual action per line")
    args = parser.parse_args()
    if not args.run_id.isascii() or not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("run ID must contain only ASCII letters, numbers, hyphens or underscores")
    if args.commands and args.mode != "manual":
        parser.error("--commands is for manual mode")

    config = json.loads((ROOT / "configs/baseline.json").read_bytes())
    registry = json.loads((ROOT / "configs/task_registry.json").read_bytes())
    count = {"manual": 1, "pilot": 2, "dev": 10}[args.mode]
    tasks = registry["development"][:count]
    if len(tasks) != count or len(set(tasks)) != count:
        raise ValueError("Development registry is missing tasks or contains duplicates")
    run = ROOT / "logs" / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_id": args.run_id, "mode": args.mode, "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")), "config": config,
        "config_sha256": sha256(json.dumps(config, sort_keys=True).encode()),
        "registry_sha256": sha256(json.dumps(registry, sort_keys=True).encode()),
        "task_ids": tasks, "python": sys.version.split()[0], "alfworld": version("alfworld"),
        "textworld": version("textworld"), "started_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv, "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    }
    (run / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    start = time.perf_counter()
    totals = {condition: {"model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                          "inference_seconds": 0.0} for condition in ("A", "B")}
    task_id = condition = None
    with (run / "trace.jsonl").open("x", encoding="utf-8", buffering=1) as trace:
        def record(event, **fields):
            row = {"event": event, "task_id": task_id, "condition": condition, **fields}
            trace.write(json.dumps(row, ensure_ascii=False) + "\n")
            if event == "model_response":
                costs = totals[condition]
                costs["model_calls"] += 1
                for key in ("input_tokens", "output_tokens", "inference_seconds"):
                    costs[key] += fields[key]

        try:
            games = {}
            for task_id in tasks:
                game = (ROOT / "data/alfworld" / task_id / "game.tw-pddl").resolve()
                data = game.read_bytes()
                if not json.loads(data)["solvable"]:
                    raise ValueError(f"Unsolvable task in registry: {task_id}")
                games[task_id] = game
                record("game_file", sha256=sha256(data))
            if args.mode == "manual":
                task_id = tasks[0]
                commands = iter(args.commands.read_text(encoding="utf-8").splitlines()) if args.commands else None
                summary = {"success": manual(games[task_id], commands, record, config)}
            else:
                task_id = None
                model = LlamaServer(args.server, config["model"], record)
                assets = reflexion_assets(config)
                reset_hashes = {}
                summary = {}
                for condition in ("A", "B"):
                    attempts = {}
                    for task_id, game in games.items():
                        attempts[task_id] = run_task(game, condition, config, assets, model, record, reset_hashes)
                        print(f"{condition} {task_id}: {attempts[task_id]}", flush=True)
                    failed_first = [task for task, outcomes in attempts.items() if not outcomes[0]]
                    summary[condition] = {
                        "tasks": len(tasks), "first_successes": len(tasks) - len(failed_first),
                        "total_successes": sum(map(any, attempts.values())),
                        "initial_failures": failed_first,
                        "recovered": sum(any(attempts[task][1:]) for task in failed_first),
                        "attempts": attempts, **totals[condition],
                    }
        except (Exception, KeyboardInterrupt) as error:
            record("run_error", error=f"{type(error).__name__}: {error}")
            raise
    summary["wall_seconds"] = time.perf_counter() - start
    (run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {run.relative_to(ROOT)}", flush=True)
    if args.mode == "manual" and not summary["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
