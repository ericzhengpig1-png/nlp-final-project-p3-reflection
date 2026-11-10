import unittest

from src.agent.anchor import admission, render, softmax


class AnchorTest(unittest.TestCase):
    def setUp(self):
        self.config = {"success_js_bits": 0.05, "failure_js_bits": 0.12,
                       "success_gain": 0.04, "failure_drop": 0.10}

    def test_success_requires_gain_and_top_rank(self):
        p = softmax({1: 0, 2: 0})
        q = softmax({1: 3, 2: 0})
        self.assertTrue(admission(p, q, 1, "success_maintain", self.config)["accepted"])
        self.assertFalse(admission(p, q, 2, "success_maintain", self.config)["accepted"])
        self.assertFalse(admission(q, q, 1, "success_maintain", self.config)["accepted"])

    def test_failure_can_pass_via_ranking_without_source_drop(self):
        p = {1: 0.10, 2: 0.89, 3: 0.01}
        q = {1: 0.20, 2: 0.05, 3: 0.75}
        result = admission(p, q, 1, "failure_correction", self.config)
        self.assertGreater(result["source_delta"], 0)
        self.assertTrue(result["accepted"])

    def test_replay_inserts_only_the_candidate_hint(self):
        snapshot = {"goal": "put the book on the table", "family": "pick_and_place_simple",
                    "history": [{"action": "go to desk 1", "feedback": "a book 1"}],
                    "observation": "The book is in reach.", "candidates": ["look", "take book 1 from desk 1"],
                    "cards": [{"hint": "an existing note"}]}
        original = render(snapshot)
        injected = render(snapshot, "Take the book when it is within reach.")
        block = "\nCandidate guidance:\nTake the book when it is within reach."
        self.assertEqual(injected.replace(block, "", 1), original)


if __name__ == "__main__":
    unittest.main()
