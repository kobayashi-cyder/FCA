from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


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
    retry_delay_seconds: float = 0.0
    retry_backoff_multiplier: float = 1.0
    max_total_delay_seconds: float = 120.0
    retry_jitter_ratio: float = 0.0

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
        if not 0.0 <= float(self.retry_delay_seconds) <= 60.0:
            raise ValueError("retry_delay_seconds must be between 0 and 60")
        if self.retry_delay_seconds and self.max_attempts <= 1:
            raise ValueError("retry delay requires max_attempts > 1")
        if not 1.0 <= float(self.retry_backoff_multiplier) <= 4.0:
            raise ValueError("retry_backoff_multiplier must be between 1 and 4")
        if self.retry_backoff_multiplier != 1.0 and not self.retry_delay_seconds:
            raise ValueError("retry backoff requires retry_delay_seconds > 0")
        if not 0.0 <= float(self.max_total_delay_seconds) <= 120.0:
            raise ValueError("max_total_delay_seconds must be between 0 and 120")
        if self.retry_delay_seconds and not self.max_total_delay_seconds:
            raise ValueError("retry delay requires a positive total delay budget")
        if not 0.0 <= float(self.retry_jitter_ratio) <= 0.5:
            raise ValueError("retry_jitter_ratio must be between 0 and 0.5")
        if self.retry_jitter_ratio and not self.retry_delay_seconds:
            raise ValueError("retry jitter requires retry_delay_seconds > 0")

    @property
    def enabled(self) -> bool:
        return self.max_attempts > 1

    def delay_before_attempt(
        self,
        attempt: int,
        *,
        elapsed_delay: float = 0.0,
        jitter_unit: float = 0.5,
        retry_after_seconds: object = None,
    ) -> float:
        """Return bounded delay after ``attempt`` failed within the total budget."""
        if not self.retry_delay_seconds:
            return 0.0
        if not 0.0 <= float(jitter_unit) <= 1.0:
            raise ValueError("jitter_unit must be between 0 and 1")
        remaining = max(0.0, float(self.max_total_delay_seconds) - float(elapsed_delay))
        delay = float(self.retry_delay_seconds) * (
            float(self.retry_backoff_multiplier) ** max(0, int(attempt) - 1)
        )
        if self.retry_jitter_ratio:
            centered = (2.0 * float(jitter_unit)) - 1.0
            delay *= 1.0 + (float(self.retry_jitter_ratio) * centered)
        try:
            hinted_delay = float(retry_after_seconds)
        except (TypeError, ValueError):
            hinted_delay = 0.0
        if not isfinite(hinted_delay) or hinted_delay < 0:
            hinted_delay = 0.0
        delay = max(delay, hinted_delay)
        return min(60.0, max(0.0, delay), remaining)
