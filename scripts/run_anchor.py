import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from zipfile import ZipFile

from run_baseline import ROOT, git, sha256
from setup_baseline import digest
from src.agent.anchor import AnchorModel, RECIPES, action_head, render, retrieve
from src.agent.llama_server import LlamaServer
from src.environment.alfworld_text import open_game, state_digest, task_instruction


def dump(path, data):
    with path.open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def game_path(task):
    return ROOT / "data/alfworld" / task / "game.tw-pddl"


def family_of(task):
    return task.split("/")[-2].split("-")[0]


def rollout(task, attempt, bank, baseline, config, model, record, reset_hashes):
    family = family_of(task)
    path = game_path(task).resolve()
    steps = []
    start = time.perf_counter()
    seed = baseline["seed"]
    random.seed(seed)
    with open_game(path) as env:
        state = env.reset()
        initial = state_digest(state)
        expected = reset_hashes.setdefault(task, initial)
        if initial != expected or state["extra.gamefile"] != str(path):
            raise RuntimeError("ALFWorld did not restore the registered task")
        goal = task_instruction(state)
        record("reset", goal=goal, initial_state_sha256=initial, env_seed=seed, game_sha256=digest(path))
        reason = "env_action_cap"
        for index in range(1, baseline["max_env_actions"] + 1):
            candidates = list(dict.fromkeys(state.admissible_commands))
            cards = retrieve(bank, family, state.feedback, candidates, config)
            snapshot = {
                "goal": goal, "family": family, "observation": state.feedback,
                "history": [{"action": s["action"], "feedback": s["feedback"]}
                            for s in steps[-12:]],
                "candidates": candidates, "cards": cards,
            }
            prompt = render(snapshot)
            step_seed = seed + 1000 * (attempt - 1) + index
            record("decision", step=index, seed=step_seed, snapshot=snapshot, prompt=prompt)
            action = model.choose(prompt, candidates, step_seed)
            if action not in candidates:
                raise RuntimeError(f"Model returned a non-admissible action: {action!r}")
            state, reward, done = env.step(action)
            step = {"step": index, "snapshot": snapshot, "prompt": prompt,
                    "action": action, "feedback": state.feedback}
            steps.append(step)
            record("environment_step", step=index, action=action, feedback=state.feedback,
                   reward=reward, won=bool(state.won), done=bool(done),
                   state_sha256=state_digest(state))
            if state.won or done:
                reason = "won" if state.won else "environment_terminal"
                break
        result = {"success": bool(state.won), "reason": reason, "env_actions": len(steps),
                  "wall_seconds": time.perf_counter() - start}
    record("attempt_end", **result)
    return goal, steps, result


def prepare_training(archive, tasks, expected):
    if digest(archive) != expected:
        raise ValueError("Unexpected ALFWorld data archive checksum")
    with ZipFile(archive) as games:
        for task in tasks:
            path = game_path(task)
            content = games.read(f"{task}/game.tw-pddl")
            if not json.loads(content)["solvable"]:
                raise ValueError(f"Training task is not marked solvable: {task}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def build(run, tasks, archive, baseline, config, model, record, context):
    start = time.perf_counter()
    prepare_training(archive, tasks, baseline["dataset"]["sha256"])
    candidates, source_steps, task_results = [], {}, {}
    reset_hashes = {}
    for task in tasks:
        context.update(task_id=task, phase="construction", attempt=1)
        goal, steps, result = rollout(task, 1, [], baseline, config, model, record, reset_hashes)
        task_results[task] = result
        context.update(phase="localization")
        notes = model.localize(goal, steps, result["success"], baseline["seed"])
        by_step = {step["step"]: step for step in steps}
        for i, note in enumerate(notes, 1):
            card_id = f'{config["experiment"]}-{len(task_results):02d}-{i:02d}'
            step = by_step.get(note["step"])
            hint = note["hint"]
            if (step is None or not hint.strip() or not note["cue"].strip() or len(hint) > 550
                    or note["recommend"] not in {action_head(a) for a in step["snapshot"]["candidates"]}
                    or (note["role"] == "success_maintain" and note["recommend"] != action_head(step["action"]))):
                record("candidate_invalid", card_id=card_id, note=note)
                continue
            card = {"id": card_id, "source_task": task, "family": family_of(task), **note}
            candidates.append(card)
            source_steps[card_id] = step
            record("candidate", card=card, source_action=step["action"])
        print(f"Training {task.split('/')[-2]} {result['success']} with {len(steps)} actions", flush=True)
    construction_seconds = time.perf_counter() - start
    dump(run / "candidates.json", candidates)
    accepted = []
    start = time.perf_counter()
    for card in candidates:
        context.update(task_id=card["source_task"], phase="screening", attempt=1, card_id=card["id"])
        step = source_steps[card["id"]]
        try:
            result = model.probe(step, card)
        except ValueError as error:
            record("screening", card=card, source_action=step["action"], accepted=False, error=str(error))
            continue
        record("screening", card=card, source_action=step["action"], **result)
        if result["accepted"]:
            accepted.append(card["id"])
        print(f'Screen {card["id"]} JS={result["js_bits"]:.4f} accepted={result["accepted"]}', flush=True)
    screening_seconds = time.perf_counter() - start
    dump(run / "bank.json", {"experiment": config["experiment"], "screened": accepted,
                             "candidates": candidates})
    return {"training": task_results, "candidates": len(candidates), "accepted": len(accepted),
            "construction_seconds": construction_seconds, "screening_seconds": screening_seconds,
            "bank_sha256": digest(run / "bank.json")}


def evaluate(tasks, bank_path, baseline, config, model, record, context):
    bank_bytes = bank_path.read_bytes()
    bank = json.loads(bank_bytes)
    if bank["experiment"] != config["experiment"]:
        raise ValueError("Bank belongs to another experiment")
    accepted = set(bank["screened"])
    candidate_ids = {card["id"] for card in bank["candidates"]}
    if not accepted or not accepted <= candidate_ids or len(candidate_ids) != len(bank["candidates"]):
        raise ValueError("Frozen bank has no valid screened comparison")
    reset_hashes, summary = {}, {}
    for condition in ("screened", "unfiltered"):
        context.update(condition=condition, phase="evaluation")
        cards = [card for card in bank["candidates"] if condition == "unfiltered" or card["id"] in accepted]
        per_task = {}
        begin = time.perf_counter()
        for task in tasks:
            results = []
            for attempt in range(1, baseline["max_attempts"] + 1):
                context.update(task_id=task, attempt=attempt)
                _, _, result = rollout(task, attempt, cards, baseline, config, model, record, reset_hashes)
                results.append(result)
                if result["success"]:
                    break
            per_task[task] = results
            print(condition, task.split("/")[-2], [r["success"] for r in results], flush=True)
        summary[condition] = {
            "tasks": per_task, "first_successes": sum(r[0]["success"] for r in per_task.values()),
            "successes": sum(any(a["success"] for a in r) for r in per_task.values()),
            "wall_seconds": time.perf_counter() - begin,
        }
    if bank_path.read_bytes() != bank_bytes:
        raise RuntimeError("Frozen memory bank changed during evaluation")
    return {"bank_sha256": sha256(bank_bytes), **summary}


def main():
    parser = argparse.ArgumentParser(description="Independent Anchor transfer experiment, attempt 1.")
    parser.add_argument("mode", choices=("probe", "build", "pilot", "dev"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    if not args.run_id.isascii() or not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Use an ASCII run ID containing letters, numbers, underscores or hyphens")
    if args.mode == "build" and args.archive is None:
        parser.error("build requires --archive")
    if args.mode in ("pilot", "dev") and args.bank is None:
        parser.error("pilot and dev require --bank")

    config = json.loads((ROOT / "configs/anchor_attempt1.json").read_bytes())
    baseline = json.loads((ROOT / "configs/baseline.json").read_bytes())
    registry = json.loads((ROOT / "configs/task_registry.json").read_bytes())
    train, dev, held = config["training_tasks"], registry["development"], registry["held_out"]
    if (len(train) != 6 or set(map(family_of, train)) != set(RECIPES)
            or any(not t.startswith("json_2.1.1/train/") for t in train)
            or len(dev) != 10 or len(held) != 30 or len(set(train + dev + held)) != 46
            or config["replay_action_tokens"] != 1 or config["construction_attempts"] != 1):
        raise ValueError("Unexpected training/evaluation registry or experiment settings")
    if (version("alfworld"), version("textworld")) != (baseline["alfworld"]["version"], baseline["alfworld"]["textworld"]):
        raise ValueError("Use the pinned baseline environment")
    tasks = {"probe": [], "build": train, "pilot": dev[:2], "dev": dev}[args.mode]
    run = ROOT / "logs" / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    dump(run / "manifest.json", {
        "experiment": config["experiment"], "mode": args.mode, "command": sys.argv,
        "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
        "started_utc": datetime.now(timezone.utc).isoformat(), "tasks": tasks,
        "config": config, "baseline_config": baseline,
        "bank_sha256": digest(args.bank) if args.bank else None,
    })
    context = {}
    start = time.perf_counter()
    with (run / "trace.jsonl").open("x", encoding="utf-8", buffering=1) as file:
        def record(event, **fields):
            file.write(json.dumps({"event": event, **context, **fields}, ensure_ascii=False) + "\n")

        try:
            model = AnchorModel(LlamaServer(args.server, baseline["model"], record), config, record)
            if args.mode == "probe":
                snapshot = {"goal": "take the mug from the countertop", "family": "pick_and_place_simple",
                            "history": [], "observation": "You see a mug 1 on countertop 1.", "cards": [],
                            "candidates": ["take mug 1 from countertop 1", "go to fridge 1", "look", "inventory"]}
                step = {"snapshot": snapshot, "prompt": render(snapshot), "action": snapshot["candidates"][0]}
                card = {"hint": "Take the mug now while it is within reach.", "role": "success_maintain"}
                summary = model.probe(step, card)
            elif args.mode == "build":
                summary = build(run, tasks, args.archive, baseline, config, model, record, context)
            else:
                summary = evaluate(tasks, args.bank, baseline, config, model, record, context)
        except (Exception, KeyboardInterrupt) as error:
            record("run_error", error=f"{type(error).__name__}: {error}")
            raise
    dump(run / "summary.json", {**summary, "wall_seconds": time.perf_counter() - start})
    print(f"Evidence: {run.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
