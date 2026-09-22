from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .improvement import CandidateState
from .structural_gate import StructuralEvidence, StructuralImprovementGate


@dataclass(frozen=True)
class StructuralMeasurement:
    key: str
    passed: bool
    quality_delta: float = 0.0
    latency_ratio: float = 1.0
    memory_ratio: float = 1.0


StructuralEvaluator = Callable[[str], Iterable[StructuralMeasurement]]


@dataclass
class StructuralCandidateEvaluation:
    candidate_digest: str
    state: CandidateState
    reason: str
    sandbox_seen: int
    holdout_seen: int
    gate: StructuralImprovementGate

    @property
    def canary_ready(self) -> bool:
        return self.gate.canary_ready


class StructuralCandidateController:
    """Run separated host evaluators and feed only measurements into FCA gates."""

    def __init__(
        self,
        *,
        min_sandbox: int = 2,
        min_holdout: int = 2,
        max_evidence_per_scope: int = 32,
        min_quality_delta: float = 0.0,
        max_latency_ratio: float = 1.25,
        max_memory_ratio: float = 1.25,
        canary_min_evidence: int = 4,
        canary_min_success_rate: float = 0.95,
    ) -> None:
        if not 1 <= int(max_evidence_per_scope) <= 256:
            raise ValueError("max_evidence_per_scope must be in [1, 256]")
        self.min_sandbox = int(min_sandbox)
        self.min_holdout = int(min_holdout)
        self.max_evidence_per_scope = int(max_evidence_per_scope)
        self.min_quality_delta = float(min_quality_delta)
        self.max_latency_ratio = float(max_latency_ratio)
        self.max_memory_ratio = float(max_memory_ratio)
        self.canary_min_evidence = int(canary_min_evidence)
        self.canary_min_success_rate = float(canary_min_success_rate)

    def evaluate(
        self,
        candidate_digest: str,
        *,
        sandbox: StructuralEvaluator,
        holdout: StructuralEvaluator,
    ) -> StructuralCandidateEvaluation:
        if not callable(sandbox) or not callable(holdout):
            raise TypeError("sandbox and holdout evaluators must be callable")

        gate = StructuralImprovementGate(
            candidate_digest,
            min_sandbox=self.min_sandbox,
            min_holdout=self.min_holdout,
            min_quality_delta=self.min_quality_delta,
            max_latency_ratio=self.max_latency_ratio,
            max_memory_ratio=self.max_memory_ratio,
            canary_min_evidence=self.canary_min_evidence,
            canary_min_success_rate=self.canary_min_success_rate,
        )
        seen = {"sandbox": 0, "holdout": 0}

        for scope, evaluator in (("sandbox", sandbox), ("holdout", holdout)):
            reason = self._run_scope(gate, scope, evaluator, seen)
            if reason:
                return StructuralCandidateEvaluation(
                    candidate_digest=gate.candidate_digest,
                    state=gate.state,
                    reason=reason,
                    sandbox_seen=seen["sandbox"],
                    holdout_seen=seen["holdout"],
                    gate=gate,
                )
            if gate.state == CandidateState.QUARANTINED:
                return StructuralCandidateEvaluation(
                    candidate_digest=gate.candidate_digest,
                    state=gate.state,
                    reason=f"{scope}_evidence_rejected",
                    sandbox_seen=seen["sandbox"],
                    holdout_seen=seen["holdout"],
                    gate=gate,
                )

        reason = (
            "ready_for_canary"
            if gate.state == CandidateState.SHADOW
            else "insufficient_independent_evidence"
        )
        return StructuralCandidateEvaluation(
            candidate_digest=gate.candidate_digest,
            state=gate.state,
            reason=reason,
            sandbox_seen=seen["sandbox"],
            holdout_seen=seen["holdout"],
            gate=gate,
        )

    def _run_scope(
        self,
        gate: StructuralImprovementGate,
        scope: str,
        evaluator: StructuralEvaluator,
        seen: dict[str, int],
    ) -> str:
        try:
            rows = evaluator(gate.candidate_digest)
            iterator = iter(rows)
        except Exception as exc:
            self._provider_failure(gate, scope, type(exc).__name__)
            return f"{scope}_provider_failed:{type(exc).__name__}"

        try:
            for index, measurement in enumerate(iterator):
                if index >= self.max_evidence_per_scope:
                    self._provider_failure(gate, scope, "EvidenceLimitExceeded")
                    return f"{scope}_evidence_limit_exceeded"
                if not isinstance(measurement, StructuralMeasurement):
                    self._provider_failure(gate, scope, "InvalidMeasurementType")
                    return f"{scope}_measurement_rejected:TypeError"
                seen[scope] += 1
                gate.add_evidence(
                    StructuralEvidence(
                        key=f"{scope}:{measurement.key}",
                        candidate_digest=gate.candidate_digest,
                        scope=scope,
                        passed=measurement.passed,
                        quality_delta=measurement.quality_delta,
                        latency_ratio=measurement.latency_ratio,
                        memory_ratio=measurement.memory_ratio,
                    )
                )
                if gate.state == CandidateState.QUARANTINED:
                    return f"{scope}_evidence_rejected"
        except Exception as exc:
            self._provider_failure(gate, scope, type(exc).__name__)
            return f"{scope}_measurement_rejected:{type(exc).__name__}"
        return ""

    @staticmethod
    def _provider_failure(
        gate: StructuralImprovementGate,
        scope: str,
        error_type: str,
    ) -> None:
        if gate.state == CandidateState.QUARANTINED:
            return
        gate.add_evidence(
            StructuralEvidence(
                key=f"{scope}:provider-failure:{error_type}"[:256],
                candidate_digest=gate.candidate_digest,
                scope=scope,
                passed=False,
            )
        )
