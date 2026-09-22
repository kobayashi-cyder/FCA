from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from typing import Any

from .repository_organ import RepositoryCodingHostResult, RepositoryCodingRunner


FAP_REPOSITORY_HOST_CONTRACT = "fap.repository.host.v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_REASON = re.compile(r"^[0-9A-Za-z_.:-]{0,160}$")
_ALLOWED_KEYS = frozenset({
    "contract", "state", "observation", "plan_id", "repository_digest",
    "progress", "reason", "attempts", "repairs_used",
})


class RepositoryHostContractError(ValueError):
    """Raised when an external FAP repository-host envelope is not admissible."""


def adapt_fap_repository_host(
    payload: Mapping[str, Any],
    *,
    max_observation_chars: int = 20_000,
) -> RepositoryCodingHostResult:
    """Validate a pure-data FAP host response and convert it to FCA inert type."""
    if not isinstance(payload, Mapping):
        raise RepositoryHostContractError("repository host payload must be a mapping")
    if not 256 <= int(max_observation_chars) <= 100_000:
        raise ValueError("max_observation_chars must be in [256, 100000]")

    keys = frozenset(str(k) for k in payload.keys())
    unknown = keys - _ALLOWED_KEYS
    missing = _ALLOWED_KEYS - keys
    if unknown:
        raise RepositoryHostContractError("repository host payload has unknown fields")
    if missing:
        raise RepositoryHostContractError("repository host payload is incomplete")

    contract = _plain_string(payload["contract"], "contract", 64)
    if contract != FAP_REPOSITORY_HOST_CONTRACT:
        raise RepositoryHostContractError("unsupported repository host contract")

    state = _plain_string(payload["state"], "state", 32)
    if state not in {"verified_candidate", "rejected", "blocked"}:
        raise RepositoryHostContractError("unsupported repository host state")

    observation = _plain_string(
        payload["observation"], "observation", int(max_observation_chars), allow_empty=True
    )
    reason = _plain_string(payload["reason"], "reason", 160, allow_empty=True)
    if reason and not _SAFE_REASON.fullmatch(reason):
        raise RepositoryHostContractError("repository host reason is not a safe code")

    progress = _bounded_float(payload["progress"], "progress", 0.0, 1.0)
    attempts = _bounded_int(payload["attempts"], "attempts", 0, 32)
    repairs_used = _bounded_int(payload["repairs_used"], "repairs_used", 0, 4)
    if repairs_used > attempts:
        raise RepositoryHostContractError("repairs_used cannot exceed attempts")

    plan_id = _plain_string(payload["plan_id"], "plan_id", 64, allow_empty=True).lower()
    repository_digest = _plain_string(
        payload["repository_digest"], "repository_digest", 64, allow_empty=True
    ).lower()

    if state == "verified_candidate":
        if not _HEX64.fullmatch(plan_id):
            raise RepositoryHostContractError("verified candidate requires valid plan_id")
        if not _HEX64.fullmatch(repository_digest):
            raise RepositoryHostContractError("verified candidate requires valid repository_digest")
        if attempts < 1:
            raise RepositoryHostContractError("verified candidate requires an attempt")
        if progress <= 0.0:
            raise RepositoryHostContractError("verified candidate requires positive progress")
    else:
        if plan_id and not _HEX64.fullmatch(plan_id):
            raise RepositoryHostContractError("plan_id must be empty or SHA-256")
        if repository_digest and not _HEX64.fullmatch(repository_digest):
            raise RepositoryHostContractError("repository_digest must be empty or SHA-256")

    return RepositoryCodingHostResult(
        state=state,
        observation=observation,
        plan_id=plan_id,
        repository_digest=repository_digest,
        progress=progress,
        reason=reason,
    )


def repository_host_runner_from_mapping(
    runner: Callable[[str, str], Mapping[str, Any]],
    *,
    max_observation_chars: int = 20_000,
) -> RepositoryCodingRunner:
    """Wrap a JSON-like host callable without importing FAP into FCA."""
    if not callable(runner):
        raise TypeError("repository host mapping runner must be callable")

    def _run(goal: str, observation: str) -> RepositoryCodingHostResult:
        payload = runner(goal, observation)
        return adapt_fap_repository_host(
            payload,
            max_observation_chars=max_observation_chars,
        )

    return _run


def _plain_string(
    value: Any,
    name: str,
    max_chars: int,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise RepositoryHostContractError(f"{name} must be a string")
    if len(value) > max_chars:
        raise RepositoryHostContractError(f"{name} exceeds size bound")
    if not allow_empty and not value:
        raise RepositoryHostContractError(f"{name} must not be empty")
    if "\\x00" in value:
        raise RepositoryHostContractError(f"{name} contains NUL")
    return value


def _bounded_float(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RepositoryHostContractError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise RepositoryHostContractError(f"{name} is out of bounds")
    return number


def _bounded_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RepositoryHostContractError(f"{name} must be an integer")
    if not low <= value <= high:
        raise RepositoryHostContractError(f"{name} is out of bounds")
    return value
