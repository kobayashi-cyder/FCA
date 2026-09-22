from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def _pairs(values: Mapping[str, object] | None) -> tuple[tuple[str, str], ...]:
    if not values:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in values.items()))


@dataclass(frozen=True)
class Entity:
    entity_id: str
    kind: str
    state: str = ""
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, order=True)
class Relation:
    subject: str
    predicate: str
    object: str
    negative: bool = False


class WorldGraph:
    """Small deterministic task/world graph.

    This generalizes FAP V87.34's object/state/relation discipline into FCA task
    state. It is deliberately not a renderer or language model.
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: set[Relation] = set()

    @property
    def entities(self) -> tuple[Entity, ...]:
        return tuple(self._entities[k] for k in sorted(self._entities))

    @property
    def relations(self) -> tuple[Relation, ...]:
        return tuple(sorted(self._relations))

    def upsert(
        self,
        entity_id: str,
        kind: str,
        *,
        state: str = "",
        attributes: Mapping[str, object] | None = None,
    ) -> Entity:
        entity_id = entity_id.strip()
        kind = kind.strip()
        if not entity_id or not kind:
            raise ValueError("entity_id and kind are required")
        entity = Entity(entity_id, kind, state.strip(), _pairs(attributes))
        self._entities[entity_id] = entity
        return entity

    def relate(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        negative: bool = False,
    ) -> Relation:
        subject = subject.strip()
        predicate = predicate.strip()
        object = object.strip()
        if not subject or not predicate or not object:
            raise ValueError("relation fields are required")
        if subject not in self._entities or object not in self._entities:
            raise ValueError("relation endpoints must already exist")
        relation = Relation(subject, predicate, object, bool(negative))
        self._relations.add(relation)
        return relation

    def has(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        negative: bool = False,
    ) -> bool:
        return Relation(subject, predicate, object, bool(negative)) in self._relations

    def snapshot(self) -> dict[str, object]:
        return {
            "entities": [
                {
                    "id": e.entity_id,
                    "kind": e.kind,
                    "state": e.state,
                    "attributes": dict(e.attributes),
                }
                for e in self.entities
            ],
            "relations": [
                {
                    "subject": r.subject,
                    "predicate": r.predicate,
                    "object": r.object,
                    "negative": r.negative,
                }
                for r in self.relations
            ],
        }
