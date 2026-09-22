import unittest

from fca.world_model import WorldGraph


class WorldGraphTests(unittest.TestCase):
    def test_typed_entities_relations_and_negative_constraints(self):
        graph = WorldGraph()
        graph.upsert("goal", "goal")
        graph.upsert("candidate", "outcome", state="rejected")
        graph.relate("goal", "accepted_outcome", "candidate", negative=True)
        self.assertTrue(
            graph.has("goal", "accepted_outcome", "candidate", negative=True)
        )
        self.assertFalse(
            graph.has("goal", "accepted_outcome", "candidate", negative=False)
        )

    def test_relation_requires_existing_endpoints(self):
        graph = WorldGraph()
        graph.upsert("goal", "goal")
        with self.assertRaisesRegex(ValueError, "endpoints"):
            graph.relate("goal", "uses", "missing")


if __name__ == "__main__":
    unittest.main()
