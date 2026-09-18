from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoalContract:
    objective: str
    success_criteria: tuple[str, ...]
    max_steps: int = 32
    max_failures: int = 4
    max_no_progress: int = 3

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective is required")
        if not self.success_criteria:
            raise ValueError("at least one success criterion is required")
        if min(self.max_steps, self.max_failures, self.max_no_progress) < 1:
            raise ValueError("limits must be positive")


@dataclass(frozen=True)
class CriterionAssessment:
    criterion: str
    satisfied: bool
    evidence: str = ""


@dataclass(frozen=True)
class GoalAssessment:
    satisfied: bool
    progress: float
    criteria: tuple[CriterionAssessment, ...]
    reason: str


class GoalCritic:
    """FAP-influenced completion gate: never declare success without all criteria."""

    def assess(
        self,
        contract: GoalContract,
        assessments: tuple[CriterionAssessment, ...],
        *,
        blocked: bool = False,
        reason: str = "",
    ) -> GoalAssessment:
        if blocked:
            return GoalAssessment(False, 0.0, assessments, reason or "blocked")

        by_name = {a.criterion: a for a in assessments}
        ordered = tuple(
            by_name.get(c, CriterionAssessment(c, False, "missing evidence"))
            for c in contract.success_criteria
        )
        satisfied_count = sum(1 for a in ordered if a.satisfied)
        progress = satisfied_count / len(ordered)
        satisfied = satisfied_count == len(ordered)
        return GoalAssessment(
            satisfied=satisfied,
            progress=progress,
            criteria=ordered,
            reason=reason or ("all criteria satisfied" if satisfied else "criteria remain"),
        )
