from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CanaryObservation:
    key: str
    candidate_digest: str
    success: bool
    quality_delta: float
    latency_ratio: float


class StagedCanary:
    """Evidence-isolated 5/20/50/100 rollout controller.

    This is a conservative operational gate, not a statistical superiority test.
    """

    stages = (0.05, 0.20, 0.50, 1.00)

    def __init__(
        self,
        candidate_digest: str,
        *,
        min_evidence: int = 4,
        min_success_rate: float = 0.95,
        min_quality_delta: float = 0.0,
        max_latency_ratio: float = 1.25,
    ) -> None:
        if not candidate_digest or min_evidence < 1:
            raise ValueError("invalid canary configuration")
        self.candidate_digest = candidate_digest
        self.min_evidence = min_evidence
        self.min_success_rate = min_success_rate
        self.min_quality_delta = min_quality_delta
        self.max_latency_ratio = max_latency_ratio
        self.stage_index = 0
        self._evidence: dict[int, dict[str, CanaryObservation]] = {i: {} for i in range(len(self.stages))}
        self.status = "monitoring"

    @property
    def stage(self) -> float:
        return self.stages[self.stage_index]

    def add(self, observation: CanaryObservation) -> str:
        if self.status in {"rollback", "complete"}:
            return self.status
        if observation.candidate_digest != self.candidate_digest:
            raise ValueError("candidate digest mismatch")
        bucket = self._evidence[self.stage_index]
        if observation.key in bucket:
            return self.status
        bucket[observation.key] = observation
        return self.evaluate()

    def evaluate(self) -> str:
        bucket = list(self._evidence[self.stage_index].values())
        if len(bucket) < self.min_evidence:
            self.status = "monitoring"
            return self.status

        success_rate = sum(1 for o in bucket if o.success) / len(bucket)
        quality = sum(o.quality_delta for o in bucket) / len(bucket)
        latency = sorted(o.latency_ratio for o in bucket)
        p95 = latency[min(len(latency) - 1, max(0, ceil(0.95 * len(latency)) - 1))]

        if (
            success_rate < self.min_success_rate
            or quality < self.min_quality_delta
            or p95 > self.max_latency_ratio
        ):
            self.status = "rollback"
            return self.status

        if self.stage_index == len(self.stages) - 1:
            self.status = "complete"
            return self.status

        self.stage_index += 1
        self.status = "monitoring"
        return "advanced"
