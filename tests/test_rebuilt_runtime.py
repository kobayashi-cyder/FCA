import unittest

from fca.lazy_organs import LazyOrganRegistry
from fca.organs import OrganResult
from fca.rebuilt_runtime import (
    FCARebuiltRuntime,
    VerificationIssue,
    VerificationResult,
)


class RebuiltRuntimeTests(unittest.TestCase):
    def test_sparse_select_load_verify_reinforce_cycle(self):
        registry = LazyOrganRegistry()
        registry.register(
            "inspect",
            lambda: (
                lambda goal, observation: OrganResult(
                    observation="candidate",
                    reward=1.0,
                    progress=0.25,
                )
            ),
        )
        registry.register(
            "respond",
            lambda: (
                lambda goal, observation: OrganResult(
                    observation="unused",
                    reward=1.0,
                )
            ),
        )

        def reject_candidate(goal, decision, result, world):
            return VerificationResult(
                accepted=result.observation != "candidate",
                score=0.0 if result.observation == "candidate" else 1.0,
                issues=(
                    (VerificationIssue("not_verified"),)
                    if result.observation == "candidate"
                    else ()
                ),
            )

        runtime = FCARebuiltRuntime(
            registry,
            verifiers=(reject_candidate,),
            reject_penalty=0.5,
        )
        step = runtime.step("verify result")

        self.assertEqual(step.decision.action, "inspect")
        self.assertEqual(step.loaded_organs, ("inspect",))
        self.assertFalse(step.accepted)
        self.assertEqual(step.effective_reward, -0.5)
        self.assertTrue(
            runtime.world.has(
                "goal",
                "accepted_outcome",
                "outcome:1",
                negative=True,
            )
        )

    def test_integrity_verifier_rejects_invalid_progress(self):
        registry = LazyOrganRegistry()
        registry.register(
            "inspect",
            lambda: (
                lambda goal, observation: OrganResult(
                    observation="bad",
                    reward=0.0,
                    progress=2.0,
                )
            ),
        )
        runtime = FCARebuiltRuntime(registry)
        step = runtime.step("check")
        self.assertFalse(step.accepted)
        codes = {
            issue.code
            for verdict in step.verification
            for issue in verdict.issues
        }
        self.assertIn("progress_out_of_range", codes)


if __name__ == "__main__":
    unittest.main()
