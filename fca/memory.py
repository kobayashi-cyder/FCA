from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt

from .connectome import SensoryHash


@dataclass(frozen=True)
class MemoryItem:
    key: str
    text: str
    signature: tuple[float, ...]
    utility: float = 0.0
    confidence: float = 0.5
    accesses: int = 0
    contradiction_group: str | None = None


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class HotColdMemory:
    """Bounded semantic-ish memory with selective page-in."""

    def __init__(
        self,
        *,
        channels: int = 128,
        hot_capacity: int = 64,
        cold_capacity: int = 4096,
        page_in: int = 8,
    ) -> None:
        if min(hot_capacity, cold_capacity, page_in) < 1:
            raise ValueError("capacities must be positive")
        if page_in > hot_capacity:
            raise ValueError("page_in cannot exceed hot_capacity")
        self.encoder = SensoryHash(channels)
        self.hot_capacity = hot_capacity
        self.cold_capacity = cold_capacity
        self.page_in = page_in
        self.hot: dict[str, MemoryItem] = {}
        self.cold: dict[str, MemoryItem] = {}

    def remember(
        self,
        key: str,
        text: str,
        *,
        utility: float = 0.0,
        confidence: float = 0.5,
        contradiction_group: str | None = None,
    ) -> None:
        key = key.strip()
        text = text.strip()
        if not key or not text:
            raise ValueError("key and text must be non-empty")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        item = MemoryItem(
            key=key,
            text=text,
            signature=tuple(self.encoder.encode_text(text)),
            utility=float(utility),
            confidence=confidence,
            contradiction_group=contradiction_group,
        )
        self.hot[key] = item
        self.cold.pop(key, None)
        self._trim_hot()
        self._trim_cold()

    def retrieve(self, query: str, limit: int | None = None) -> list[MemoryItem]:
        qsig = tuple(self.encoder.encode_text(query))
        limit = self.page_in if limit is None else max(1, min(limit, self.page_in))
        candidates = {**self.cold, **self.hot}

        def score(item: MemoryItem) -> tuple[float, float, int, str]:
            semantic = _cosine(qsig, item.signature)
            return (
                semantic + 0.10 * item.utility + 0.05 * item.confidence,
                item.utility,
                item.accesses,
                item.key,
            )

        ranked = sorted(candidates.values(), key=score, reverse=True)[:limit]
        out: list[MemoryItem] = []
        for item in ranked:
            updated = replace(item, accesses=item.accesses + 1)
            self.hot[item.key] = updated
            self.cold.pop(item.key, None)
            out.append(updated)
        self._trim_hot()
        return out

    def _protected(self, item: MemoryItem) -> bool:
        return item.contradiction_group is not None or item.confidence >= 0.90

    def _retention(self, item: MemoryItem) -> tuple[int, float, float, int]:
        return (
            1 if self._protected(item) else 0,
            item.utility,
            item.confidence,
            item.accesses,
        )

    def _trim_hot(self) -> None:
        while len(self.hot) > self.hot_capacity:
            victim = min(self.hot.values(), key=self._retention)
            self.cold[victim.key] = victim
            del self.hot[victim.key]
        self._trim_cold()

    def _trim_cold(self) -> None:
        while len(self.cold) > self.cold_capacity:
            unprotected = [m for m in self.cold.values() if not self._protected(m)]
            pool = unprotected or list(self.cold.values())
            victim = min(pool, key=self._retention)
            del self.cold[victim.key]

    @property
    def size(self) -> int:
        return len(self.hot) + len(self.cold)
