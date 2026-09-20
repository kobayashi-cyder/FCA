import unittest

from fca.evidence_promotion import VerifiedExperienceGate


class VerifiedExperienceGateTests(unittest.TestCase):
    def test_three_distinct_verified_successes_consolidate(self):
        gate = VerifiedExperienceGate()
        self.assertEqual(gate.observe(candidate_id="c1", evidence_id="e1", reward=0.8, verified=True).stage, "ephemeral")
        self.assertEqual(gate.observe(candidate_id="c1", evidence_id="e2", reward=0.9, verified=True).stage, "shadow")
        self.assertEqual(gate.observe(candidate_id="c1", evidence_id="e3", reward=0.7, verified=True).stage, "consolidated")
        self.assertTrue(gate.consolidated("c1"))

    def test_duplicate_evidence_cannot_advance_promotion(self):
        gate = VerifiedExperienceGate()
        gate.observe(candidate_id="c1", evidence_id="e1", reward=1.0, verified=True)
        with self.assertRaisesRegex(ValueError, "duplicate evidence"):
            gate.observe(candidate_id="c1", evidence_id="e1", reward=1.0, verified=True)
        self.assertEqual(gate.stage_for("c1"), "ephemeral")

    def test_unverified_or_low_reward_evidence_is_rejected(self):
        gate = VerifiedExperienceGate()
        self.assertEqual(gate.observe(candidate_id="c1", evidence_id="e1", reward=1.0, verified=False).stage, "rejected")
        self.assertEqual(gate.observe(candidate_id="c1", evidence_id="e2", reward=0.69, verified=True).stage, "rejected")
        self.assertFalse(gate.consolidated("c1"))

    def test_evidence_id_is_global_replay_key(self):
        gate = VerifiedExperienceGate()
        gate.observe(candidate_id="a", evidence_id="shared", reward=0.9, verified=True)
        with self.assertRaisesRegex(ValueError, "duplicate evidence"):
            gate.observe(candidate_id="b", evidence_id="shared", reward=0.9, verified=True)

    def test_connectome_is_not_required_or_modified_by_gate(self):
        gate = VerifiedExperienceGate()
        self.assertIsNone(gate.stage_for("missing"))
        self.assertFalse(gate.consolidated("missing"))


if __name__ == "__main__":
    unittest.main()
