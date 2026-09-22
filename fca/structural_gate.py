from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .canary import CanaryObservation, StagedCanary
from .improvement import CandidateState


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SCOPES = frozenset({"sandbox", "holdout"})


@dataclass(frozen=True)
class StructuralEvidence:
    key: str
    candidate_digest: str
    scope: str
    passed: bool
    quality_delta: float = 0.0
    latency_ratio: float = 1.0
    memory_ratio: float = 1.0


class StructuralImprovementGate:
    """Evidence-isolated sandbox/holdout gate before staged canary rollout."""

    def __init__(
        self,
        candidate_digest: str,
        *,
        min_sandbox: int = 2,
        min_holdout: int = 2,
        min_quality_delta: float = 0.0,
        max_latency_ratio: float = 1.25,
        max_memory_ratio: float = 1.25,
        canary_min_evidence: int = 4,
        canary_min_success_rate: float = 0.95,
    ) -> None:
        digest = str(candidate_digest or "").strip().lower()
        if not _HEX64.fullmatch(digest):
            raise ValueError("candidate_digest must be a lowercase SHA-256")
        if min_sandbox < 1 or min_holdout < 1:
            raise ValueError("sandbox/holdout evidence requirements must be positive")
        if max_latency_ratio <= 0.0 or max_memory_ratio <= 0.0:
            raise ValueError("resource ratios must be positive")

        self.candidate_digest = digest
        self.min_sandbox = int(min_sandbox)
        self.min_holdout = int(min_holdout)
        self.min_quality_delta = float(min_quality_delta)
        self.max_latency_ratio = float(max_latency_ratio)
        self.max_memory_ratio = float(max_memory_ratio)
        self.state = CandidateState.EPHEMERAL
        self._evidence: dict[str, StructuralEvidence] = {}
        self._canary = StagedCanary(
            digest,
            min_evidence=int(canary_min_evidence),
            min_success_rate=float(canary_min_success_rate),
            min_quality_delta=self.min_quality_delta,
            max_latency_ratio=self.max_latency_ratio,
        )

    @property
    def evidence_counts(self) -> dict[str, int]:
        return {
            scope: sum(
                1
                for evidence in self._evidence.values()
                if evidence.scope == scope and evidence.passed
            )
            for scope in sorted(_SCOPES)
        }

    @property
    def canary_stage(self) -> float:
        return self._canary.stage

    @property
    def canary_status(self) -> str:
        return self._canary.status

    @property
    def canary_ready(self) -> bool:
        return self.state == CandidateState.SHADOW

    def add_evidence(self, evidence: StructuralEvidence) -> CandidateState:
        if self.state in {CandidateState.QUARANTINED, CandidateState.CONSOLIDATED}:
            return self.state

        key = str(evidence.key or "").strip()
        digest = str(evidence.candidate_digest or "").strip().lower()
        scope = str(evidence.scope or "").strip().lower()
        if not key:
            raise ValueError("evidence key is required")
        if digest != self.candidate_digest:
            raise ValueError("candidate digest mismatch")
        if scope not in _SCOPES:
            raise ValueError("scope must be sandbox or holdout")
        if key in self._evidence:
            return self.state

        quality = float(evidence.quality_delta)
        latency = float(evidence.latency_ratio)
        memory = float(evidence.memory_ratio)
        if (
            not math.isfinite(quality)
            or not math.isfinite(latency)
            or not math.isfinite(memory)
            or latency <= 0.0
            or memory <= 0.0
        ):
            self.state = CandidateState.QUARANTINED
            return self.state

        self._evidence[key] = StructuralEvidence(
            key=key,
            candidate_digest=digest,
            scope=scope,
            passed=bool(evidence.passed),
            quality_delta=quality,
            latency_ratio=latency,
            memory_ratio=memory,
        )

        if (
            not evidence.passed
            or quality < self.min_quality_delta
            or latency > self.max_latency_ratio
            or memory > self.max_memory_ratio
        ):
            self.state = CandidateState.QUARANTINED
            return self.state

        counts = self.evidence_counts
        if (
            counts["sandbox"] >= self.min_sandbox
            and counts["holdout"] >= self.min_holdout
        ):
            self.state = CandidateState.SHADOW
        return self.state

    def add_canary(self, observation: CanaryObservation) -> str:
        if self.state == CandidateState.QUARANTINED:
            return "rollback"
        if self.state == CandidateState.CONSOLIDATED:
            return "complete"
        if self.state != CandidateState.SHADOW:
            raise RuntimeError("candidate is not ready for canary rollout")
        if (
            not math.isfinite(float(observation.quality_delta))
            or not math.isfinite(float(observation.latency_ratio))
            or float(observation.latency_ratio) <= 0.0
        ):
            self.state = CandidateState.QUARANTINED
            return "rollback"

        status = self._canary.add(observation)
        if status == "rollback":
            self.state = CandidateState.QUARANTINED
        elif status == "complete":
            self.state = CandidateState.CONSOLIDATED
        return status
