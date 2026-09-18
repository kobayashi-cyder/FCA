import unittest

from fca import (
    CanaryObservation,
    CapabilityPriorityEngine,
    GapEvidence,
    GapKind,
    ProvenanceChain,
    StagedCanary,
)


class ControlPlaneTests(unittest.TestCase):
    def test_priority_requires_repeated_verified_evidence(self):
        p = CapabilityPriorityEngine(min_verified=2)
        p.ingest(GapEvidence("1", GapKind.REASONING, "multi_step", True))
        p.ingest(GapEvidence("2", GapKind.REASONING, "multi_step", False))
        self.assertEqual(p.priorities(), [])
        p.ingest(GapEvidence("3", GapKind.REASONING, "multi_step", True))
        rows = p.priorities()
        self.assertEqual(rows[0][0], GapKind.REASONING)
        self.assertEqual(rows[0][2], 2)

    def test_canary_evidence_is_stage_isolated(self):
        c = StagedCanary("abc", min_evidence=2, min_success_rate=1.0)
        self.assertEqual(c.add(CanaryObservation("a", "abc", True, 0.1, 1.0)), "monitoring")
        self.assertEqual(c.add(CanaryObservation("b", "abc", True, 0.1, 1.0)), "advanced")
        self.assertEqual(c.stage, 0.20)
        self.assertEqual(c.evaluate(), "monitoring")

    def test_canary_rolls_back_regression(self):
        c = StagedCanary("abc", min_evidence=2, min_success_rate=1.0)
        c.add(CanaryObservation("a", "abc", True, 0.0, 1.0))
        status = c.add(CanaryObservation("b", "abc", False, 0.0, 1.0))
        self.assertEqual(status, "rollback")

    def test_provenance_chain_detects_tampering(self):
        p = ProvenanceChain()
        p.append("candidate", {"digest": "a"})
        p.append("evidence", {"passed": True})
        self.assertTrue(p.verify())
        object.__setattr__(p.events[0], "event_hash", "f" * 64)
        self.assertFalse(p.verify())


if __name__ == "__main__":
    unittest.main()
