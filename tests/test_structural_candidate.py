from __future__ import annotations

import unittest

from fca.capability import GapKind
from fca.improvement import CandidateState
from fca.structural_candidate import (
    StructuralCandidateFactory,
    StructuralCandidateProposal,
    StructuralCandidateRequest,
)
from fca.structural_controller import (
    StructuralCandidateController,
    StructuralMeasurement,
)


class StructuralCandidateFactoryTests(unittest.TestCase):
    def setUp(self):
        self.request = StructuralCandidateRequest(
            request_id="gap-001",
            kind=GapKind.REASONING,
            gap_signature_digest="a" * 64,
            evidence_count=4,
            priority_score=2.5,
        )
        self.proposal = StructuralCandidateProposal(
            candidate_digest="b" * 64,
            provider_id="host.generator.v1",
            mechanism_id="bounded_rule_patch",
            provenance_digest="c" * 64,
        )

    def test_accepts_metadata_only_proposal(self):
        result = StructuralCandidateFactory().generate(
            self.request, lambda request: self.proposal
        )
        self.assertEqual(result.state, "generated")
        self.assertEqual(result.reason, "candidate_metadata_accepted")
        self.assertEqual(result.proposal, self.proposal)

    def test_provider_error_is_sanitized(self):
        def provider(_):
            raise RuntimeError("SECRET=/private/provider/path")

        result = StructuralCandidateFactory().generate(self.request, provider)
        self.assertEqual(result.state, "rejected")
        self.assertEqual(result.reason, "candidate_provider_failed:RuntimeError")
        self.assertNotIn("SECRET", result.reason)

    def test_invalid_proposal_type_or_digest_is_rejected(self):
        result = StructuralCandidateFactory().generate(self.request, lambda _: {})
        self.assertEqual(result.state, "rejected")
        self.assertEqual(result.reason, "candidate_proposal_rejected:TypeError")

        bad = StructuralCandidateProposal(
            candidate_digest="not-a-digest",
            provider_id="host.generator.v1",
            mechanism_id="bounded_rule_patch",
            provenance_digest="c" * 64,
        )
        result = StructuralCandidateFactory().generate(self.request, lambda _: bad)
        self.assertEqual(result.state, "rejected")
        self.assertEqual(result.reason, "candidate_proposal_rejected:ValueError")

    def test_invalid_request_blocks_before_provider(self):
        calls = []
        bad = StructuralCandidateRequest(
            request_id="bad request with spaces",
            kind=GapKind.REASONING,
            gap_signature_digest="a" * 64,
            evidence_count=4,
            priority_score=2.5,
        )

        result = StructuralCandidateFactory().generate(
            bad, lambda request: calls.append(request)
        )
        self.assertEqual(result.state, "blocked")
        self.assertEqual(calls, [])

    def test_generate_and_evaluate_reaches_shadow_without_code_payload(self):
        controller = StructuralCandidateController(
            min_sandbox=1,
            min_holdout=1,
        )
        factory = StructuralCandidateFactory()
        run = factory.generate_and_evaluate(
            self.request,
            lambda _: self.proposal,
            controller=controller,
            sandbox=lambda digest: (StructuralMeasurement("s1", True),),
            holdout=lambda digest: (StructuralMeasurement("h1", True),),
        )
        self.assertEqual(run.generation.state, "generated")
        self.assertIsNotNone(run.evaluation)
        self.assertEqual(run.evaluation.state, CandidateState.SHADOW)
        self.assertTrue(run.evaluation.canary_ready)
        rendered = repr(run)
        self.assertNotIn("source_code", rendered)
        self.assertNotIn("diff", rendered)
        self.assertNotIn("replacement", rendered)


if __name__ == "__main__":
    unittest.main()
