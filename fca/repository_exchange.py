from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Any

from .exchange import ExchangeCapsule
from .exchange_registry import ExchangeRegistry, ExchangeState


CAPABILITY = "repository_coding_verified_candidate"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = frozenset(
    {"content", "replacement", "excerpt", "diff", "output", "argv"}
)


@dataclass(frozen=True)
class RepositoryFileEvidence:
    path: str
    operation: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True)
class RepositoryCodingEvidence:
    source_commit: str
    capsule_digest: str
    plan_id: str
    repository_digest: str
    goal_sha256: str
    files: tuple[RepositoryFileEvidence, ...]
    attempt_count: int
    repairs_used: int
    static_passed: bool
    promotion_branch: str | None = None
    promotion_commit: str | None = None


@dataclass(frozen=True)
class RepositoryExchangeReceipt:
    evidence: RepositoryCodingEvidence
    state: ExchangeState


class RepositoryEvidenceImporter:
    """Validate inert FAP repository-coding evidence.

    This importer never executes source, reconstructs edits, checks out a
    branch, or changes FCA action selection. A valid capsule can only enter the
    existing ExchangeRegistry at RECEIVED state. Independent FCA evidence is
    required for later SHADOW/ACCEPTED transitions.
    """

    def validate(self, capsule: ExchangeCapsule) -> RepositoryCodingEvidence:
        if capsule.source_project != "FAP":
            raise ValueError("repository coding evidence must originate from FAP")
        if capsule.capability != CAPABILITY:
            raise ValueError("unsupported repository coding capability")

        mechanism = capsule.mechanism
        evidence = capsule.evidence
        if _find_forbidden_keys(mechanism) or _find_forbidden_keys(evidence):
            raise ValueError("repository capsule contains executable/source payload keys")

        if mechanism.get("contract") != "fap.repository.coding.v1":
            raise ValueError("unsupported repository coding contract")
        if mechanism.get("plan_contract") != "fap.repository.plan.v1":
            raise ValueError("unsupported repository plan contract")
        if mechanism.get("verification_contract") != "fap.repository.verification.v1":
            raise ValueError("unsupported repository verification contract")
        if evidence.get("repair_contract") != "fap.repository.repair.v1":
            raise ValueError("unsupported repository repair contract")

        if evidence.get("status") != "verified_candidate":
            raise ValueError("repository evidence is not verified_candidate")
        if evidence.get("final_execution_state") != "applied_in_sandbox":
            raise ValueError("final execution was not sandbox-applied")
        if evidence.get("final_verification_state") != "verified_candidate":
            raise ValueError("final verification was not verified_candidate")
        if evidence.get("static_passed") is not True:
            raise ValueError("static verification evidence is missing")

        plan_id = str(mechanism.get("plan_id", "")).lower()
        repository_digest = str(mechanism.get("repository_digest", "")).lower()
        goal_sha256 = str(mechanism.get("goal_sha256", "")).lower()
        if not HEX64.fullmatch(plan_id):
            raise ValueError("invalid plan_id")
        if not HEX64.fullmatch(repository_digest):
            raise ValueError("invalid repository digest")
        if not HEX64.fullmatch(goal_sha256):
            raise ValueError("invalid goal digest")

        attempt_count = _bounded_int(
            evidence.get("attempt_count"),
            "attempt_count",
            minimum=1,
            maximum=5,
        )
        repairs_used = _bounded_int(
            evidence.get("repairs_used"),
            "repairs_used",
            minimum=0,
            maximum=4,
        )
        if repairs_used > attempt_count - 1:
            raise ValueError("repairs_used exceeds attempt evidence")

        commands = evidence.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValueError("verification command evidence is required")
        phases: set[str] = set()
        for row in commands:
            if not isinstance(row, dict):
                raise ValueError("command evidence rows must be objects")
            if row.get("passed") is not True:
                raise ValueError("all exported verification checks must pass")
            if row.get("timed_out") is not False:
                raise ValueError("timed-out verification cannot be accepted")
            if row.get("output_limited") is not False:
                raise ValueError("output-limited verification cannot be accepted")
            phase = str(row.get("phase", ""))
            if phase not in {"static", "focused", "regression"}:
                raise ValueError("invalid verification phase evidence")
            phases.add(phase)
        if "static" not in phases:
            raise ValueError("static verification phase evidence is required")

        files_raw = mechanism.get("files")
        if not isinstance(files_raw, list) or not files_raw:
            raise ValueError("file evidence is required")
        files: list[RepositoryFileEvidence] = []
        seen: set[str] = set()
        for row in files_raw:
            files.append(self._parse_file(row, seen))

        self._validate_constraints(capsule.constraints)

        promotion_branch: str | None = None
        promotion_commit: str | None = None
        promotion = evidence.get("promotion")
        if promotion is not None:
            if not isinstance(promotion, dict):
                raise ValueError("promotion evidence must be an object")
            if promotion.get("state") != "candidate_branch_created":
                raise ValueError("invalid promotion state")
            branch = str(promotion.get("branch", ""))
            commit = str(promotion.get("commit_sha", "")).lower()
            base = str(promotion.get("base_commit", "")).lower()
            if not branch.startswith("fap/candidate/"):
                raise ValueError("unexpected FAP candidate branch namespace")
            if not HEX40.fullmatch(commit) or not HEX40.fullmatch(base):
                raise ValueError("invalid promotion commit evidence")
            promotion_branch = branch
            promotion_commit = commit

        return RepositoryCodingEvidence(
            source_commit=capsule.source_commit,
            capsule_digest=capsule.digest,
            plan_id=plan_id,
            repository_digest=repository_digest,
            goal_sha256=goal_sha256,
            files=tuple(files),
            attempt_count=attempt_count,
            repairs_used=repairs_used,
            static_passed=True,
            promotion_branch=promotion_branch,
            promotion_commit=promotion_commit,
        )

    def receive(
        self,
        capsule: ExchangeCapsule,
        registry: ExchangeRegistry,
    ) -> RepositoryExchangeReceipt:
        parsed = self.validate(capsule)
        state = registry.receive(capsule)
        if state != ExchangeState.RECEIVED:
            # A previously known capsule may already have independent evidence;
            # receiving it again must never synthesize or advance evidence.
            state = registry.state(capsule.digest)
        return RepositoryExchangeReceipt(evidence=parsed, state=state)

    @staticmethod
    def _parse_file(
        row: Any,
        seen: set[str],
    ) -> RepositoryFileEvidence:
        if not isinstance(row, dict):
            raise ValueError("file evidence rows must be objects")
        path = str(row.get("path", "")).replace("\\", "/")
        posix = PurePosixPath(path)
        if (
            not path
            or posix.is_absolute()
            or any(part in {"", ".", "..", ".git"} for part in posix.parts)
        ):
            raise ValueError("unsafe repository evidence path")
        normalized = posix.as_posix()
        if normalized in seen:
            raise ValueError("duplicate repository evidence path")
        seen.add(normalized)

        operation = str(row.get("operation", ""))
        before = str(row.get("before_sha256", "")).lower()
        after = str(row.get("after_sha256", "")).lower()
        if operation == "create":
            if before or not HEX64.fullmatch(after):
                raise ValueError("invalid create hash evidence")
        elif operation == "delete":
            if not HEX64.fullmatch(before) or after:
                raise ValueError("invalid delete hash evidence")
        elif operation == "modify":
            if not HEX64.fullmatch(before) or not HEX64.fullmatch(after):
                raise ValueError("invalid modify hash evidence")
        else:
            raise ValueError("invalid repository file operation")

        return RepositoryFileEvidence(
            path=normalized,
            operation=operation,
            before_sha256=before,
            after_sha256=after,
        )

    @staticmethod
    def _validate_constraints(constraints: tuple[str, ...]) -> None:
        joined = "\n".join(constraints).casefold()
        required_fragments = (
            "must not execute or activate code",
            "connectome",
            "independent fca evidence",
            "no automatic branch promotion",
        )
        missing = [item for item in required_fragments if item not in joined]
        if missing:
            raise ValueError(
                "repository exchange constraints are incomplete: "
                + ",".join(missing)
            )


def _bounded_int(
    value: Any,
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} outside accepted bounds")
    return value


def _find_forbidden_keys(value: Any, prefix: str = "") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).casefold() in FORBIDDEN_KEYS:
                found.append(path)
            found.extend(_find_forbidden_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_keys(child, f"{prefix}[{index}]"))
    return tuple(found)
