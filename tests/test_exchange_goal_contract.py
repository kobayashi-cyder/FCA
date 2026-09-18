import unittest

from fca import CriterionAssessment, ExchangeCapsule, GoalContract, GoalCritic


class ExchangeGoalContractTests(unittest.TestCase):
    def test_capsule_seals_and_rejects_tamper(self):
        raw = {
            "schema": "fca-fap.exchange.v1",
            "source_project": "FAP",
            "source_commit": "a" * 40,
            "capability": "goal_loop",
            "mechanism": {"x": 1},
            "evidence": {"tests": "pass"},
            "constraints": ["bounded"],
        }
        sealed = ExchangeCapsule.seal(raw)
        cap = ExchangeCapsule.from_dict(sealed)
        self.assertEqual(cap.capability, "goal_loop")
        sealed["mechanism"]["x"] = 2
        with self.assertRaises(ValueError):
            ExchangeCapsule.from_dict(sealed)

    def test_goal_critic_requires_all_criteria(self):
        contract = GoalContract("finish", ("built", "verified"))
        critic = GoalCritic()
        partial = critic.assess(contract, (CriterionAssessment("built", True, "artifact"),))
        self.assertFalse(partial.satisfied)
        self.assertEqual(partial.progress, 0.5)
        done = critic.assess(
            contract,
            (
                CriterionAssessment("built", True, "artifact"),
                CriterionAssessment("verified", True, "tests"),
            ),
        )
        self.assertTrue(done.satisfied)
        self.assertEqual(done.progress, 1.0)


if __name__ == "__main__":
    unittest.main()
