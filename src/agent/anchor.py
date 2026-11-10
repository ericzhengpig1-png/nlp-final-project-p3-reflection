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

HEADS = ("go to", "open", "close", "take", "move", "clean", "heat", "cool",
         "use", "examine", "look", "inventory", "help")


def action_head(command):
    return "go to" if command.startswith("go to ") else command.split()[0]


def render(snapshot, hint=None):
    history = "\n".join(f'{s["action"]} -> {s["feedback"][:260]}' for s in snapshot["history"])
    cards = "\n".join(f'- {card["hint"]}' for card in snapshot["cards"]) or "(none)"
    extra = "" if hint is None else f"\nCandidate guidance:\n{hint}"
    return (
        "Complete the household goal. Choose exactly one listed command. "
        "Use observations to track what you hold and what you have finished. "
        "Avoid revisiting locations without a reason. Continue after <action> with the command only.\n"
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

    def localize(self, goal, steps, won, seed):
        if not steps:
            return []
        count = min(len(steps), 20)
        selected = [steps[i * (len(steps) - 1) // max(count - 1, 1)] for i in range(count)]
        evidence = [{
            "step": s["step"], "observation": s["snapshot"]["observation"][:350],
            "legal_heads": sorted({action_head(a) for a in s["snapshot"]["candidates"]}),
            "action": s["action"], "feedback": s["feedback"][:240],
        } for s in selected]
        schema = {"type": "object", "properties": {"notes": {
            "type": "array", "minItems": 0, "maxItems": self.config["localizer_max_cards"],
            "items": {"type": "object", "properties": {
                "step": {"type": "integer", "enum": [s["step"] for s in selected]},
                "role": {"enum": ["success_maintain", "failure_correction"]},
                "cue": {"type": "string"}, "recommend": {"enum": list(HEADS)},
                "hint": {"type": "string"},
            }, "required": ["step", "role", "cue", "recommend", "hint"],
                "additionalProperties": False},
        }}, "required": ["notes"], "additionalProperties": False}
        instruction = (
            "Review the following game trajectory. Identify up to five important local decisions. "
            "Include both a helpful move to keep and an unhelpful move to correct when supported "
            "by feedback, even if the episode failed. Exclude uncertain decisions. "
            "For each, write a short concrete one-action English hint. "
            "State when it applies in cue; recommend must be an available action head at that step. "
            "For success_maintain reinforce the observed action. For failure_correction tell "
            "what to avoid and give an immediate alternative. Use generic object names where "
            "possible so the note can transfer. Use only the observations available by that step "
            "to describe its situation. Return a JSON object with the notes array.\n"
            f"Goal: {goal}\nEpisode success: {won}\nTrajectory: {json.dumps(evidence)}"
        )
        prompt = self.server.request("/apply-template", {
            "messages": [{"role": "user", "content": instruction}],
        })["prompt"]
        self.record("localizer_prompt", prompt=prompt, selected_steps=[s["step"] for s in selected])
        response = self.complete(prompt, "localizer", json_schema=schema, temperature=0.0, seed=seed,
                                 n_predict=self.config["localizer_tokens"])
        return json.loads(response["content"])["notes"]
