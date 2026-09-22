from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable

from .agent import Decision, FCAAgent
from .lazy_organs import LazyOrganRegistry
from .organs import OrganResult
from .world_model import WorldGraph


@dataclass(frozen=True)
class VerificationIssue:
    code: str
    detail: str = ""


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    score: float = 1.0
    issues: tuple[VerificationIssue, ...] = ()


Verifier = Callable[[str, Decision, OrganResult, WorldGraph], VerificationResult]


class IntegrityVerifier:
    """Minimum fail-closed structural verifier for organ outcomes."""

    def __call__(
        self,
        goal: str,
        decision: Decision,
        result: OrganResult,
        world: WorldGraph,
    ) -> VerificationResult:
        issues: list[VerificationIssue] = []
        if not isfinite(float(result.reward)):
            issues.append(VerificationIssue("non_finite_reward"))
        if not isfinite(float(result.progress)) or not 0.0 <= float(result.progress) <= 1.0:
            issues.append(VerificationIssue("progress_out_of_range"))
        if result.terminal and result.blocked:
            issues.append(VerificationIssue("terminal_and_blocked"))
        return VerificationResult(
            accepted=not issues,
            score=1.0 if not issues else 0.0,
            issues=tuple(issues),
        )


@dataclass(frozen=True)
class RuntimeStep:
    index: int
    decision: Decision
    result: OrganResult
    verification: tuple[VerificationResult, ...]
    accepted: bool
    effective_reward: float
    loaded_organs: tuple[str, ...]


class FCARebuiltRuntime:
    """Connectome-first runtime rebuilt from later FAP execution lessons.

    Flow:
      sparse connectome decision
      -> load one selected organ
      -> execute
      -> verify fail-closed
      -> reinforce using accepted/rejected outcome
      -> append explicit task-state relations
    """

    def __init__(
        self,
        registry: LazyOrganRegistry,
        *,
        agent: FCAAgent | None = None,
        verifiers: tuple[Verifier, ...] = (),
        reject_penalty: float = 0.25,
        world: WorldGraph | None = None,
    ) -> None:
        if not registry.names:
            raise ValueError("registry must contain at least one organ")
        if reject_penalty < 0.0 or not isfinite(reject_penalty):
            raise ValueError("reject_penalty must be finite and non-negative")
        self.registry = registry
        self.agent = agent or FCAAgent(actions=registry.names)
        if set(self.agent.policy.actions) != set(registry.names):
            raise ValueError("agent actions must match lazy registry")
        self.verifiers = (IntegrityVerifier(),) + tuple(verifiers)
        self.reject_penalty = float(reject_penalty)
        self.world = world or WorldGraph()
        self._step_index = 0

    def _record(
        self,
        goal: str,
        decision: Decision,
        result: OrganResult,
        accepted: bool,
    ) -> None:
        self.world.upsert("goal", "goal", state="active", attributes={"text": goal})
        action_id = f"action:{self._step_index}"
        outcome_id = f"outcome:{self._step_index}"
        self.world.upsert(
            action_id,
            "action",
            state="selected",
            attributes={"name": decision.action},
        )
        self.world.upsert(
            outcome_id,
            "outcome",
            state="accepted" if accepted else "rejected",
            attributes={
                "observation": result.observation,
                "progress": result.progress,
                "blocked": result.blocked,
                "terminal": result.terminal,
            },
        )
        self.world.relate("goal", "selected", action_id)
        self.world.relate(action_id, "produced", outcome_id)
        self.world.relate(
            "goal",
            "accepted_outcome",
            outcome_id,
            negative=not accepted,
        )

    def step(self, goal: str, observation: str = "") -> RuntimeStep:
        goal = goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")

        self._step_index += 1
        decision = self.agent.decide(f"GOAL {goal}\nSTATE {observation}")
        result = self.registry.run(decision.action, goal, observation)

        verdicts = tuple(v(goal, decision, result, self.world) for v in self.verifiers)
        for verdict in verdicts:
            if not 0.0 <= float(verdict.score) <= 1.0 or not isfinite(float(verdict.score)):
                raise ValueError("verifier score must be finite in [0,1]")
        accepted = all(v.accepted for v in verdicts)

        if accepted:
            effective_reward = float(result.reward)
        else:
            effective_reward = min(0.0, float(result.reward)) - self.reject_penalty

        self.agent.reinforce(effective_reward)
        self._record(goal, decision, result, accepted)
        return RuntimeStep(
            index=self._step_index,
            decision=decision,
            result=result,
            verification=verdicts,
            accepted=accepted,
            effective_reward=effective_reward,
            loaded_organs=self.registry.loaded,
        )

    def status(self) -> dict[str, object]:
        return {
            "architecture": "connectome-first-v0.3",
            "registered_organs": self.registry.names,
            "loaded_organs": self.registry.loaded,
            "organ_load_count": self.registry.load_count,
            "steps": self._step_index,
            "world": self.world.snapshot(),
        }
