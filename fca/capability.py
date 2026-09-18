from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GapKind(str, Enum):
    KNOWLEDGE = "KNOWLEDGE_GAP"
    SEMANTIC = "SEMANTIC_GAP"
    REASONING = "REASONING_GAP"
    LONG_HORIZON = "LONG_HORIZON_GAP"
    MATH = "MATH_GAP"
    CODE = "CODE_GAP"
    VISION = "VISION_GAP"
    IMAGE_GENERATION = "IMAGE_GENERATION_GAP"
    WEB_DESIGN = "WEB_DESIGN_GAP"
    TOOL_USE = "TOOL_USE_GAP"
    MEMORY = "MEMORY_GAP"
    VERIFICATION = "VERIFICATION_GAP"
    LANGUAGE_GENERATION = "LANGUAGE_GENERATION_GAP"
    PLANNING = "PLANNING_GAP"
    UNKNOWN = "UNKNOWN_GAP"


@dataclass(frozen=True)
class GapEvidence:
    key: str
    kind: GapKind
    signature: str
    verified: bool
    generality: float = 1.0
    expected_gain: float = 1.0
    implementation_cost: float = 1.0
    regression_risk: float = 0.0


class CapabilityPriorityEngine:
    """Ranks recurring verified capability gaps without benchmark-specific scoring."""

    def __init__(self, min_verified: int = 2) -> None:
        if min_verified < 1:
            raise ValueError("min_verified must be positive")
        self.min_verified = min_verified
        self._seen: dict[str, GapEvidence] = {}

    def ingest(self, evidence: GapEvidence) -> None:
        if evidence.verified:
            self._seen.setdefault(evidence.key, evidence)

    def priorities(self) -> list[tuple[GapKind, str, int, float]]:
        groups: dict[tuple[GapKind, str], list[GapEvidence]] = {}
        for e in self._seen.values():
            groups.setdefault((e.kind, e.signature), []).append(e)

        rows: list[tuple[GapKind, str, int, float]] = []
        for (kind, signature), evidence in groups.items():
            n = len(evidence)
            if n < self.min_verified:
                continue
            avg_generality = sum(e.generality for e in evidence) / n
            avg_gain = sum(e.expected_gain for e in evidence) / n
            avg_cost = max(1e-9, sum(e.implementation_cost for e in evidence) / n)
            avg_risk = max(0.0, sum(e.regression_risk for e in evidence) / n)
            score = n * avg_generality * avg_gain / (avg_cost * (1.0 + avg_risk))
            rows.append((kind, signature, n, score))
        return sorted(rows, key=lambda r: (-r[3], r[0].value, r[1]))
