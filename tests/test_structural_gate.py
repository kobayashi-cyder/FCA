from __future__ import annotations

import unittest

from fca.canary import CanaryObservation
from fca.improvement import CandidateState
from fca.structural_gate import StructuralEvidence, StructuralImprovementGate


class StructuralImprovementGateTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64

    def evidence(self, key, scope, **kwargs):
        return StructuralEvidence(
            key=key,
            candidate_digest=self.digest,
            scope=scope,
            passed=kwargs.get("passed", True),
            quality_delta=kwargs.get("quality_delta", 0.0),
            latency_ratio=kwargs.get("latency_ratio", 1.0),
            memory_ratio=kwargs.get("memory_ratio", 1.0),
        )

    def test_requires_independent_sandbox_and_holdout_evidence(self):
        gate = StructuralImprovementGate(self.digest, min_sandbox=2, min_holdout=2)
        self.assertEqual(gate.add_evidence(self.evidence("s1", "sandbox")), CandidateState.EPHEMERAL)
        self.assertEqual(gate.add_evidence(self.evidence("s2", "sandbox")), CandidateState.EPHEMERAL)
        self.assertFalse(gate.canary_ready)
        self.assertEqual(gate.add_evidence(self.evidence("h1", "holdout")), CandidateState.EPHEMERAL)
        self.assertEqual(gate.add_evidence(self.evidence("h2", "holdout")), CandidateState.SHADOW)
        self.assertTrue(gate.canary_ready)
        self.assertEqual(gate.evidence_counts, {"holdout": 2, "sandbox": 2})

    def test_duplicate_evidence_does_not_advance_counts(self):
        gate = StructuralImprovementGate(self.digest, min_sandbox=1, min_holdout=2)
        gate.add_evidence(self.evidence("s1", "sandbox"))
        gate.add_evidence(self.evidence("h1", "holdout"))
        gate.add_evidence(self.evidence("h1", "holdout"))
        self.assertEqual(gate.evidence_counts["holdout"], 1)
        self.assertEqual(gate.state, CandidateState.EPHEMERAL)

    def test_failure_or_resource_regression_quarantines(self):
        gate = StructuralImprovementGate(self.digest, min_sandbox=1, min_holdout=1)
        state = gate.add_evidence(self.evidence("s1", "sandbox", memory_ratio=1.5))
        self.assertEqual(state, CandidateState.QUARANTINED)
        self.assertEqual(gate.add_evidence(self.evidence("h1", "holdout")), CandidateState.QUARANTINED)

    def test_non_finite_evidence_and_canary_fail_closed(self):
        gate = StructuralImprovementGate(self.digest, min_sandbox=1, min_holdout=1)
        state = gate.add_evidence(
            self.evidence("s1", "sandbox", latency_ratio=float("nan"))
        )
        self.assertEqual(state, CandidateState.QUARANTINED)

        gate = StructuralImprovementGate(
            self.digest,
            min_sandbox=1,
            min_holdout=1,
            canary_min_evidence=1,
        )
        gate.add_evidence(self.evidence("s1", "sandbox"))
        gate.add_evidence(self.evidence("h1", "holdout"))
        status = gate.add_canary(
            CanaryObservation("c1", self.digest, True, 0.0, float("nan"))
        )
        self.assertEqual(status, "rollback")
        self.assertEqual(gate.state, CandidateState.QUARANTINED)

    def test_canary_is_blocked_before_shadow(self):
        gate = StructuralImprovementGate(self.digest, min_sandbox=1, min_holdout=1, canary_min_evidence=1)
        with self.assertRaises(RuntimeError):
            gate.add_canary(CanaryObservation("c1", self.digest, True, 0.0, 1.0))

    def test_shadow_advances_through_canary_to_consolidated(self):
        gate = StructuralImprovementGate(
            self.digest,
            min_sandbox=1,
            min_holdout=1,
            canary_min_evidence=1,
            canary_min_success_rate=1.0,
        )
        gate.add_evidence(self.evidence("s1", "sandbox"))
        gate.add_evidence(self.evidence("h1", "holdout"))
        self.assertEqual(gate.state, CandidateState.SHADOW)

        self.assertEqual(gate.add_canary(CanaryObservation("c1", self.digest, True, 0.0, 1.0)), "advanced")
        self.assertEqual(gate.canary_stage, 0.20)
        self.assertEqual(gate.add_canary(CanaryObservation("c2", self.digest, True, 0.0, 1.0)), "advanced")
        self.assertEqual(gate.canary_stage, 0.50)
        self.assertEqual(gate.add_canary(CanaryObservation("c3", self.digest, True, 0.0, 1.0)), "advanced")
        self.assertEqual(gate.canary_stage, 1.00)
        self.assertEqual(gate.add_canary(CanaryObservation("c4", self.digest, True, 0.0, 1.0)), "complete")
        self.assertEqual(gate.state, CandidateState.CONSOLIDATED)

    def test_canary_regression_quarantines(self):
        gate = StructuralImprovementGate(
            self.digest,
            min_sandbox=1,
            min_holdout=1,
            canary_min_evidence=1,
            canary_min_success_rate=1.0,
        )
        gate.add_evidence(self.evidence("s1", "sandbox"))
        gate.add_evidence(self.evidence("h1", "holdout"))
        status = gate.add_canary(CanaryObservation("c1", self.digest, False, -0.1, 1.0))
        self.assertEqual(status, "rollback")
        self.assertEqual(gate.state, CandidateState.QUARANTINED)

    def test_passed_requires_real_bool(self):
        gate = StructuralImprovementGate(self.digest)
        evidence = StructuralEvidence("x", self.digest, "sandbox", "false")
        with self.assertRaises(TypeError):
            gate.add_evidence(evidence)

    def test_digest_and_scope_are_fail_closed(self):
        gate = StructuralImprovementGate(self.digest)
        with self.assertRaises(ValueError):
            gate.add_evidence(StructuralEvidence("x", "b" * 64, "sandbox", True))
        with self.assertRaises(ValueError):
            gate.add_evidence(StructuralEvidence("x", self.digest, "training", True))


if __name__ == "__main__":
    unittest.main()
