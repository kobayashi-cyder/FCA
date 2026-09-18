from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CandidateState(str, Enum):
    EPHEMERAL = "ephemeral"
    SHADOW = "shadow"
    CONSOLIDATED = "consolidated"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class Evidence:
    key: str
    passed: bool
    quality_delta: float = 0.0
    latency_ratio: float = 1.0


@dataclass
class CandidateLifecycle:
    """FAP-derived verified promotion logic, kept outside the neural core."""

    shadow_after: int = 2
    consolidate_after: int = 4
    max_latency_ratio: float = 1.25
    state: CandidateState = CandidateState.EPHEMERAL
    _evidence: dict[str, Evidence] = field(default_factory=dict)

    def add(self, evidence: Evidence) -> CandidateState:
        if evidence.key in self._evidence:
            return self.state
        self._evidence[evidence.key] = evidence

        if (not evidence.passed) or evidence.quality_delta < 0.0 or evidence.latency_ratio > self.max_latency_ratio:
            self.state = CandidateState.QUARANTINED
            return self.state

        good = sum(1 for e in self._evidence.values() if e.passed and e.quality_delta >= 0.0)
        if good >= self.consolidate_after:
            self.state = CandidateState.CONSOLIDATED
        elif good >= self.shadow_after:
            self.state = CandidateState.SHADOW
        return self.state


@dataclass(frozen=True)
class FailureRecord:
    kind: str
    signature: str
    verified: bool = True


class FailureMemory:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}

    def record(self, failure: FailureRecord) -> None:
        if not failure.verified:
            return
        key = (failure.kind, failure.signature)
        self._counts[key] = self._counts.get(key, 0) + 1

    def priorities(self) -> list[tuple[str, str, int]]:
        rows = [(kind, sig, count) for (kind, sig), count in self._counts.items()]
        return sorted(rows, key=lambda r: (-r[2], r[0], r[1]))
