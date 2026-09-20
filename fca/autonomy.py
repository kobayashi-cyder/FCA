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

    FAP-derived stall guards stop no-progress/repetition loops.
    With a checkpoint store FCA can resume after interruption while preserving
    trace state and learned action values.

    A compatible FCAAgent may be injected so compact circuit priors can influence
    MBON competition without bypassing the connectome-first controller.
    """

    def __init__(
        self,
        registry: OrganRegistry,
        *,
        max_steps: int = 32,
        blocker_limit: int = 3,
        no_progress_limit: int = 3,
        same_action_limit: int = 3,
        min_progress_delta: float = 0.01,
        store: JSONGoalCheckpointStore | None = None,
        agent: FCAAgent | None = None,
    ) -> None:
        if min(max_steps, blocker_limit, no_progress_limit, same_action_limit) < 1:
            raise ValueError("budgets must be positive")
        if min_progress_delta < 0.0:
            raise ValueError("min_progress_delta must be non-negative")
        if not registry.names:
            raise ValueError("registry must contain at least one organ")
        self.registry = registry
        self.agent = agent or FCAAgent(actions=registry.names)
        if set(self.agent.policy.actions) != set(registry.names):
            raise ValueError("agent actions must match registered organs")
        self.max_steps = max_steps
        self.blocker_limit = blocker_limit
        self.no_progress_limit = no_progress_limit
        self.same_action_limit = same_action_limit
        self.min_progress_delta = float(min_progress_delta)
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
        no_progress_streak: int,
        last_action: str,
        same_action_streak: int,
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
                "no_progress_streak": no_progress_streak,
                "last_action": last_action,
                "same_action_streak": same_action_streak,
                "next_step": next_step,
                "agent": self.agent.snapshot(),
            },
        )

    def _resume(
        self,
        goal_id: str,
        goal: str,
    ) -> tuple[GoalReport, str, int, int, str, int, int] | None:
        if self.store is None:
            return None
        raw = self.store.load(goal_id)
        if raw is None:
            return None
        if raw.get("goal") != goal:
            raise ValueError("stored goal does not match supplied goal")

        report = GoalReport(
            goal=goal,
            status=str(raw.get("status", "running")),
            steps=[Step(**row) for row in raw.get("steps", [])],
            progress=float(raw.get("progress", 0.0)),
        )
        observation = str(raw.get("observation", ""))
        blocker_streak = int(raw.get("blocker_streak", 0))
        no_progress_streak = int(raw.get("no_progress_streak", 0))
        last_action = str(raw.get("last_action", ""))
        same_action_streak = int(raw.get("same_action_streak", 0))
        next_step = int(raw.get("next_step", len(report.steps) + 1))

        if report.status not in {"completed", "blocked", "stalled"}:
            report.status = "running"
            self.agent.restore(raw.get("agent", {}))

        return (
            report,
            observation,
            blocker_streak,
            no_progress_streak,
            last_action,
            same_action_streak,
            next_step,
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
            no_progress_streak = 0
            last_action = ""
            same_action_streak = 0
            start_step = 1
        else:
            (
                report,
                observation,
                blocker_streak,
                no_progress_streak,
                last_action,
                same_action_streak,
                start_step,
            ) = restored
            if report.status in {"completed", "blocked", "stalled"}:
                return report

        for index in range(start_step, self.max_steps + 1):
            decision = self.agent.decide(f"GOAL {goal}\nSTATE {observation}")
            result: OrganResult = self.registry.run(decision.action, goal, observation)
            self.agent.reinforce(result.reward)

            old_progress = report.progress
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

            if report.progress >= old_progress + self.min_progress_delta:
                no_progress_streak = 0
            else:
                no_progress_streak += 1

            if decision.action == last_action:
                same_action_streak += 1
            else:
                last_action = decision.action
                same_action_streak = 1

            if result.terminal:
                report.status = "completed"
                self._checkpoint(
                    goal_id, report, observation, blocker_streak, no_progress_streak,
                    last_action, same_action_streak, index + 1,
                )
                return report

            if result.blocked:
                blocker_streak += 1
                if blocker_streak >= self.blocker_limit:
                    report.status = "blocked"
                    self._checkpoint(
                        goal_id, report, observation, blocker_streak, no_progress_streak,
                        last_action, same_action_streak, index + 1,
                    )
                    return report
            else:
                blocker_streak = 0

            if no_progress_streak >= self.no_progress_limit:
                report.status = "stalled"
                self._checkpoint(
                    goal_id, report, observation, blocker_streak, no_progress_streak,
                    last_action, same_action_streak, index + 1,
                )
                return report

            if same_action_streak >= self.same_action_limit and no_progress_streak > 0:
                report.status = "stalled"
                self._checkpoint(
                    goal_id, report, observation, blocker_streak, no_progress_streak,
                    last_action, same_action_streak, index + 1,
                )
                return report

            self._checkpoint(
                goal_id, report, observation, blocker_streak, no_progress_streak,
                last_action, same_action_streak, index + 1,
            )

        report.status = "budget_exhausted"
        self._checkpoint(
            goal_id, report, observation, blocker_streak, no_progress_streak,
            last_action, same_action_streak, self.max_steps + 1,
        )
        return report
