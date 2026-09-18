from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from math import tanh
from typing import Iterable, Sequence


def _u64(text: str) -> int:
    return int.from_bytes(blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


@dataclass(frozen=True)
class SparsePattern:
    active: tuple[int, ...]
    values: tuple[float, ...]

    def as_dict(self) -> dict[int, float]:
        return dict(zip(self.active, self.values))


class SensoryHash:
    """Maps arbitrary text into bounded projection-neuron-like channels.

    This is intentionally deterministic and tiny. It is not an OCR/NLP model.
    """

    def __init__(self, channels: int = 128) -> None:
        if channels < 16:
            raise ValueError("channels must be >= 16")
        self.channels = channels

    def encode_text(self, text: str) -> list[float]:
        text = text.strip()
        if not text:
            return [0.0] * self.channels
        v = [0.0] * self.channels
        tokens = text.casefold().split()
        if len(tokens) == 1:
            s = tokens[0]
            tokens = [s[i : i + 2] for i in range(max(1, len(s) - 1))] or [s]
        for token in tokens:
            for salt in range(3):
                h = _u64(f"{salt}:{token}")
                idx = h % self.channels
                sign = 1.0 if ((h >> 8) & 1) else -1.0
                v[idx] += sign
        scale = max(1.0, max(abs(x) for x in v))
        return [x / scale for x in v]


class KenyonLayer:
    """Sparse expansion + global competition, inspired by mushroom-body KC coding.

    The default fixed hash-derived fan-in is a compact bootstrap wiring table.
    Explicit wiring may be injected for data-backed connectome experiments.
    """

    def __init__(
        self,
        input_channels: int = 128,
        kcs: int = 256,
        fan_in: int = 6,
        winners: int = 16,
        seed: str = "FCA",
        wiring: Sequence[Sequence[int]] | None = None,
    ) -> None:
        self.input_channels = input_channels
        self.fan_in = fan_in
        self.seed = seed
        if wiring is None:
            if not (1 <= fan_in <= input_channels):
                raise ValueError("fan_in out of range")
            self.kcs = kcs
            self._wiring = tuple(self._fan_in_for(kc) for kc in range(kcs))
        else:
            checked: list[tuple[int, ...]] = []
            for inputs in wiring:
                row = tuple(dict.fromkeys(int(i) for i in inputs))
                if not row or any(i < 0 or i >= input_channels for i in row):
                    raise ValueError("invalid explicit wiring")
                checked.append(row)
            if not checked:
                raise ValueError("wiring must contain at least one KC")
            self.kcs = len(checked)
            self._wiring = tuple(checked)
        if not (1 <= winners <= self.kcs):
            raise ValueError("winners must be in 1..kcs")
        self.winners = winners

    def _fan_in_for(self, kc: int) -> tuple[int, ...]:
        seen: set[int] = set()
        i = 0
        while len(seen) < self.fan_in:
            seen.add(_u64(f"{self.seed}:{kc}:{i}") % self.input_channels)
            i += 1
        return tuple(sorted(seen))

    def activate(self, sensory: Sequence[float], trace: dict[int, float] | None = None) -> SparsePattern:
        if len(sensory) != self.input_channels:
            raise ValueError("sensory vector has wrong width")
        trace = trace or {}
        scored: list[tuple[float, int]] = []
        for kc, inputs in enumerate(self._wiring):
            drive = sum(sensory[i] for i in inputs) / len(inputs)
            drive += 0.10 * trace.get(kc, 0.0)
            scored.append((tanh(drive), kc))
        scored.sort(key=lambda p: (p[0], -p[1]), reverse=True)
        winners = scored[: self.winners]
        return SparsePattern(
            active=tuple(kc for _, kc in winners),
            values=tuple(value for value, _ in winners),
        )


class TemporalTrace:
    def __init__(self, decay: float = 0.82, floor: float = 1e-4) -> None:
        if not 0.0 < decay < 1.0:
            raise ValueError("decay must be in (0,1)")
        self.decay = decay
        self.floor = floor
        self.state: dict[int, float] = {}

    def update(self, pattern: SparsePattern) -> dict[int, float]:
        nxt = {k: v * self.decay for k, v in self.state.items() if abs(v * self.decay) >= self.floor}
        for kc, value in zip(pattern.active, pattern.values):
            nxt[kc] = max(nxt.get(kc, 0.0), value)
        self.state = nxt
        return dict(self.state)


class MBONPolicy:
    """Small action-value readout with dopamine-like reward-prediction-error learning."""

    def __init__(self, actions: Iterable[str], learning_rate: float = 0.08) -> None:
        actions = tuple(dict.fromkeys(actions))
        if not actions:
            raise ValueError("at least one action is required")
        self.actions = actions
        self.learning_rate = learning_rate
        self.weights: dict[str, dict[int, float]] = {a: {} for a in actions}
        self.baseline = 0.0

    def scores(self, pattern: SparsePattern) -> dict[str, float]:
        p = pattern.as_dict()
        return {
            action: sum(self.weights[action].get(kc, 0.0) * value for kc, value in p.items())
            for action in self.actions
        }

    def select(self, pattern: SparsePattern) -> str:
        scores = self.scores(pattern)
        return max(self.actions, key=lambda a: (scores[a], -self.actions.index(a)))

    def learn(self, pattern: SparsePattern, action: str, reward: float) -> float:
        if action not in self.weights:
            raise KeyError(action)
        prediction = self.scores(pattern)[action]
        rpe = reward - prediction - self.baseline
        for kc, value in zip(pattern.active, pattern.values):
            self.weights[action][kc] = self.weights[action].get(kc, 0.0) + self.learning_rate * rpe * value
        self.baseline = 0.98 * self.baseline + 0.02 * reward
        return rpe
