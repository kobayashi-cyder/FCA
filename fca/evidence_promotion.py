from __future__ import annotations

from dataclasses import dataclass


STAGES = ("rejected", "ephemeral", "shadow", "consolidated")


@dataclass(frozen=True)
class VerifiedExperience:
    candidate_id: str
    evidence_id: str
    reward: float
    verified: bool
    stage: str


class VerifiedExperienceGate:
    """Replay-protected evidence gate for FCA-local learned candidates.

    This is deliberately outside the connectome controller. It can decide when a
    learned candidate has enough independent evidence to be trusted as a compact
    prior, but it never selects actions or bypasses KC/MBON computation.
    """

    def __init__(self, *, reward_threshold: float = 0.70, consolidate_after: int = 3) -> None:
        if not 0.0 <= reward_threshold <= 1.0:
            raise ValueError("reward_threshold must be in [0, 1]")
        if consolidate_after < 3:
            raise ValueError("consolidate_after must be at least 3")
        self.reward_threshold = float(reward_threshold)
        self.consolidate_after = int(consolidate_after)
        self.records: list[VerifiedExperience] = []
        self._seen_evidence: set[str] = set()

    def observe(self, *, candidate_id: str, evidence_id: str, reward: float, verified: bool) -> VerifiedExperience:
        candidate_id = str(candidate_id).strip()
        evidence_id = str(evidence_id).strip()
        if not candidate_id:
            raise ValueError("candidate_id is required")
        if not evidence_id:
            raise ValueError("evidence_id is required")
        if evidence_id in self._seen_evidence:
            raise ValueError("duplicate evidence")
        reward = float(reward)
        if not 0.0 <= reward <= 1.0:
            raise ValueError("reward must be in [0, 1]")

        successful = bool(verified) and reward >= self.reward_threshold
        prior_successes = sum(
            1 for row in self.records
            if row.candidate_id == candidate_id
            and row.verified
            and row.reward >= self.reward_threshold
            and row.stage != "rejected"
        )
        success_count = prior_successes + (1 if successful else 0)
        if not successful:
            stage = "rejected"
        elif success_count >= self.consolidate_after:
            stage = "consolidated"
        elif success_count >= 2:
            stage = "shadow"
        else:
            stage = "ephemeral"

        row = VerifiedExperience(candidate_id, evidence_id, reward, bool(verified), stage)
        self.records.append(row)
        self._seen_evidence.add(evidence_id)
        return row

    def stage_for(self, candidate_id: str) -> str | None:
        rows = [row for row in self.records if row.candidate_id == candidate_id]
        if not rows:
            return None
        rank = {name: index for index, name in enumerate(STAGES)}
        successful = [row for row in rows if row.stage != "rejected"]
        if not successful:
            return "rejected"
        return max(successful, key=lambda row: rank[row.stage]).stage

    def consolidated(self, candidate_id: str) -> bool:
        return self.stage_for(candidate_id) == "consolidated"
