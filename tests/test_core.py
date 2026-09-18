import unittest

from fca import FCAAgent


class CoreTests(unittest.TestCase):
    def test_sparse_pattern_is_bounded(self):
        a = FCAAgent()
        d = a.decide("observe a changing environment")
        self.assertEqual(len(d.pattern.active), 16)
        self.assertEqual(len(set(d.pattern.active)), 16)

    def test_deterministic_first_decision(self):
        a = FCAAgent()
        b = FCAAgent()
        self.assertEqual(a.decide("same input").pattern, b.decide("same input").pattern)

    def test_reward_updates_selected_action(self):
        a = FCAAgent(actions=("left", "right"))
        d = a.decide("cue")
        before = d.scores[d.action]
        a.reinforce(1.0)
        after = a.policy.scores(d.pattern)[d.action]
        self.assertGreaterEqual(after, before)


if __name__ == "__main__":
    unittest.main()
