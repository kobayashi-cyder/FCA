from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


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
        self._validate_evidence(evidence)
        existing = self._seen.get(evidence.key)
        if existing is not None:
            if existing != evidence:
                raise ValueError("conflicting duplicate gap evidence key")
            return
        if evidence.verified:
            self._seen[evidence.key] = evidence

    @staticmethod
    def _validate_evidence(evidence: GapEvidence) -> None:
        if not isinstance(evidence, GapEvidence):
            raise TypeError("evidence must be GapEvidence")
        if not isinstance(evidence.key, str) or not 1 <= len(evidence.key.strip()) <= 256:
            raise ValueError("evidence key must be 1..256 characters")
        if not isinstance(evidence.kind, GapKind):
            raise TypeError("evidence kind must be GapKind")
        if (
            not isinstance(evidence.signature, str)
            or not 1 <= len(evidence.signature.strip()) <= 20_000
        ):
            raise ValueError("evidence signature must be 1..20000 characters")
        if not isinstance(evidence.verified, bool):
            raise TypeError("evidence verified must be bool")

        values = (
            ("generality", evidence.generality, 0.0, False),
            ("expected_gain", evidence.expected_gain, 0.0, False),
            ("implementation_cost", evidence.implementation_cost, 0.0, True),
            ("regression_risk", evidence.regression_risk, 0.0, False),
        )
        for name, value, minimum, strictly_positive in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name} must be finite")
            if strictly_positive:
                if number <= minimum:
                    raise ValueError(f"{name} must be positive")
            elif number < minimum:
                raise ValueError(f"{name} must be non-negative")

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
