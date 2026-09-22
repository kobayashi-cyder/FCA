from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math

from .capability import CapabilityPriorityEngine, GapKind
from .structural_candidate import (
    StructuralCandidateFactory,
    StructuralCandidateProvider,
    StructuralCandidateRequest,
    StructuralCandidateRun,
)
from .structural_controller import StructuralCandidateController, StructuralEvaluator


@dataclass(frozen=True)
class StructuralImprovementOutcome:
    state: str
    reason: str
    request: StructuralCandidateRequest | None = None
    run: StructuralCandidateRun | None = None


class StructuralImprovementCoordinator:
    """Bridge verified capability priorities into metadata-only candidate evaluation."""

    def __init__(
        self,
        *,
        factory: StructuralCandidateFactory | None = None,
        controller: StructuralCandidateController | None = None,
        max_signature_chars: int = 20_000,
    ) -> None:
        if not 1 <= int(max_signature_chars) <= 100_000:
            raise ValueError("max_signature_chars must be in [1, 100000]")
        self.factory = factory or StructuralCandidateFactory()
        self.controller = controller or StructuralCandidateController()
        self.max_signature_chars = int(max_signature_chars)

    def run_top_priority(
        self,
        engine: CapabilityPriorityEngine,
        provider: StructuralCandidateProvider,
        *,
        sandbox: StructuralEvaluator,
        holdout: StructuralEvaluator,
    ) -> StructuralImprovementOutcome:
        if not isinstance(engine, CapabilityPriorityEngine):
            return StructuralImprovementOutcome("blocked", "invalid_priority_engine")

        rows = engine.priorities()
        if not rows:
            return StructuralImprovementOutcome("blocked", "no_verified_priority")

        try:
            request = self._request_from_priority(rows[0])
        except Exception as exc:
            return StructuralImprovementOutcome(
                "blocked",
                f"priority_rejected:{type(exc).__name__}",
            )

        run = self.factory.generate_and_evaluate(
            request,
            provider,
            controller=self.controller,
            sandbox=sandbox,
            holdout=holdout,
        )
        if run.generation.state != "generated":
            return StructuralImprovementOutcome(
                state=run.generation.state,
                reason=run.generation.reason,
                request=request,
                run=run,
            )
        if run.evaluation is None:
            return StructuralImprovementOutcome(
                state="rejected",
                reason="candidate_evaluation_missing",
                request=request,
                run=run,
            )

        return StructuralImprovementOutcome(
            state=run.evaluation.state.value,
            reason=run.evaluation.reason,
            request=request,
            run=run,
        )

    def _request_from_priority(
        self,
        row: tuple[GapKind, str, int, float],
    ) -> StructuralCandidateRequest:
        if not isinstance(row, tuple) or len(row) != 4:
            raise TypeError("priority row must be a 4-tuple")
        kind, signature, count, score = row
        if not isinstance(kind, GapKind):
            raise TypeError("priority kind must be GapKind")
        if not isinstance(signature, str):
            raise TypeError("priority signature must be str")
        signature = signature.strip()
        if not signature or len(signature) > self.max_signature_chars:
            raise ValueError("priority signature is empty or oversized")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= 1_000_000
        ):
            raise ValueError("priority evidence count is invalid")
        score = float(score)
        if not math.isfinite(score) or score < 0.0:
            raise ValueError("priority score must be finite and non-negative")

        digest = sha256(signature.encode("utf-8")).hexdigest()
        request_id = f"gap:{kind.name.lower()}:{digest[:16]}:{count}"
        return StructuralCandidateRequest(
            request_id=request_id,
            kind=kind,
            gap_signature_digest=digest,
            evidence_count=count,
            priority_score=score,
        )
