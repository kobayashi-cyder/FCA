import tempfile
import unittest

from fca import AutonomousLoop, FCAAgent, JSONGoalCheckpointStore, OrganRegistry, OrganResult


class CheckpointResumeTests(unittest.TestCase):
    def test_agent_snapshot_roundtrip(self):
        a = FCAAgent(actions=("a", "b"))
        d = a.decide("cue")
        a.reinforce(1.0)
        snap = a.snapshot()

        b = FCAAgent(actions=("a", "b"))
        b.restore(snap)
        self.assertEqual(a.trace.state, b.trace.state)
        self.assertEqual(a.policy.weights, b.policy.weights)
        self.assertEqual(a.policy.baseline, b.policy.baseline)

    def test_loop_resumes_after_interruption(self):
        with tempfile.TemporaryDirectory() as td:
            store = JSONGoalCheckpointStore(td)
            reg1 = OrganRegistry()

            def first(goal, observation):
                if not observation:
                    return OrganResult("first done", reward=0.5, progress=0.5)
                raise RuntimeError("simulated interruption")

            reg1.register("work", first)
            loop1 = AutonomousLoop(reg1, max_steps=3, store=store)
            with self.assertRaises(RuntimeError):
                loop1.run("finish", goal_id="g")

            reg2 = OrganRegistry()
            reg2.register(
                "work",
                lambda goal, observation: OrganResult(
                    "second done",
                    reward=1.0,
                    progress=1.0,
                    terminal=(observation == "first done"),
                ),
            )
            loop2 = AutonomousLoop(reg2, max_steps=3, store=store)
            report = loop2.run("finish", goal_id="g", resume=True)
            self.assertEqual(report.status, "completed")
            self.assertEqual(len(report.steps), 2)
            self.assertEqual(report.steps[0].observation, "first done")
            self.assertEqual(report.steps[1].index, 2)


if __name__ == "__main__":
    unittest.main()
