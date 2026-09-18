from __future__ import annotations

from dataclasses import dataclass, field

from .agent import FCAAgent
from .organs import OrganRegistry, OrganResult


@dataclass(frozen=True)
class Step:
    index: int
    action: str
    observation: str
    reward: float
    progress: float
    terminal: bool
    blocked: bool
    reason: str


@dataclass
class GoalReport:
    goal: str
    status: str
    steps: list[Step] = field(default_factory=list)
    progress: float = 0.0

    @property
    def final_observation(self) -> str:
        return self.steps[-1].observation if self.steps else ""


class AutonomousLoop:
    """Bounded persistent goal loop.

    It stops only on completion, explicit blocker, or budget exhaustion.
    """

    def __init__(
        self,
        registry: OrganRegistry,
        *,
        max_steps: int = 32,
        blocker_limit: int = 3,
    ) -> None:
        if max_steps < 1 or blocker_limit < 1:
            raise ValueError("budgets must be positive")
        if not registry.names:
            raise ValueError("registry must contain at least one organ")
        self.registry = registry
        self.agent = FCAAgent(actions=registry.names)
        self.max_steps = max_steps
        self.blocker_limit = blocker_limit

    def run(self, goal: str, initial_observation: str = "") -> GoalReport:
        goal = goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")

        report = GoalReport(goal=goal, status="running")
        observation = initial_observation
        blocker_streak = 0

        for index in range(1, self.max_steps + 1):
            decision = self.agent.decide(f"GOAL {goal}\nSTATE {observation}")
            result: OrganResult = self.registry.run(decision.action, goal, observation)
            self.agent.reinforce(result.reward)

            report.progress = max(report.progress, result.progress)
            report.steps.append(
                Step(
                    index=index,
                    action=decision.action,
                    observation=result.observation,
                    reward=result.reward,
                    progress=result.progress,
                    terminal=result.terminal,
                    blocked=result.blocked,
                    reason=result.reason,
                )
            )
            observation = result.observation

            if result.terminal:
                report.status = "completed"
                return report

            if result.blocked:
                blocker_streak += 1
                if blocker_streak >= self.blocker_limit:
                    report.status = "blocked"
                    return report
            else:
                blocker_streak = 0

        report.status = "budget_exhausted"
        return report
