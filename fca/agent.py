from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .connectome import KenyonLayer, MBONPolicy, SensoryHash, SparsePattern, TemporalTrace


@dataclass(frozen=True)
class Decision:
    action: str
    pattern: SparsePattern
    scores: dict[str, float]


class FCAAgent:
    """Minimal Fly Connectome Agent loop.

    sense -> sparse KC code -> competing action channels -> act -> reward -> plasticity
    """

    def __init__(self, actions: tuple[str, ...] = ("respond", "inspect", "wait")) -> None:
        self.sensory = SensoryHash(128)
        self.kc = KenyonLayer(input_channels=128, kcs=256, fan_in=6, winners=16)
        self.trace = TemporalTrace()
        self.policy = MBONPolicy(actions)
        self.last_decision: Decision | None = None

    def decide(self, observation: str) -> Decision:
        vec = self.sensory.encode_text(observation)
        pattern = self.kc.activate(vec, self.trace.state)
        self.trace.update(pattern)
        scores = self.policy.scores(pattern)
        decision = Decision(action=self.policy.select(pattern), pattern=pattern, scores=scores)
        self.last_decision = decision
        return decision

    def reinforce(self, reward: float) -> float:
        if self.last_decision is None:
            raise RuntimeError("decide() must be called before reinforce()")
        return self.policy.learn(self.last_decision.pattern, self.last_decision.action, reward)

    def snapshot(self) -> dict[str, Any]:
        """Serializable post-step neural state for checkpoint/resume."""
        return {
            "trace": {str(k): float(v) for k, v in self.trace.state.items()},
            "baseline": float(self.policy.baseline),
            "weights": {
                action: {str(k): float(v) for k, v in weights.items()}
                for action, weights in self.policy.weights.items()
            },
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            raise ValueError("agent snapshot must be an object")
        raw_trace = snapshot.get("trace", {})
        raw_weights = snapshot.get("weights", {})
        baseline = float(snapshot.get("baseline", 0.0))
        if not isinstance(raw_trace, dict) or not isinstance(raw_weights, dict) or not isfinite(baseline):
            raise ValueError("invalid agent snapshot")
        if set(raw_weights) != set(self.policy.actions):
            raise ValueError("snapshot action set does not match agent")

        trace: dict[int, float] = {}
        for key, value in raw_trace.items():
            kc = int(key)
            val = float(value)
            if not (0 <= kc < self.kc.kcs) or not isfinite(val):
                raise ValueError("invalid trace entry")
            trace[kc] = val

        weights: dict[str, dict[int, float]] = {}
        for action in self.policy.actions:
            row = raw_weights[action]
            if not isinstance(row, dict):
                raise ValueError("invalid weight row")
            converted: dict[int, float] = {}
            for key, value in row.items():
                kc = int(key)
                val = float(value)
                if not (0 <= kc < self.kc.kcs) or not isfinite(val):
                    raise ValueError("invalid weight entry")
                converted[kc] = val
            weights[action] = converted

        self.trace.state = trace
        self.policy.weights = weights
        self.policy.baseline = baseline
        self.last_decision = None
