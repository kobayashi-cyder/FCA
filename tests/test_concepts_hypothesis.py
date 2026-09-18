import unittest

from fca import ConceptGraph, Fact, HypothesisCompetition, HypothesisEngine


class ConceptHypothesisTests(unittest.TestCase):
    def test_alias_and_contradiction_retention(self):
        g = ConceptGraph()
        g.alias("H2O", "water")
        g.add(Fact("H2O", "state", "liquid", 0.9, True))
        g.add(Fact("water", "state", "solid", 0.7, False))
        self.assertEqual(len(g.contradictions("water", "state")), 2)
        self.assertEqual(g.query("H2O", "state")[0].subject, "water")

    def test_two_hop_is_hypothesis_not_fact(self):
        g = ConceptGraph()
        g.add(Fact("sparrow", "is_a", "bird", 0.95, True))
        g.add(Fact("bird", "is_a", "animal", 0.95, True))
        hs = HypothesisEngine().infer_two_hop(g)
        self.assertEqual((hs[0].subject, hs[0].object), ("sparrow", "animal"))
        self.assertEqual(g.query("sparrow", "is_a")[0].object, "bird")

    def test_competition_is_bounded(self):
        g = ConceptGraph()
        for i in range(6):
            g.add(Fact(f"x{i}", "is_a", f"m{i}", 0.8, True))
            g.add(Fact(f"m{i}", "is_a", "root", 0.8, True))
        hs = HypothesisEngine().infer_two_hop(g)
        selected = HypothesisCompetition(max_active=3).select(hs)
        self.assertEqual(len(selected), 3)


if __name__ == "__main__":
    unittest.main()
