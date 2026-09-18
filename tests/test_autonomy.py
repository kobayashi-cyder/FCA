import unittest

from fca import AutonomousLoop, OrganRegistry, OrganResult
from fca.connectome import KenyonLayer


class AutonomyTests(unittest.TestCase):
    def test_loop_runs_until_terminal(self):
        state = {"n": 0}
        reg = OrganRegistry()

        def work(goal, observation):
            state["n"] += 1
            n = state["n"]
            return OrganResult(
                observation=f"step {n}",
                reward=1.0,
                progress=min(1.0, n / 3),
                terminal=n >= 3,
            )

        reg.register("work", work)
        report = AutonomousLoop(reg, max_steps=8).run("finish task")
        self.assertEqual(report.status, "completed")
        self.assertEqual(len(report.steps), 3)
        self.assertEqual(report.progress, 1.0)

    def test_blocker_stops_after_limit(self):
        reg = OrganRegistry()
        reg.register("work", lambda goal, observation: OrganResult("blocked", blocked=True, reason="credential"))
        report = AutonomousLoop(reg, blocker_limit=2).run("finish task")
        self.assertEqual(report.status, "blocked")
        self.assertEqual(len(report.steps), 2)

    def test_budget_exhaustion_is_explicit(self):
        reg = OrganRegistry()
        reg.register("work", lambda goal, observation: OrganResult("not done", progress=0.1))
        report = AutonomousLoop(reg, max_steps=2).run("finish task")
        self.assertEqual(report.status, "budget_exhausted")

    def test_explicit_wiring_supported(self):
        layer = KenyonLayer(input_channels=16, winners=1, wiring=[(0, 1), (2, 3)])
        p = layer.activate([1.0, 1.0] + [0.0] * 14)
        self.assertEqual(p.active, (0,))


if __name__ == "__main__":
    unittest.main()
