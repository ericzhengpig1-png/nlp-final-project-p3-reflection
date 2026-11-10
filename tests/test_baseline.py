import json
import unittest

from scripts.run_baseline import ROOT, reflexion_assets, run_task


class ScriptedModel:
    def __init__(self, actions):
        self.actions = actions
        self.calls = []

    def generate(self, prompt, kind, seed, **context):
        self.calls.append((kind, seed, prompt))
        return "Find and carry the book again after reset." if kind == "reflection" else self.actions(context)


class BaselineProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/baseline.json").read_bytes())
        task_id = json.loads((ROOT / "configs/task_registry.json").read_bytes())["development"][0]
        cls.game = ROOT / "data/alfworld" / task_id / "game.tw-pddl"
        cls.assets = reflexion_assets(cls.config)

    def run_condition(self, condition, model, resets):
        trace = []
        results = run_task(self.game, condition, self.config, self.assets, model,
                           lambda event, **fields: trace.append((event, fields)), resets)
        return results, trace

    def test_cap_reset_and_reflection(self):
        def actions(context):
            turn = context["policy_turn"]
            if turn <= 2:
                return ("go to bed 1", "take book 1 from bed 1")[turn - 1]
            return ("inventory", "look")[turn % 2]

        resets = {}
        models = {condition: ScriptedModel(actions) for condition in ("A", "B")}
        for condition, model in models.items():
            with self.subTest(condition=condition):
                results, trace = self.run_condition(condition, model, resets)
                self.assertEqual(results, [False, False, False])
                ends = [fields for event, fields in trace if event == "attempt_end"]
                self.assertEqual([(e["reason"], e["env_actions"]) for e in ends], [("env_action_cap", 30)] * 3)
                starts = [fields for event, fields in trace if event == "reset"]
                self.assertEqual(len({s["initial_state_sha256"] for s in starts}), 1)
                first_pickup = [fields for event, fields in trace if event == "environment_step"][1]
                self.assertIn("You pick up the book 1", first_pickup["observation"])
                self.assertNotEqual(first_pickup["state_sha256"], starts[1]["initial_state_sha256"])
                reflection_count = 2 if condition == "B" else 0
                self.assertEqual(sum(event == "reflection" for event, _ in trace), reflection_count)
                self.assertEqual(len(starts[-1]["memory"]), reflection_count)
        self.assertEqual(models["A"].calls[:30], models["B"].calls[:30])
        self.assertIn("Find and carry the book again after reset.", models["B"].calls[31][2])

    def test_success_stops_immediately(self):
        actions = iter(["think: I should find a book.", *(ROOT / "configs/tutorial_actions.txt").read_text().splitlines()])
        model = ScriptedModel(lambda context: next(actions))
        results, trace = self.run_condition("B", model, {})
        self.assertEqual(results, [True])
        self.assertEqual(len(model.calls), 5)
        self.assertEqual(sum(event == "environment_step" for event, _ in trace), 4)
        self.assertEqual(trace[-1][1]["reason"], "won")
        self.assertFalse(any(event == "reflection" for event, _ in trace))


if __name__ == "__main__":
    unittest.main()
