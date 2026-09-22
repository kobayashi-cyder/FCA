from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class HotPathStatus:
    native_present: bool
    native_enabled: bool
    native_verified: bool
    native_failures: int
    calls: int


class VerifiedHotPath(Generic[T]):
    """Reference-preserving optional native hot path.

    The Python reference remains authoritative. The native function must be
    deterministic and side-effect-free because the first native call is checked
    against the reference result. Any exception or mismatch permanently falls
    back to Python for this instance.
    """

    def __init__(
        self,
        reference: Callable[..., T],
        native: Callable[..., T] | None = None,
        *,
        equivalent: Callable[[T, T], bool] | None = None,
    ) -> None:
        if not callable(reference):
            raise TypeError("reference must be callable")
        if native is not None and not callable(native):
            raise TypeError("native must be callable")
        self.reference = reference
        self.native = native
        self.equivalent = equivalent or (lambda a, b: a == b)
        self._native_enabled = native is not None
        self._native_verified = False
        self._native_failures = 0
        self._calls = 0

    @property
    def status(self) -> HotPathStatus:
        return HotPathStatus(
            native_present=self.native is not None,
            native_enabled=self._native_enabled,
            native_verified=self._native_verified,
            native_failures=self._native_failures,
            calls=self._calls,
        )

    def __call__(self, *args, **kwargs) -> T:
        self._calls += 1
        if not self._native_enabled or self.native is None:
            return self.reference(*args, **kwargs)

        if not self._native_verified:
            reference_value = self.reference(*args, **kwargs)
            try:
                native_value = self.native(*args, **kwargs)
            except Exception:
                self._native_failures += 1
                self._native_enabled = False
                return reference_value
            if not self.equivalent(reference_value, native_value):
                self._native_failures += 1
                self._native_enabled = False
                return reference_value
            self._native_verified = True
            return native_value

        try:
            return self.native(*args, **kwargs)
        except Exception:
            self._native_failures += 1
            self._native_enabled = False
            return self.reference(*args, **kwargs)
