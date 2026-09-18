from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class ProvenanceEvent:
    index: int
    kind: str
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str


class ProvenanceChain:
    """Tamper-evident append-only event chain for structural improvements."""

    def __init__(self) -> None:
        self.events: list[ProvenanceEvent] = []

    @staticmethod
    def _hash(index: int, kind: str, payload: dict[str, Any], previous_hash: str) -> str:
        raw = json.dumps(
            {"index": index, "kind": kind, "payload": payload, "previous_hash": previous_hash},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(raw).hexdigest()

    def append(self, kind: str, payload: dict[str, Any]) -> ProvenanceEvent:
        if not kind:
            raise ValueError("kind must be non-empty")
        index = len(self.events)
        previous = self.events[-1].event_hash if self.events else "0" * 64
        event = ProvenanceEvent(index, kind, dict(payload), previous, self._hash(index, kind, payload, previous))
        self.events.append(event)
        return event

    def verify(self) -> bool:
        previous = "0" * 64
        for index, event in enumerate(self.events):
            if event.index != index or event.previous_hash != previous:
                return False
            expected = self._hash(event.index, event.kind, event.payload, event.previous_hash)
            if event.event_hash != expected:
                return False
            previous = event.event_hash
        return True
