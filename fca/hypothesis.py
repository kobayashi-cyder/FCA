from __future__ import annotations

from dataclasses import dataclass

from .concepts import ConceptGraph


@dataclass(frozen=True)
class Hypothesis:
    subject: str
    relation: str
    object: str
    confidence: float
    support: int
    contradictions: int
    novelty: float = 0.0
    verification_cost: float = 0.0

    @property
    def score(self) -> float:
        return (
            self.confidence
            + 0.10 * self.support
            + 0.10 * self.novelty
            - 0.20 * self.contradictions
            - 0.05 * self.verification_cost
        )


class HypothesisEngine:
    """Generates explicitly non-factual transitive candidates."""

    def infer_two_hop(self, graph: ConceptGraph, relation: str = "is_a") -> list[Hypothesis]:
        edges = [f for f in graph.edges() if f.relation == relation]
        by_subject: dict[str, list] = {}
        existing = {(f.subject, f.relation, f.object) for f in edges}
        for fact in edges:
            by_subject.setdefault(fact.subject, []).append(fact)

        candidates: dict[tuple[str, str, str], Hypothesis] = {}
        for a in edges:
            for b in by_subject.get(a.object, []):
                key = (a.subject, relation, b.object)
                if key in existing or a.subject == b.object:
                    continue
                confidence = min(a.confidence, b.confidence) * (0.95 if a.verified and b.verified else 0.80)
                conflicts = len(graph.contradictions(a.subject, relation))
                h = Hypothesis(
                    subject=a.subject,
                    relation=relation,
                    object=b.object,
                    confidence=confidence,
                    support=2,
                    contradictions=conflicts,
                    novelty=1.0,
                    verification_cost=1.0,
                )
                old = candidates.get(key)
                if old is None or h.score > old.score:
                    candidates[key] = h
        return sorted(candidates.values(), key=lambda h: (-h.score, h.subject, h.object))


class HypothesisCompetition:
    def __init__(self, max_active: int = 4) -> None:
        if max_active < 1:
            raise ValueError("max_active must be positive")
        self.max_active = max_active

    def select(self, hypotheses: list[Hypothesis]) -> tuple[Hypothesis, ...]:
        return tuple(sorted(hypotheses, key=lambda h: (-h.score, h.subject, h.relation, h.object))[: self.max_active])
