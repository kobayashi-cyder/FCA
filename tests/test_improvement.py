import unittest

from fca import CandidateLifecycle, CandidateState, Evidence, FailureMemory, FailureRecord


class ImprovementTests(unittest.TestCase):
    def test_evidence_is_duplicate_safe(self):
        c = CandidateLifecycle(shadow_after=2, consolidate_after=3)
        c.add(Evidence("a", True, 0.1, 1.0))
        c.add(Evidence("a", True, 0.1, 1.0))
        self.assertEqual(c.state, CandidateState.EPHEMERAL)

    def test_lifecycle(self):
        c = CandidateLifecycle(shadow_after=2, consolidate_after=3)
        self.assertEqual(c.add(Evidence("a", True, 0.1, 1.0)), CandidateState.EPHEMERAL)
        self.assertEqual(c.add(Evidence("b", True, 0.1, 1.0)), CandidateState.SHADOW)
        self.assertEqual(c.add(Evidence("c", True, 0.1, 1.0)), CandidateState.CONSOLIDATED)

    def test_regression_quarantines(self):
        c = CandidateLifecycle()
        self.assertEqual(c.add(Evidence("bad", False)), CandidateState.QUARANTINED)

    def test_failure_memory_uses_verified_failures(self):
        fm = FailureMemory()
        fm.record(FailureRecord("REASONING_GAP", "x", True))
        fm.record(FailureRecord("REASONING_GAP", "x", False))
        self.assertEqual(fm.priorities(), [("REASONING_GAP", "x", 1)])


if __name__ == "__main__":
    unittest.main()
