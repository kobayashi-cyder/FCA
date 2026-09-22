from __future__ import annotations

import unittest

from fca.improvement import CandidateState
from fca.structural_canary import (
    StructuralCanaryController,
    StructuralCanaryMeasurement,
)
from fca.structural_controller import StructuralCandidateEvaluation
from fca.structural_gate import StructuralEvidence, StructuralImprovementGate


class StructuralCanaryControllerTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64

    def _evaluation(self, *, canary_min_evidence=1):
        gate = StructuralImprovementGate(
            self.digest,
            min_sandbox=1,
            min_holdout=1,
            canary_min_evidence=canary_min_evidence,
            canary_min_success_rate=1.0,
        )
        gate.add_evidence(
            StructuralEvidence("s1", self.digest, "sandbox", True)
        )
        gate.add_evidence(
            StructuralEvidence("h1", self.digest, "holdout", True)
        )
        return StructuralCandidateEvaluation(
            candidate_digest=self.digest,
            state=gate.state,
            reason="ready_for_canary",
            sandbox_seen=1,
            holdout_seen=1,
            gate=gate,
        )

    def test_advances_only_one_stage_per_call(self):
        evaluation = self._evaluation(canary_min_evidence=1)
        controller = StructuralCanaryController()

        def evaluator(digest, stage):
            return tuple(
                StructuralCanaryMeasurement(f"m{i}", True)
                for i in range(10)
            )

        step = controller.advance_one_stage(evaluation, evaluator)
        self.assertEqual(step.status, "advanced")
        self.assertEqual(step.stage_before, 0.05)
        self.assertEqual(step.stage_after, 0.20)
        self.assertEqual(step.observations, 1)
        self.assertEqual(evaluation.gate.state, CandidateState.SHADOW)

    def test_four_explicit_calls_can_complete_rollout(self):
        evaluation = self._evaluation(canary_min_evidence=1)
        controller = StructuralCanaryController()

        def evaluator(digest, stage):
            return (StructuralCanaryMeasurement(f"stage-{stage}", True),)

        statuses = [
            controller.advance_one_stage(evaluation, evaluator).status
            for _ in range(4)
        ]
        self.assertEqual(statuses, ["advanced", "advanced", "advanced", "complete"])
        self.assertEqual(evaluation.gate.state, CandidateState.CONSOLIDATED)

    def test_accumulates_evidence_without_skipping_stage(self):
        evaluation = self._evaluation(canary_min_evidence=2)
        controller = StructuralCanaryController()

        first = controller.advance_one_stage(
            evaluation,
            lambda digest, stage: (StructuralCanaryMeasurement("a", True),),
        )
        self.assertEqual(first.status, "monitoring")
        self.assertEqual(first.stage_after, 0.05)

        second = controller.advance_one_stage(
            evaluation,
            lambda digest, stage: (StructuralCanaryMeasurement("b", True),),
        )
        self.assertEqual(second.status, "advanced")
        self.assertEqual(second.stage_after, 0.20)

    def test_regression_rolls_back_and_quarantines(self):
        evaluation = self._evaluation(canary_min_evidence=1)
        step = StructuralCanaryController().advance_one_stage(
            evaluation,
            lambda digest, stage: (
                StructuralCanaryMeasurement("bad", False, -0.1, 1.0),
            ),
        )
        self.assertEqual(step.status, "rollback")
        self.assertEqual(step.reason, "canary_regression")
        self.assertEqual(evaluation.gate.state, CandidateState.QUARANTINED)

    def test_provider_failure_is_sanitized_and_does_not_mutate_candidate(self):
        evaluation = self._evaluation(canary_min_evidence=1)

        def evaluator(digest, stage):
            raise RuntimeError("SECRET=/private/path")

        step = StructuralCanaryController().advance_one_stage(
            evaluation,
            evaluator,
        )
        self.assertEqual(step.status, "blocked")
        self.assertEqual(step.reason, "canary_provider_failed:RuntimeError")
        self.assertNotIn("SECRET", step.reason)
        self.assertEqual(evaluation.gate.state, CandidateState.SHADOW)
        self.assertEqual(evaluation.gate.canary_stage, 0.05)

    def test_invalid_measurement_blocks_without_advancing(self):
        evaluation = self._evaluation(canary_min_evidence=1)
        step = StructuralCanaryController().advance_one_stage(
            evaluation,
            lambda digest, stage: ({"key": "bad"},),
        )
        self.assertEqual(step.status, "blocked")
        self.assertEqual(step.reason, "canary_measurement_rejected:TypeError")
        self.assertEqual(evaluation.gate.state, CandidateState.SHADOW)
        self.assertEqual(evaluation.gate.canary_stage, 0.05)

    def test_ephemeral_candidate_is_not_runnable(self):
        gate = StructuralImprovementGate(self.digest)
        evaluation = StructuralCandidateEvaluation(
            candidate_digest=self.digest,
            state=gate.state,
            reason="insufficient_independent_evidence",
            sandbox_seen=0,
            holdout_seen=0,
            gate=gate,
        )
        calls = []
        step = StructuralCanaryController().advance_one_stage(
            evaluation,
            lambda digest, stage: calls.append((digest, stage)),
        )
        self.assertEqual(step.status, "blocked")
        self.assertEqual(step.reason, "candidate_not_ready_for_canary")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
