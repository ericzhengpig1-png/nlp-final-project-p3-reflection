import hashlib
import json
from contextlib import contextmanager

import textworld
from alfworld.agents.environment.alfred_tw_env import AlfredDemangler, AlfredInfos


@contextmanager
def open_game(game_file):
    """Start one explicit game with the upstream ALFWorld evaluation wrappers."""
    infos = textworld.EnvInfos(won=True, facts=True, objective=True,
                               admissible_commands=True, extras=["gamefile"])
    env = textworld.start(str(game_file), infos, wrappers=[AlfredDemangler, AlfredInfos])
    try:
        yield env
    finally:
        env.close()


def state_digest(state):
    facts = state["facts"]
    if facts is None:
        raise RuntimeError("TextWorld did not return state facts for the reset audit")
    payload = json.dumps({"facts": sorted(str(fact) for fact in facts),
                          "observation": state.feedback, "won": state.won}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def policy_observation(observation):
    if observation.startswith("You arrive at loc "):
        return observation.partition(". ")[2]
    return observation


def task_instruction(state):
    return state.feedback.split("Your task is to:", 1)[1].strip()


def textworld_command(action):
    # Reflexion's examples use the older ALFWorld placement verb.
    if action.startswith("put ") and " in/on " in action:
        item, target = action[4:].split(" in/on ", 1)
        return f"move {item} to {target}"
    return action
