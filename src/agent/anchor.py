import json
import math
import re
import time


RECIPES = {
    "pick_and_place_simple": "Find and take the requested item, then place it at the goal receptacle.",
    "pick_clean_then_place_in_recep": "Take the item, clean it at a sinkbasin, then place it.",
    "pick_heat_then_place_in_recep": "Take the item, heat it with the microwave, then place it.",
    "pick_cool_then_place_in_recep": "Take the item, cool it with the fridge, then place it.",
    "look_at_obj_in_light": "Take the requested object and use the desklamp at its location.",
    "pick_two_obj_and_place": "Place two distinct objects of the requested kind in the same receptacle.",
}

def action_head(command):
    return "go to" if command.startswith("go to ") else command.split()[0]


def render(snapshot, hint=None):
    history = "\n".join(f'{s["action"]} -> {s["feedback"][:260]}' for s in snapshot["history"])
    cards = "\n".join(f'- {card["hint"]}' for card in snapshot["cards"]) or "(none)"
    extra = "" if hint is None else f"\nCandidate guidance:\n{hint}"
    return (
        "Complete the household goal. Choose exactly one listed command. "
        "Use observations to track what you hold and what you have finished. "
        "Search visible surfaces for the requested object. Avoid repeating open/close or examine "
        "when it yields no progress. Continue after <action> with the command only.\n"
        f"Example interaction:\n{snapshot.get('demo', '(none)')}\n"
        f"Goal: {snapshot['goal']}\n"
        f"Task guidance: {RECIPES[snapshot['family']]}\n"
        f"Recent actions and feedback:\n{history or '(start)'}\n"
        f"Observation:\n{snapshot['observation']}\n"
        f"Memory evidence:\n{cards}{extra}\n"
        f"Admissible actions: {' | '.join(snapshot['candidates'])}\n"
        "<action>"
    )


def words(text):
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def retrieve(bank, family, observation, commands, config):
    available = {action_head(command) for command in commands}
    current = words(observation)
    matches = []
    for card in bank:
        if card["family"] != family or card["recommend"] not in available:
            continue
        cue = words(card["cue"])
        overlap = len(cue & current) / len(cue | current) if cue | current else 0
        # Family match and feasible action are required. Cue overlap ranks matching cards.
        score = 0.50 + 0.20 + 0.30 * overlap
        if score >= config["retrieval_threshold"]:
            matches.append({"id": card["id"], "hint": card["hint"], "score": score})
    return sorted(matches, key=lambda card: (-card["score"], card["id"]))[:config["retrieval_top_k"]]


def softmax(scores):
    maximum = max(scores.values())
    weights = {key: math.exp(score - maximum) for key, score in scores.items()}
    total = sum(weights.values())
    return {key: weight / total for key, weight in weights.items()}


def admission(before, after, source, role, config):
    js = 0.0
    for key, p in before.items():
        q = after[key]
        middle = (p + q) / 2
        js += (p * math.log2(p / middle) if p else 0) / 2
        js += (q * math.log2(q / middle) if q else 0) / 2
    delta = after[source] - before[source]
    top_before, top_after = max(before, key=before.get), max(after, key=after.get)
    if role == "success_maintain":
        magnitude = js >= config["success_js_bits"]
        direction = top_after == source and delta >= config["success_gain"]
    else:
        magnitude = js >= config["failure_js_bits"]
        direction = delta <= -config["failure_drop"] or top_after != source
    return {"js_bits": js, "source_delta": delta, "top_before": top_before,
            "top_after": top_after, "magnitude_pass": magnitude,
            "direction_pass": direction, "accepted": magnitude and direction}


class AnchorModel:
    def __init__(self, server, config, record):
        self.server = server
        self.config = config
        self.record = record

    def complete(self, prompt, kind, **parameters):
        start = time.perf_counter()
        response = self.server.request("/completion", {
            "prompt": prompt, "cache_prompt": False, **parameters,
        })
        timing = response["timings"]
        self.record("model_call", kind=kind, output=response["content"],
                    input_tokens=response["tokens_evaluated"], output_tokens=response["tokens_predicted"],
                    inference_seconds=(timing["prompt_ms"] + timing["predicted_ms"]) / 1000,
                    wall_seconds=time.perf_counter() - start, stop_type=response["stop_type"],
                    truncated=response["truncated"])
        if response["model"] != self.server.alias or response["truncated"]:
            raise RuntimeError("Unexpected model or context overflow")
        return response

    def choose(self, prompt, commands, seed):
        # Decode a full legal command with the same leading space used in replay.
        grammar = "root ::= " + " | ".join(json.dumps(f" {a}</action>") for a in commands)
        settings = self.server.model
        answer = self.complete(prompt, "action", **settings["sampling"], seed=seed, grammar=grammar,
                               stop=["</action>"], n_predict=settings["action_tokens"])
        return answer["content"].strip()

    def tokenize(self, text):
        return self.server.request("/tokenize", {"content": text, "add_special": True})["tokens"]

    def score(self, tokens, required, kind):
        for limit in (2048, 16384):
            response = self.complete(tokens, kind, n_predict=1, temperature=-1, n_probs=limit,
                                     post_sampling_probs=False, return_tokens=True, ignore_eos=True)
            predictions = response.get("completion_probabilities", [])
            scores = {row["id"]: row["logprob"] for row in predictions[0]["top_logprobs"]} if predictions else {}
            if all(token in scores and math.isfinite(scores[token]) for token in required):
                return {token: scores[token] for token in required}
        raise ValueError("One or more required candidate token scores were absent")

    def probe(self, step, card):
        snapshot = step["snapshot"]
        before, after = step["prompt"], render(snapshot, card["hint"])
        if before != render(snapshot):
            raise ValueError("Saved prompt does not match its decision snapshot")
        base, injected = self.tokenize(before), self.tokenize(after)
        categories = {}
        command_tokens = {}
        for command in snapshot["candidates"]:
            left = self.tokenize(f"{before} {command}</action>")
            right = self.tokenize(f"{after} {command}</action>")
            if left[:len(base)] != base or right[:len(injected)] != injected:
                raise ValueError("Action tokenization crossed the saved prompt boundary")
            token = left[len(base)]
            if right[len(injected)] != token:
                raise ValueError("Candidate token changed under note injection")
            categories.setdefault(token, []).append(command)
            command_tokens[command] = token
        source = command_tokens[step["action"]]
        before_scores = self.score(base, categories, "probe_without_note")
        after_scores = self.score(injected, categories, "probe_with_note")
        p, q = softmax(before_scores), softmax(after_scores)
        return {
            "without_prompt": before, "with_prompt": after,
            "categories": categories, "source_token": source,
            "without_logprob": before_scores, "with_logprob": after_scores,
            "without_probability": p, "with_probability": q,
            **admission(p, q, source, card["role"], self.config),
        }

    def localize(self, goal, steps, won, item, seed):
        observed_item = re.compile(rf"\b{re.escape(item.lower())} \d+\b", re.I)
        good, bad = [], []
        seen = set()
        for step in steps:
            action, feedback = step["action"], step["feedback"]
            head = action_head(action)
            repeated = (action, feedback) in seen
            seen.add((action, feedback))
            if repeated or feedback == "Nothing happens.":
                bad.append(step)
            elif head in ("go to", "open", "take", "move", "clean", "cool", "heat") and observed_item.search(feedback):
                good.append(step)
        if won and steps[-1] not in good:
            good.append(steps[-1])
        limit = self.config["localizer_max_cards"]
        notes = []
        for role, eligible, budget in (
            ("success_maintain", good, limit // 2),
            ("failure_correction", bad, limit - limit // 2),
        ):
            if eligible:
                notes.extend(self.write_hints(goal, steps, won, eligible, budget, role, seed))
        return notes

    def write_hints(self, goal, steps, won, eligible, budget, role, seed):
        selectable = eligible[:9] + eligible[-1:] if len(eligible) > 10 else eligible
        ids = [s["step"] for s in selectable]
        context_steps = {s["step"]: s for s in selectable}
        for i in range(10):
            step = steps[i * (len(steps) - 1) // 9]
            context_steps.setdefault(step["step"], step)
        evidence = [{
            "step": s["step"], "observation": s["snapshot"]["observation"][:350],
            "legal_heads": sorted({action_head(a) for a in s["snapshot"]["candidates"]}),
            "action": s["action"], "feedback": s["feedback"][:240],
        } for _, s in sorted(context_steps.items())]
        schema = {"type": "object", "properties": {"steps": {
            "type": "array", "minItems": 1, "maxItems": min(len(ids), budget),
            "items": {"type": "integer", "enum": ids},
        }}, "required": ["steps"], "additionalProperties": False}
        task = "Choose useful decisions to preserve" if role == "success_maintain" else "Choose mistakes to correct"
        try:
            selection = self.structured(
                f"Review the game trajectory. {task} from {ids}. "
                f"Return up to {budget} distinct consequential step numbers in steps.\n"
                f"Goal: {goal}\nEpisode success: {won}\nTrajectory: {json.dumps(evidence)}",
                schema, "localizer", seed,
            )
        except json.JSONDecodeError as error:
            self.record("extraction_rejected", role=role, reason=str(error))
            return []
        notes = []
        for index in dict.fromkeys(selection["steps"]):
            try:
                notes.append(self.write_hint(goal, context_steps[index], role, seed))
            except json.JSONDecodeError as error:
                self.record("extraction_rejected", role=role, step=index, reason=str(error))
        return notes

    def write_hint(self, goal, step, role, seed):
        source = step["action"]
        success = role == "success_maintain"
        commands = [source] if success else [
            action for action in step["snapshot"]["candidates"]
            if action_head(action) != action_head(source)
        ]
        schema = {"type": "object", "properties": {
            "action": {"enum": commands},
            "cue": {"type": "string", "minLength": 1, "maxLength": 120},
            "guidance": {"type": "string", "minLength": 1, "maxLength": 180},
        }, "required": ["action", "cue", "guidance"], "additionalProperties": False}
        task = ("Reinforce the observed action." if success else
                "Choose one useful alternative from the legal commands. Avoid repeating the recorded action.")
        note = self.structured(
            f"{task} Write a short English cue (under 12 words) and one practical guidance sentence "
            "(under 20 words). Use only evidence in this decision.\n"
            f"Goal: {goal}\nObservation: {step['snapshot']['observation']}\n"
            f"Recorded action: {source}\nFeedback: {step['feedback']}\n"
            f"Legal commands for the advice: {' | '.join(commands)}",
            schema, "hint_writer", seed,
        )
        action = note["action"]
        cue = note["cue"].strip()
        guidance = note["guidance"].strip()
        instruction = f"Prefer {action}." if success else f"Avoid repeating {source}; try {action}."
        return {"step": step["step"], "role": role, "cue": cue, "recommend": action_head(action),
                "hint": f"{guidance} {instruction}".strip()}

    def structured(self, instruction, schema, kind, seed):
        prompt = self.server.request("/apply-template", {
            "messages": [{"role": "user", "content": instruction}],
        })["prompt"]
        self.record("extraction_prompt", kind=kind, prompt=prompt, schema=schema)
        response = self.complete(prompt, kind, json_schema=schema, temperature=0.0, seed=seed,
                                 n_predict=self.config["localizer_tokens"])
        return json.loads(response["content"])
