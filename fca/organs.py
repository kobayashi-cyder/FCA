from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .provider_gate import ProviderHealthGate
from .retry_policy import OrganRetryPolicy


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
    capability healthy. Connectome selection itself is unchanged. Selected
    organs may additionally opt into bounded retries, but only with an explicit
    idempotency declaration and justification.
    """

    def __init__(self, *, health_gate: ProviderHealthGate | None = None) -> None:
        self._organs: dict[str, Organ] = {}
        self._capabilities: dict[str, str] = {}
        self._retry_policies: dict[str, OrganRetryPolicy] = {}
        self.health_gate = health_gate

    def register(
        self,
        name: str,
        organ: Organ,
        *,
        capability: str = "",
        retry_policy: OrganRetryPolicy | None = None,
    ) -> None:
        name = name.strip()
        capability = capability.strip()
        if not name or name.startswith("_"):
            raise ValueError("invalid organ name")
        self._organs[name] = organ
        if capability:
            self._capabilities[name] = capability
        else:
            self._capabilities.pop(name, None)
        if retry_policy is not None:
            self._retry_policies[name] = retry_policy
        else:
            self._retry_policies.pop(name, None)

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

        policy = self._retry_policies.get(name, OrganRetryPolicy())
        for attempt in range(1, policy.max_attempts + 1):
            try:
                result = organ(goal, observation)
            except (TimeoutError, ConnectionError):
                if attempt < policy.max_attempts:
                    continue
                raise
            if not isinstance(result, OrganResult):
                raise TypeError("organ must return OrganResult")
            return result
        raise RuntimeError("organ retry loop exhausted")
