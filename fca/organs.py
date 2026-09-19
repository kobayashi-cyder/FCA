from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .provider_gate import ProviderHealthGate


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
    """Bounded dispatch table for specialist organs/providers.

    Provider-backed organs may declare a capability. When a health gate is
    installed those organs fail closed until an independent probe marks that
    capability healthy. Connectome selection itself is unchanged.
    """

    def __init__(self, *, health_gate: ProviderHealthGate | None = None) -> None:
        self._organs: dict[str, Organ] = {}
        self._capabilities: dict[str, str] = {}
        self.health_gate = health_gate

    def register(self, name: str, organ: Organ, *, capability: str = "") -> None:
        name = name.strip()
        capability = capability.strip()
        if not name or name.startswith("_"):
            raise ValueError("invalid organ name")
        self._organs[name] = organ
        if capability:
            self._capabilities[name] = capability
        else:
            self._capabilities.pop(name, None)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._organs)

    def run(self, name: str, goal: str, observation: str) -> OrganResult:
        try:
            organ = self._organs[name]
        except KeyError as exc:
            raise KeyError(f"unknown organ: {name}") from exc
        capability = self._capabilities.get(name, "")
        if capability and self.health_gate is not None and not self.health_gate.allows(capability):
            return OrganResult(
                observation=observation,
                blocked=True,
                reason=self.health_gate.rejection_reason(capability),
            )
        result = organ(goal, observation)
        if not isinstance(result, OrganResult):
            raise TypeError("organ must return OrganResult")
        return result
