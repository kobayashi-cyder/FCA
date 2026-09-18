from __future__ import annotations

from dataclasses import dataclass

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
