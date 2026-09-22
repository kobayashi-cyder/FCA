from __future__ import annotations

from hashlib import sha256
import unittest

from fca.capability import CapabilityPriorityEngine, GapEvidence, GapKind
from fca.improvement import CandidateState
from fca.structural_candidate import StructuralCandidateProposal
from fca.structural_controller import StructuralCandidateController, StructuralMeasurement
from fca.structural_coordinator import StructuralImprovementCoordinator


class StructuralImprovementCoordinatorTests(unittest.TestCase):
    def _engine(self) -> CapabilityPriorityEngine:
        engine = CapabilityPriorityEngine(min_verified=2)
        engine.ingest(
            GapEvidence(
                "e1",
                GapKind.REASONING,
                "multi_step_reasoning_gap",
                True,
                expected_gain=2.0,
            )
        )
        engine.ingest(
            GapEvidence(
                "e2",
                GapKind.REASONING,
                "multi_step_reasoning_gap",
                True,
                expected_gain=2.0,
            )
        )
        return engine

    def _controller(self) -> StructuralCandidateController:
        return StructuralCandidateController(min_sandbox=1, min_holdout=1)

    def _provider(self, captured):
        def provider(request):
            captured.append(request)
            return StructuralCandidateProposal(
                candidate_digest="b" * 64,
                provider_id="host.generator.v1",
                mechanism_id="reasoning_patch",
                provenance_digest="c" * 64,
            )
        return provider

    def test_top_priority_flows_to_shadow_without_raw_signature(self):
        captured = []
        coordinator = StructuralImprovementCoordinator(controller=self._controller())
        result = coordinator.run_top_priority(
            self._engine(),
            self._provider(captured),
            sandbox=lambda digest: (StructuralMeasurement("s1", True),),
            holdout=lambda digest: (StructuralMeasurement("h1", True),),
        )

        self.assertEqual(result.state, CandidateState.SHADOW.value)
        self.assertEqual(result.reason, "ready_for_canary")
        self.assertIsNotNone(result.request)
        self.assertEqual(len(captured), 1)
        request = captured[0]
        self.assertEqual(
            request.gap_signature_digest,
            sha256(b"multi_step_reasoning_gap").hexdigest(),
        )
        rendered = repr(request)
        self.assertNotIn("multi_step_reasoning_gap", rendered)

    def test_no_verified_priority_blocks_without_provider_call(self):
        engine = CapabilityPriorityEngine(min_verified=2)
        calls = []
        result = StructuralImprovementCoordinator().run_top_priority(
            engine,
            lambda request: calls.append(request),
            sandbox=lambda digest: (),
            holdout=lambda digest: (),
        )
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason, "no_verified_priority")
        self.assertEqual(calls, [])

    def test_request_is_deterministic_for_same_priority(self):
        coordinator = StructuralImprovementCoordinator()
        row = self._engine().priorities()[0]
        first = coordinator._request_from_priority(row)
        second = coordinator._request_from_priority(row)
        self.assertEqual(first, second)
        self.assertTrue(first.request_id.startswith("gap:reasoning:"))

    def test_provider_failure_remains_sanitized(self):
        def provider(_):
            raise RuntimeError("SECRET=/private/path")

        result = StructuralImprovementCoordinator(
            controller=self._controller()
        ).run_top_priority(
            self._engine(),
            provider,
            sandbox=lambda digest: (),
            holdout=lambda digest: (),
        )
        self.assertEqual(result.state, "rejected")
        self.assertEqual(result.reason, "candidate_provider_failed:RuntimeError")
        self.assertNotIn("SECRET", result.reason)

    def test_invalid_priority_row_fails_closed(self):
        class BadEngine(CapabilityPriorityEngine):
            def priorities(self):
                return [(GapKind.REASONING, "gap", 2, float("nan"))]

        result = StructuralImprovementCoordinator().run_top_priority(
            BadEngine(),
            lambda request: None,
            sandbox=lambda digest: (),
            holdout=lambda digest: (),
        )
        self.assertEqual(result.state, "blocked")
        self.assertEqual(result.reason, "priority_rejected:ValueError")


if __name__ == "__main__":
    unittest.main()
