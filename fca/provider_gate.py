from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderHealth:
    """Provider probe result used to gate externally-backed capabilities."""

    status: str
    capabilities: frozenset[str] = frozenset()
    provider_id: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"healthy", "unhealthy", "unknown"}:
            raise ValueError("invalid provider health status")


class ProviderHealthGate:
    """Fail-closed capability gate adapted from FAP V74.

    FCA's connectome remains responsible for selecting an organ. This gate only
    decides whether a provider-backed organ may execute after selection.
    """

    def __init__(self, health: ProviderHealth | None = None) -> None:
        self.health = health

    def update(self, health: ProviderHealth) -> None:
        self.health = health

    def allows(self, capability: str) -> bool:
        capability = capability.strip()
        if not capability:
            return True
        return bool(
            self.health is not None
            and self.health.status == "healthy"
            and capability in self.health.capabilities
        )

    def rejection_reason(self, capability: str) -> str:
        if self.health is None:
            return "provider_probe_required"
        if self.health.status != "healthy":
            return self.health.reason or "provider_not_healthy"
        if capability not in self.health.capabilities:
            return "capability_not_declared"
        return ""
