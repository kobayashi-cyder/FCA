from __future__ import annotations

import unittest

from fca.improvement import CandidateState
from fca.structural_controller import (
    StructuralCandidateController,
    StructuralMeasurement,
)


class StructuralCandidateControllerTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64

    def test_independent_evaluators_reach_shadow_only(self):
        calls = []

        def sandbox(digest):
            calls.append(("sandbox", digest))
            return (
                StructuralMeasurement("s1", True, 0.0, 1.0, 1.0),
                StructuralMeasurement("s2", True, 0.0, 1.0, 1.0),
            )

        def holdout(digest):
            calls.append(("holdout", digest))
            return (
                StructuralMeasurement("h1", True, 0.0, 1.0, 1.0),
                StructuralMeasurement("h2", True, 0.0, 1.0, 1.0),
            )

        result = StructuralCandidateController().evaluate(
            self.digest, sandbox=sandbox, holdout=holdout
        )
        self.assertEqual(result.state, CandidateState.SHADOW)
        self.assertTrue(result.canary_ready)
        self.assertEqual(result.reason, "ready_for_canary")
        self.assertEqual(result.sandbox_seen, 2)
        self.assertEqual(result.holdout_seen, 2)
        self.assertEqual(calls, [("sandbox", self.digest), ("holdout", self.digest)])

    def test_sandbox_failure_stops_before_holdout(self):
        calls = []

        def sandbox(_):
            calls.append("sandbox")
            return (StructuralMeasurement("s1", False),)

        def holdout(_):
            calls.append("holdout")
            return (StructuralMeasurement("h1", True),)

        result = StructuralCandidateController(min_sandbox=1, min_holdout=1).evaluate(
            self.digest, sandbox=sandbox, holdout=holdout
        )
        self.assertEqual(result.state, CandidateState.QUARANTINED)
        self.assertEqual(result.reason, "sandbox_evidence_rejected")
        self.assertEqual(calls, ["sandbox"])

    def test_provider_exception_is_sanitized(self):
        def sandbox(_):
            raise RuntimeError("SECRET=/private/path")

        result = StructuralCandidateController(min_sandbox=1, min_holdout=1).evaluate(
            self.digest, sandbox=sandbox, holdout=lambda _: ()
        )
        self.assertEqual(result.state, CandidateState.QUARANTINED)
        self.assertEqual(result.reason, "sandbox_provider_failed:RuntimeError")
        self.assertNotIn("SECRET", result.reason)
        self.assertNotIn("private", result.reason)

    def test_evidence_limit_fails_closed(self):
        def sandbox(_):
            return tuple(StructuralMeasurement(f"s{i}", True) for i in range(3))

        result = StructuralCandidateController(
            min_sandbox=1, min_holdout=1, max_evidence_per_scope=2
        ).evaluate(self.digest, sandbox=sandbox, holdout=lambda _: ())
        self.assertEqual(result.state, CandidateState.QUARANTINED)
        self.assertEqual(result.reason, "sandbox_evidence_limit_exceeded")

    def test_invalid_measurement_type_fails_closed(self):
        result = StructuralCandidateController(min_sandbox=1, min_holdout=1).evaluate(
            self.digest,
            sandbox=lambda _: ({"key": "s1", "passed": True},),
            holdout=lambda _: (),
        )
        self.assertEqual(result.state, CandidateState.QUARANTINED)
        self.assertEqual(result.reason, "sandbox_measurement_rejected:TypeError")

    def test_insufficient_evidence_stays_ephemeral(self):
        result = StructuralCandidateController(min_sandbox=2, min_holdout=2).evaluate(
            self.digest,
            sandbox=lambda _: (StructuralMeasurement("s1", True),),
            holdout=lambda _: (StructuralMeasurement("h1", True),),
        )
        self.assertEqual(result.state, CandidateState.EPHEMERAL)
        self.assertFalse(result.canary_ready)
        self.assertEqual(result.reason, "insufficient_independent_evidence")


if __name__ == "__main__":
    unittest.main()
