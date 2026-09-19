from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrganRetryPolicy:
    """Fail-closed retry contract for an FCA organ.

    Re-execution is opt-in and allowed only for explicitly idempotent organs.
    The connectome still selects the organ; this policy only governs bounded
    recovery after that selected organ raises a transient transport error.
    """

    max_attempts: int = 1
    idempotent: bool = False
    justification: str = ""

    def __post_init__(self) -> None:
        if not 1 <= int(self.max_attempts) <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if self.max_attempts > 1 and not self.idempotent:
            raise ValueError("retry requires an idempotent organ")
        if self.max_attempts > 1 and not self.justification.strip():
            raise ValueError("retry requires an idempotency justification")

    @property
    def enabled(self) -> bool:
        return self.max_attempts > 1
