from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from .exchange_registry import ExchangeRegistry
from .lazy_organs import LazyOrganRegistry
from .organs import Organ, OrganResult


CAPABILITY = "repository_coding_verified_candidate"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RepositoryCodingHostResult:
    """Inert result returned by a host-provided repository coding runner."""

    state: str
    observation: str
    plan_id: str = ""
    repository_digest: str = ""
    progress: float = 0.0
    reason: str = ""


RepositoryCodingRunner = Callable[[str, str], RepositoryCodingHostResult]


@dataclass(frozen=True)
class RepositoryCodingHostBinding:
    """Explicit host binding for repository coding execution.

    FCA does not derive this callable from an exchange capsule. The capsule only
    gates whether the already host-provided binding may be invoked.
    """

    binding_id: str
    capsule_digest: str
    runner: RepositoryCodingRunner
    sandbox_only: bool = True
    promotion_requires_approval: bool = True


class RepositoryCodingOrgan:
    """Connectome-selected adapter around an explicitly host-provided runner."""

    def __init__(
        self,
        binding: RepositoryCodingHostBinding,
        registry: ExchangeRegistry,
        *,
        max_observation_chars: int = 20_000,
    ) -> None:
        binding_id = binding.binding_id.strip()
        digest = binding.capsule_digest.strip().lower()
        if not binding_id or binding_id.startswith("_"):
            raise ValueError("invalid repository coding binding_id")
        if not HEX64.fullmatch(digest):
            raise ValueError("capsule_digest must be a 64-char lowercase SHA-256")
        if not callable(binding.runner):
            raise TypeError("repository coding runner must be callable")
        if binding.sandbox_only is not True:
            raise ValueError("repository coding host binding must be sandbox_only")
        if binding.promotion_requires_approval is not True:
            raise ValueError(
                "repository coding host binding must require promotion approval"
            )
        if not 256 <= int(max_observation_chars) <= 100_000:
            raise ValueError("max_observation_chars must be in [256, 100000]")
        self.binding = binding
        self.registry = registry
        self.max_observation_chars = int(max_observation_chars)

    def __call__(self, goal: str, observation: str) -> OrganResult:
        if not self.registry.allows(self.binding.capsule_digest, CAPABILITY):
            return OrganResult(
                observation=observation,
                reward=0.0,
                progress=0.0,
                terminal=False,
                blocked=True,
                reason="repository_coding_evidence_not_accepted",
            )

        try:
            result = self.binding.runner(goal, observation)
        except Exception as exc:
            return OrganResult(
                observation=observation,
                reward=0.0,
                progress=0.0,
                terminal=False,
                blocked=True,
                reason=f"repository_coding_runner_failed:{type(exc).__name__}",
            )

        try:
            return self._adapt_result(result, fallback_observation=observation)
        except Exception as exc:
            return OrganResult(
                observation=observation,
                reward=0.0,
                progress=0.0,
                terminal=False,
                blocked=True,
                reason=f"repository_coding_result_rejected:{type(exc).__name__}",
            )

    def _adapt_result(
        self,
        result: RepositoryCodingHostResult,
        *,
        fallback_observation: str,
    ) -> OrganResult:
        if not isinstance(result, RepositoryCodingHostResult):
            raise TypeError("runner must return RepositoryCodingHostResult")
        state = result.state.strip()
        if state not in {"verified_candidate", "rejected", "blocked"}:
            raise ValueError("unsupported repository coding host state")
        if not 0.0 <= float(result.progress) <= 1.0:
            raise ValueError("repository coding progress must be in [0, 1]")

        text = str(result.observation)
        if len(text) > self.max_observation_chars:
            raise ValueError("repository coding observation exceeds bound")
        if not text:
            text = fallback_observation

        if state == "verified_candidate":
            plan_id = result.plan_id.strip().lower()
            repository_digest = result.repository_digest.strip().lower()
            if not HEX64.fullmatch(plan_id):
                raise ValueError("verified candidate requires a valid plan_id")
            if not HEX64.fullmatch(repository_digest):
                raise ValueError(
                    "verified candidate requires a valid repository_digest"
                )
            return OrganResult(
                observation=text,
                reward=0.0,
                progress=max(float(result.progress), 1.0),
                terminal=False,
                blocked=False,
                reason=(
                    "repository_coding_verified_candidate:"
                    f"{plan_id[:16]}:{repository_digest[:16]}"
                ),
            )

        reason = result.reason.strip() or f"repository_coding_{state}"
        return OrganResult(
            observation=text,
            reward=0.0,
            progress=float(result.progress),
            terminal=False,
            blocked=True,
            reason=reason,
        )


def register_repository_coding_organ(
    organs: LazyOrganRegistry,
    registry: ExchangeRegistry,
    binding: RepositoryCodingHostBinding,
    *,
    name: str = "repository_coding",
    provider_capability: str = "",
    max_observation_chars: int = 20_000,
) -> None:
    """Register lazily; construction still happens only after selection."""
    organs.register(
        name,
        lambda: RepositoryCodingOrgan(
            binding,
            registry,
            max_observation_chars=max_observation_chars,
        ),
        capability=provider_capability,
    )
