from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
import re

from .capability import GapKind
from .structural_controller import (
    StructuralCandidateController,
    StructuralCandidateEvaluation,
    StructuralEvaluator,
)


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[0-9A-Za-z_.:-]{1,128}$")


@dataclass(frozen=True)
class StructuralCandidateRequest:
    request_id: str
    kind: GapKind
    gap_signature_digest: str
    evidence_count: int
    priority_score: float


@dataclass(frozen=True)
class StructuralCandidateProposal:
    candidate_digest: str
    provider_id: str
    mechanism_id: str
    provenance_digest: str


StructuralCandidateProvider = Callable[[StructuralCandidateRequest], StructuralCandidateProposal]


@dataclass(frozen=True)
class StructuralGenerationResult:
    state: str
    reason: str
    proposal: StructuralCandidateProposal | None = None


@dataclass(frozen=True)
class StructuralCandidateRun:
    generation: StructuralGenerationResult
    evaluation: StructuralCandidateEvaluation | None = None


class StructuralCandidateFactory:
    """Metadata-only candidate generation boundary for FCA structural changes."""

    def generate(
        self,
        request: StructuralCandidateRequest,
        provider: StructuralCandidateProvider,
    ) -> StructuralGenerationResult:
        try:
            self._validate_request(request)
        except Exception as exc:
            return StructuralGenerationResult(
                state="blocked",
                reason=f"candidate_request_rejected:{type(exc).__name__}",
            )
        if not callable(provider):
            return StructuralGenerationResult(
                state="blocked",
                reason="candidate_provider_not_callable",
            )
        try:
            proposal = provider(request)
        except Exception as exc:
            return StructuralGenerationResult(
                state="rejected",
                reason=f"candidate_provider_failed:{type(exc).__name__}",
            )
        try:
            self._validate_proposal(proposal)
        except Exception as exc:
            return StructuralGenerationResult(
                state="rejected",
                reason=f"candidate_proposal_rejected:{type(exc).__name__}",
            )
        return StructuralGenerationResult(
            state="generated",
            reason="candidate_metadata_accepted",
            proposal=proposal,
        )

    def generate_and_evaluate(
        self,
        request: StructuralCandidateRequest,
        provider: StructuralCandidateProvider,
        *,
        controller: StructuralCandidateController,
        sandbox: StructuralEvaluator,
        holdout: StructuralEvaluator,
    ) -> StructuralCandidateRun:
        generated = self.generate(request, provider)
        if generated.state != "generated" or generated.proposal is None:
            return StructuralCandidateRun(generation=generated, evaluation=None)

        evaluation = controller.evaluate(
            generated.proposal.candidate_digest,
            sandbox=sandbox,
            holdout=holdout,
        )
        return StructuralCandidateRun(generation=generated, evaluation=evaluation)

    @staticmethod
    def _validate_request(request: StructuralCandidateRequest) -> None:
        if not isinstance(request, StructuralCandidateRequest):
            raise TypeError("request must be StructuralCandidateRequest")
        if not _SAFE_ID.fullmatch(request.request_id):
            raise ValueError("invalid request_id")
        if not isinstance(request.kind, GapKind):
            raise TypeError("kind must be GapKind")
        if not _HEX64.fullmatch(str(request.gap_signature_digest).lower()):
            raise ValueError("gap_signature_digest must be SHA-256")
        if isinstance(request.evidence_count, bool) or not isinstance(request.evidence_count, int):
            raise TypeError("evidence_count must be int")
        if not 1 <= request.evidence_count <= 1_000_000:
            raise ValueError("evidence_count out of bounds")
        score = float(request.priority_score)
        if not math.isfinite(score) or score < 0.0:
            raise ValueError("priority_score must be finite and non-negative")

    @staticmethod
    def _validate_proposal(proposal: StructuralCandidateProposal) -> None:
        if not isinstance(proposal, StructuralCandidateProposal):
            raise TypeError("provider must return StructuralCandidateProposal")
        if not _HEX64.fullmatch(str(proposal.candidate_digest).lower()):
            raise ValueError("candidate_digest must be SHA-256")
        if not _SAFE_ID.fullmatch(proposal.provider_id):
            raise ValueError("invalid provider_id")
        if not _SAFE_ID.fullmatch(proposal.mechanism_id):
            raise ValueError("invalid mechanism_id")
        if not _HEX64.fullmatch(str(proposal.provenance_digest).lower()):
            raise ValueError("provenance_digest must be SHA-256")
