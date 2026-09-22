from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import math

from .canary import CanaryObservation
from .improvement import CandidateState
from .structural_controller import StructuralCandidateEvaluation


@dataclass(frozen=True)
class StructuralCanaryMeasurement:
    key: str
    success: bool
    quality_delta: float = 0.0
    latency_ratio: float = 1.0


StructuralCanaryEvaluator = Callable[
    [str, float],
    Iterable[StructuralCanaryMeasurement],
]


@dataclass(frozen=True)
class StructuralCanaryStep:
    state: CandidateState
    status: str
    reason: str
    stage_before: float
    stage_after: float
    observations: int


class StructuralCanaryController:
    """Advance at most one staged-canary level per explicit invocation."""

    def __init__(self, *, max_observations_per_stage: int = 64) -> None:
        if not 1 <= int(max_observations_per_stage) <= 1024:
            raise ValueError("max_observations_per_stage must be in [1, 1024]")
        self.max_observations_per_stage = int(max_observations_per_stage)

    def advance_one_stage(
        self,
        evaluation: StructuralCandidateEvaluation,
        evaluator: StructuralCanaryEvaluator,
    ) -> StructuralCanaryStep:
        if not isinstance(evaluation, StructuralCandidateEvaluation):
            raise TypeError("evaluation must be StructuralCandidateEvaluation")
        gate = evaluation.gate
        if evaluation.candidate_digest != gate.candidate_digest:
            raise ValueError("candidate digest mismatch")

        stage_before = gate.canary_stage
        if gate.state == CandidateState.QUARANTINED:
            return StructuralCanaryStep(
                state=gate.state,
                status="rollback",
                reason="candidate_quarantined",
                stage_before=stage_before,
                stage_after=gate.canary_stage,
                observations=0,
            )
        if gate.state == CandidateState.CONSOLIDATED:
            return StructuralCanaryStep(
                state=gate.state,
                status="complete",
                reason="candidate_already_consolidated",
                stage_before=stage_before,
                stage_after=gate.canary_stage,
                observations=0,
            )
        if gate.state != CandidateState.SHADOW:
            return StructuralCanaryStep(
                state=gate.state,
                status="blocked",
                reason="candidate_not_ready_for_canary",
                stage_before=stage_before,
                stage_after=gate.canary_stage,
                observations=0,
            )
        if not callable(evaluator):
            return StructuralCanaryStep(
                state=gate.state,
                status="blocked",
                reason="canary_evaluator_not_callable",
                stage_before=stage_before,
                stage_after=gate.canary_stage,
                observations=0,
            )

        try:
            rows = evaluator(gate.candidate_digest, stage_before)
            iterator = iter(rows)
        except Exception as exc:
            return StructuralCanaryStep(
                state=gate.state,
                status="blocked",
                reason=f"canary_provider_failed:{type(exc).__name__}",
                stage_before=stage_before,
                stage_after=gate.canary_stage,
                observations=0,
            )

        observations = 0
        try:
            for index, measurement in enumerate(iterator):
                if index >= self.max_observations_per_stage:
                    return StructuralCanaryStep(
                        state=gate.state,
                        status="blocked",
                        reason="canary_evidence_limit_exceeded",
                        stage_before=stage_before,
                        stage_after=gate.canary_stage,
                        observations=observations,
                    )
                self._validate_measurement(measurement)
                observations += 1
                key = f"canary:{stage_before:.2f}:{measurement.key}"
                status = gate.add_canary(
                    CanaryObservation(
                        key=key,
                        candidate_digest=gate.candidate_digest,
                        success=measurement.success,
                        quality_delta=float(measurement.quality_delta),
                        latency_ratio=float(measurement.latency_ratio),
                    )
                )
                if status == "rollback":
                    return StructuralCanaryStep(
                        state=gate.state,
                        status=status,
                        reason="canary_regression",
                        stage_before=stage_before,
                        stage_after=gate.canary_stage,
                        observations=observations,
                    )
                if status == "complete":
                    return StructuralCanaryStep(
                        state=gate.state,
                        status=status,
                        reason="canary_complete",
                        stage_before=stage_before,
                        stage_after=gate.canary_stage,
                        observations=observations,
                    )
                if status == "advanced":
                    return StructuralCanaryStep(
                        state=gate.state,
                        status=status,
                        reason="canary_stage_advanced",
                        stage_before=stage_before,
                        stage_after=gate.canary_stage,
                        observations=observations,
                    )
        except Exception as exc:
            return StructuralCanaryStep(
                state=gate.state,
                status="blocked",
                reason=f"canary_measurement_rejected:{type(exc).__name__}",
                stage_before=stage_before,
                stage_after=gate.canary_stage,
                observations=observations,
            )

        return StructuralCanaryStep(
            state=gate.state,
            status="monitoring",
            reason="canary_more_evidence_required",
            stage_before=stage_before,
            stage_after=gate.canary_stage,
            observations=observations,
        )

    @staticmethod
    def _validate_measurement(measurement: StructuralCanaryMeasurement) -> None:
        if not isinstance(measurement, StructuralCanaryMeasurement):
            raise TypeError("canary evaluator must return StructuralCanaryMeasurement")
        key = str(measurement.key or "").strip()
        if not key or len(key) > 256:
            raise ValueError("canary measurement key must be 1..256 characters")
        if not isinstance(measurement.success, bool):
            raise TypeError("canary success must be bool")
        quality = float(measurement.quality_delta)
        latency = float(measurement.latency_ratio)
        if not math.isfinite(quality) or not math.isfinite(latency) or latency <= 0.0:
            raise ValueError("canary measurements must be finite with positive latency")
