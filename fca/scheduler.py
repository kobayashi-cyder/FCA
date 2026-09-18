from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrganBid:
    name: str
    relevance: float
    expected_value: float
    information_gain: float
    cost: float

    @property
    def score(self) -> float:
        return self.relevance * (self.expected_value + self.information_gain) - self.cost


class ValueScheduler:
    """Selects sparse specialist activation under a per-step resource budget."""

    def __init__(self, budget: float = 1.0, max_active: int = 3) -> None:
        if budget <= 0 or max_active < 1:
            raise ValueError("invalid budget")
        self.budget = budget
        self.max_active = max_active

    def select(self, bids: list[OrganBid]) -> tuple[str, ...]:
        chosen: list[str] = []
        spent = 0.0
        for bid in sorted(bids, key=lambda b: (b.score, -b.cost, b.name), reverse=True):
            if bid.score <= 0.0:
                continue
            if len(chosen) >= self.max_active:
                break
            if spent + bid.cost > self.budget:
                continue
            chosen.append(bid.name)
            spent += bid.cost
        return tuple(chosen)
