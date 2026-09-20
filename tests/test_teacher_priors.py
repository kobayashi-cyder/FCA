from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
import unittest

from fca import (
    AutonomousLoop,
    ConceptGraph,
    FCAAgent,
    FAPV78CircuitPriors,
    HotColdMemory,
    OrganRegistry,
    OrganResult,
    TeacherAwareFCAAgent,
    TeacherPriorError,
)


class TeacherPriorTests(unittest.TestCase):
    def test_verified_source_counts_and_shadow_boundary(self):
        priors = FAPV78CircuitPriors()
        self.assertEqual(len(priors.circuits), 10)
        self.assertEqual(len(priors.memory_rows), 22)
        self.assertEqual(len(priors.concepts["nodes"]), 28)
        self.assertEqual(len(priors.concepts["edges"]), 27)
        self.assertEqual(
            priors.provenance["source_artifact"]["sha256"],
            "e12f51a37681d3aabb4dd00d320fe1bf31362a7e939e454b4e7abc1f7db66909",
        )
        self.assertTrue(all(row["source"] == "teacher_shadow" for row in priors.memory_rows))

    def test_base_agent_remains_unbiased(self):
        decision = FCAAgent().decide("エラーを切り分ける")
        self.assertEqual(decision.biases, {"respond": 0.0, "inspect": 0.0, "wait": 0.0})

    def test_debugging_prior_biases_inspection_after_sparse_pattern(self):
        agent = TeacherAwareFCAAgent()
        decision = agent.decide("エラーを切り分けて最小再現を作る")
        names = [x.name for x in agent.last_teacher_activations]
        self.assertIn("debugging", names)
        self.assertGreater(decision.biases["inspect"], 0.0)
        self.assertEqual(decision.action, "inspect")
        self.assertEqual(len(decision.pattern.active), 16)

    def test_conversation_repair_biases_response(self):
        agent = TeacherAwareFCAAgent()
        decision = agent.decide("違う、それではなく前の前提を訂正して")
        self.assertIn("conversation_repair", [x.name for x in agent.last_teacher_activations])
        self.assertGreater(decision.biases["respond"], 0.0)
        self.assertEqual(decision.action, "respond")

    def test_reward_plasticity_still_updates_mbon_weights(self):
        agent = TeacherAwareFCAAgent()
        decision = agent.decide("エラーを切り分けて修正する")
        self.assertEqual(decision.action, "inspect")
        before = dict(agent.policy.weights["inspect"])
        agent.reinforce(1.0)
        self.assertNotEqual(before, agent.policy.weights["inspect"])

    def test_seed_shadow_memory_and_unverified_concepts(self):
        priors = FAPV78CircuitPriors()
        memory = HotColdMemory(hot_capacity=32, cold_capacity=64, page_in=8)
        graph = ConceptGraph()
        self.assertEqual(priors.seed_memory(memory), 22)
        self.assertEqual(memory.size, 22)
        self.assertEqual(priors.seed_concepts(graph), 27)
        self.assertEqual(len(graph.edges()), 27)
        self.assertTrue(all(not fact.verified for fact in graph.edges()))
        self.assertTrue(all(fact.source == "FAP:v78:teacher_shadow" for fact in graph.edges()))

    def test_teacher_aware_agent_can_drive_autonomous_loop(self):
        registry = OrganRegistry()
        registry.register("respond", lambda goal, obs: OrganResult(obs + "|respond"))
        registry.register("inspect", lambda goal, obs: OrganResult("inspected", reward=1.0, progress=1.0, terminal=True))
        registry.register("wait", lambda goal, obs: OrganResult(obs + "|wait"))

        agent = TeacherAwareFCAAgent(actions=registry.names)
        loop = AutonomousLoop(registry, max_steps=3, agent=agent)
        report = loop.run("エラーを切り分けて修正する", "例外が発生")
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.steps[0].action, "inspect")

    def test_tampering_fails_closed(self):
        source = Path(__file__).resolve().parents[1] / "fca" / "data" / "fap_v78"
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            for path in source.iterdir():
                shutil.copy2(path, target / path.name)
            circuits_path = target / "teacher_consolidated_circuits.json"
            circuits = json.loads(circuits_path.read_text(encoding="utf-8"))
            circuits["debugging"]["detect"].append("tampered")
            circuits_path.write_text(json.dumps(circuits, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(TeacherPriorError, "digest mismatch"):
                FAPV78CircuitPriors(target)


if __name__ == "__main__":
    unittest.main()
