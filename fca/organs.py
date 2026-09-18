from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class OrganResult:
    observation: str
    reward: float = 0.0
    progress: float = 0.0
    terminal: bool = False
    blocked: bool = False
    reason: str = ""


Organ = Callable[[str, str], OrganResult]


class OrganRegistry:
    """Bounded dispatch table for specialist organs/providers."""

    def __init__(self) -> None:
        self._organs: dict[str, Organ] = {}

    def register(self, name: str, organ: Organ) -> None:
        name = name.strip()
        if not name or name.startswith("_"):
            raise ValueError("invalid organ name")
        self._organs[name] = organ

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._organs)

    def run(self, name: str, goal: str, observation: str) -> OrganResult:
        try:
            organ = self._organs[name]
        except KeyError as exc:
            raise KeyError(f"unknown organ: {name}") from exc
        result = organ(goal, observation)
        if not isinstance(result, OrganResult):
            raise TypeError("organ must return OrganResult")
        return result
