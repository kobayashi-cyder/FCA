from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    subject: str
    relation: str
    object: str
    confidence: float = 0.5
    verified: bool = False
    source: str = ""


class ConceptGraph:
    """Small contradiction-preserving graph.

    Conflicting objects for the same (subject, relation) are retained, not overwritten.
    """

    def __init__(self) -> None:
        self._aliases: dict[str, str] = {}
        self._facts: dict[tuple[str, str, str], Fact] = {}

    def alias(self, alias: str, canonical: str) -> None:
        alias = alias.strip()
        canonical = canonical.strip()
        if not alias or not canonical:
            raise ValueError("alias and canonical must be non-empty")
        self._aliases[alias] = canonical

    def canonical(self, value: str) -> str:
        seen: set[str] = set()
        cur = value.strip()
        while cur in self._aliases:
            if cur in seen:
                raise ValueError("alias cycle")
            seen.add(cur)
            cur = self._aliases[cur]
        return cur

    def add(self, fact: Fact) -> Fact:
        if not 0.0 <= fact.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        normalized = Fact(
            subject=self.canonical(fact.subject),
            relation=fact.relation.strip(),
            object=self.canonical(fact.object),
            confidence=fact.confidence,
            verified=fact.verified,
            source=fact.source,
        )
        if not normalized.subject or not normalized.relation or not normalized.object:
            raise ValueError("fact fields must be non-empty")
        key = (normalized.subject, normalized.relation, normalized.object)
        old = self._facts.get(key)
        if old is None or (normalized.verified, normalized.confidence) > (old.verified, old.confidence):
            self._facts[key] = normalized
        return self._facts[key]

    def query(self, subject: str, relation: str | None = None) -> list[Fact]:
        subject = self.canonical(subject)
        out = [
            f for f in self._facts.values()
            if f.subject == subject and (relation is None or f.relation == relation)
        ]
        return sorted(out, key=lambda f: (f.relation, -int(f.verified), -f.confidence, f.object))

    def contradictions(self, subject: str, relation: str) -> list[Fact]:
        facts = self.query(subject, relation)
        if len({f.object for f in facts}) <= 1:
            return []
        return facts

    def edges(self) -> tuple[Fact, ...]:
        return tuple(sorted(self._facts.values(), key=lambda f: (f.subject, f.relation, f.object)))
