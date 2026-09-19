from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrganRetryPolicy:
    """Fail-closed retry contract for an FCA organ.

    Re-execution is opt-in and allowed only for explicitly idempotent organs.
    Handler exceptions remain terminal unless their concrete exception type is
    explicitly listed. The connectome still selects the organ; this policy only
    governs bounded recovery after that selected organ begins execution.
    """

    max_attempts: int = 1
    idempotent: bool = False
    justification: str = ""
    retryable_exceptions: tuple[type[Exception], ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= int(self.max_attempts) <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if self.max_attempts > 1 and not self.idempotent:
            raise ValueError("retry requires an idempotent organ")
        if self.max_attempts > 1 and not self.justification.strip():
            raise ValueError("retry requires an idempotency justification")
        for exc_type in self.retryable_exceptions:
            if not isinstance(exc_type, type) or not issubclass(exc_type, Exception):
                raise ValueError("retryable_exceptions must contain Exception types")
        if self.retryable_exceptions and self.max_attempts <= 1:
            raise ValueError("retryable_exceptions require max_attempts > 1")

    @property
    def enabled(self) -> bool:
        return self.max_attempts > 1
