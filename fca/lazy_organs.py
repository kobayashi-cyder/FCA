from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable

from .organs import Organ, OrganRegistry, OrganResult
from .provider_gate import ProviderHealthGate
from .retry_policy import OrganRetryPolicy


OrganFactory = Callable[[], Organ]


@dataclass(frozen=True)
class LazyOrganSpec:
    name: str
    factory: OrganFactory
    capability: str = ""
    retry_policy: OrganRetryPolicy | None = None


class LazyOrganRegistry:
    """Sparse/lazy organ registry compatible with AutonomousLoop.

    Registration stores factories only. An organ is constructed on first
    selection, then cached. This preserves FCA's connectome-first action
    selection while avoiding eager specialist startup.
    """

    def __init__(
        self,
        *,
        health_gate: ProviderHealthGate | None = None,
        sleeper=None,
        jitter_source=None,
    ) -> None:
        kwargs = {"health_gate": health_gate}
        if sleeper is not None:
            kwargs["sleeper"] = sleeper
        if jitter_source is not None:
            kwargs["jitter_source"] = jitter_source
        self._runtime = OrganRegistry(**kwargs)
        self._specs: dict[str, LazyOrganSpec] = {}
        self._loaded: set[str] = set()
        self._load_count = 0
        self._lock = Lock()

    @staticmethod
    def _clean_name(name: str) -> str:
        name = name.strip()
        if not name or name.startswith("_"):
            raise ValueError("invalid organ name")
        return name

    def register(
        self,
        name: str,
        factory: OrganFactory,
        *,
        capability: str = "",
        retry_policy: OrganRetryPolicy | None = None,
    ) -> None:
        name = self._clean_name(name)
        if not callable(factory):
            raise TypeError("factory must be callable")
        if name in self._specs:
            raise ValueError(f"duplicate organ: {name}")
        self._specs[name] = LazyOrganSpec(
            name=name,
            factory=factory,
            capability=capability.strip(),
            retry_policy=retry_policy,
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    @property
    def loaded(self) -> tuple[str, ...]:
        return tuple(name for name in self._specs if name in self._loaded)

    @property
    def load_count(self) -> int:
        return self._load_count

    def _ensure_loaded(self, name: str) -> None:
        if name in self._loaded:
            return
        try:
            spec = self._specs[name]
        except KeyError as exc:
            raise KeyError(f"unknown organ: {name}") from exc

        with self._lock:
            if name in self._loaded:
                return
            organ = spec.factory()
            if not callable(organ):
                raise TypeError("organ factory must return a callable organ")
            self._runtime.register(
                name,
                organ,
                capability=spec.capability,
                retry_policy=spec.retry_policy,
            )
            self._loaded.add(name)
            self._load_count += 1

    def run(self, name: str, goal: str, observation: str) -> OrganResult:
        self._ensure_loaded(name)
        return self._runtime.run(name, goal, observation)
