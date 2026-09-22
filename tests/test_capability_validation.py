from __future__ import annotations

import unittest

from fca.capability import CapabilityPriorityEngine, GapEvidence, GapKind


class CapabilityPriorityValidationTests(unittest.TestCase):
    def test_rejects_non_finite_and_invalid_resource_values(self):
        engine = CapabilityPriorityEngine()

        with self.assertRaises(ValueError):
            engine.ingest(
                GapEvidence(
                    "nan",
                    GapKind.REASONING,
                    "gap",
                    True,
                    expected_gain=float("nan"),
                )
            )
        with self.assertRaises(ValueError):
            engine.ingest(
                GapEvidence(
                    "zero-cost",
                    GapKind.REASONING,
                    "gap",
                    True,
                    implementation_cost=0.0,
                )
            )
        with self.assertRaises(ValueError):
            engine.ingest(
                GapEvidence(
                    "negative-risk",
                    GapKind.REASONING,
                    "gap",
                    True,
                    regression_risk=-0.1,
                )
            )

    def test_verified_requires_real_bool(self):
        engine = CapabilityPriorityEngine()
        with self.assertRaises(TypeError):
            engine.ingest(
                GapEvidence(
                    "bool",
                    GapKind.CODE,
                    "gap",
                    "true",
                )
            )

    def test_duplicate_identical_evidence_is_idempotent(self):
        engine = CapabilityPriorityEngine(min_verified=1)
        evidence = GapEvidence(
            "same",
            GapKind.CODE,
            "repair",
            True,
        )
        engine.ingest(evidence)
        engine.ingest(evidence)
        rows = engine.priorities()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 1)

    def test_conflicting_duplicate_key_fails_closed(self):
        engine = CapabilityPriorityEngine(min_verified=1)
        engine.ingest(
            GapEvidence(
                "collision",
                GapKind.CODE,
                "repair",
                True,
            )
        )
        with self.assertRaises(ValueError):
            engine.ingest(
                GapEvidence(
                    "collision",
                    GapKind.REASONING,
                    "different",
                    True,
                )
            )

    def test_unverified_valid_evidence_does_not_enter_priorities(self):
        engine = CapabilityPriorityEngine(min_verified=1)
        engine.ingest(
            GapEvidence(
                "u1",
                GapKind.MEMORY,
                "recall-gap",
                False,
            )
        )
        self.assertEqual(engine.priorities(), [])


if __name__ == "__main__":
    unittest.main()
