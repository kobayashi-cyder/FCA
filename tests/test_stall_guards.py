import unittest

from fca import AutonomousLoop, OrganRegistry, OrganResult


class StallGuardTests(unittest.TestCase):
    def test_no_progress_stalls(self):
        reg = OrganRegistry()
        reg.register("work", lambda goal, observation: OrganResult("same", progress=0.0))
        report = AutonomousLoop(reg, max_steps=10, no_progress_limit=2, same_action_limit=10).run("finish")
        self.assertEqual(report.status, "stalled")
        self.assertEqual(len(report.steps), 2)

    def test_progress_prevents_false_stall(self):
        state = {"n": 0}
        reg = OrganRegistry()

        def work(goal, observation):
            state["n"] += 1
            return OrganResult(
                f"step {state['n']}",
                progress=state["n"] / 3,
                terminal=state["n"] >= 3,
            )

        reg.register("work", work)
        report = AutonomousLoop(reg, max_steps=5, no_progress_limit=2, same_action_limit=2).run("finish")
        self.assertEqual(report.status, "completed")
        self.assertEqual(len(report.steps), 3)


if __name__ == "__main__":
    unittest.main()
