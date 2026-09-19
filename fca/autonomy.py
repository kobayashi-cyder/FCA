from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256

from .agent import FCAAgent
from .organs import OrganRegistry, OrganResult
from .state_store import JSONGoalCheckpointStore


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
    With a checkpoint store it can resume after interruption while preserving
    trace state and learned action values.
    """

    def __init__(
        self,
        registry: OrganRegistry,
        *,
        max_steps: int = 32,
        blocker_limit: int = 3,
        store: JSONGoalCheckpointStore | None = None,
    ) -> None:
        if max_steps < 1 or blocker_limit < 1:
            raise ValueError("budgets must be positive")
        if not registry.names:
            raise ValueError("registry must contain at least one organ")
        self.registry = registry
        self.agent = FCAAgent(actions=registry.names)
        self.max_steps = max_steps
        self.blocker_limit = blocker_limit
        self.store = store

    @staticmethod
    def deterministic_goal_id(goal: str) -> str:
        return "goal-" + sha256(goal.strip().encode("utf-8")).hexdigest()[:16]

    def _checkpoint(
        self,
        goal_id: str,
        report: GoalReport,
        observation: str,
        blocker_streak: int,
        next_step: int,
    ) -> None:
        if self.store is None:
            return
        self.store.save(
            goal_id,
            {
                "goal": report.goal,
                "status": report.status,
                "progress": report.progress,
                "steps": [asdict(step) for step in report.steps],
                "observation": observation,
                "blocker_streak": blocker_streak,
                "next_step": next_step,
                "agent": self.agent.snapshot(),
            },
        )

    def _resume(
        self,
        goal_id: str,
        goal: str,
    ) -> tuple[GoalReport, str, int, int] | None:
        if self.store is None:
            return None
        raw = self.store.load(goal_id)
        if raw is None:
            return None
        if raw.get("goal") != goal:
            raise ValueError("stored goal does not match supplied goal")
        if raw.get("status") in {"completed", "blocked"}:
            report = GoalReport(
                goal=goal,
                status=str(raw["status"]),
                steps=[Step(**row) for row in raw.get("steps", [])],
                progress=float(raw.get("progress", 0.0)),
            )
            return report, str(raw.get("observation", "")), int(raw.get("blocker_streak", 0)), int(raw.get("next_step", 1))
        self.agent.restore(raw.get("agent", {}))
        report = GoalReport(
            goal=goal,
            status="running",
            steps=[Step(**row) for row in raw.get("steps", [])],
            progress=float(raw.get("progress", 0.0)),
        )
        return (
            report,
            str(raw.get("observation", "")),
            int(raw.get("blocker_streak", 0)),
            int(raw.get("next_step", len(report.steps) + 1)),
        )

    def run(
        self,
        goal: str,
        initial_observation: str = "",
        *,
        goal_id: str | None = None,
        resume: bool = True,
    ) -> GoalReport:
        goal = goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")
        goal_id = goal_id or self.deterministic_goal_id(goal)

        restored = self._resume(goal_id, goal) if resume else None
        if restored is None:
            report = GoalReport(goal=goal, status="running")
            observation = initial_observation
            blocker_streak = 0
            start_step = 1
        else:
            report, observation, blocker_streak, start_step = restored
            if report.status in {"completed", "blocked"}:
                return report

        for index in range(start_step, self.max_steps + 1):
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
                self._checkpoint(goal_id, report, observation, blocker_streak, index + 1)
                return report

            if result.blocked:
                blocker_streak += 1
                if blocker_streak >= self.blocker_limit:
                    report.status = "blocked"
                    self._checkpoint(goal_id, report, observation, blocker_streak, index + 1)
                    return report
            else:
                blocker_streak = 0

            self._checkpoint(goal_id, report, observation, blocker_streak, index + 1)

        report.status = "budget_exhausted"
        self._checkpoint(goal_id, report, observation, blocker_streak, self.max_steps + 1)
        return report
