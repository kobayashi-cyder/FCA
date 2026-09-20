from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterable

from .agent import FCAAgent
from .concepts import ConceptGraph, Fact
from .connectome import KenyonLayer, SensoryHash, SparsePattern
from .memory import HotColdMemory


class TeacherPriorError(RuntimeError):
    pass


@dataclass(frozen=True)
class TeacherCircuit:
    name: str
    priority: float
    detect: tuple[str, ...]
    plan: tuple[str, ...]
    principles: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class TeacherActivation:
    name: str
    score: float
    overlap: float
    cue_hits: tuple[str, ...]


def _canonical_digest(path: Path) -> str:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TeacherPriorError(f"teacher prior data unreadable: {path.name}") from exc
    payload = json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").casefold())


class FAPV78CircuitPriors:
    """Gemma 4 distilled procedural priors adapted to FCA's connectome-first core.

    FCA always computes its normal sensory projection and sparse KC-like pattern first.
    The imported circuits are compared against that sparse representation and may only
    add a bounded bias to existing MBON-like action channels. They do not bypass reward
    learning and teacher-derived memory remains unverified shadow evidence.
    """

    DEFAULT_ACTION_MAP = {
        "uncertainty": ("inspect", "verify", "verification", "wait"),
        "conversation_repair": ("respond", "conversation_repair"),
        "constraint_aware": ("inspect", "plan", "planning"),
        "decomposition": ("plan", "decomposition", "inspect"),
        "verification": ("verify", "verification", "inspect"),
        "planning": ("plan", "planning", "inspect"),
        "debugging": ("debug", "debugging", "inspect"),
        "context_followup": ("respond", "context_followup"),
        "tool_use": ("tool", "tool_use", "inspect"),
        "long_form": ("respond", "long_form"),
    }

    SUPPLEMENTAL_CUES = {
        "uncertainty": ("不確実", "可能性", "分からない", "断定"),
        "conversation_repair": ("じゃなく", "というより"),
        "constraint_aware": ("メモリ", "RAM", "速度", "精度", "制約", "容量"),
        "decomposition": ("手順", "段階", "タスク"),
        "verification": ("証拠", "確認"),
        "planning": ("計画", "ゴール", "目標"),
        "debugging": ("エラー", "例外", "不具合", "デバッグ"),
        "context_followup": ("これ", "その", "さっき"),
        "tool_use": ("API", "コマンド", "ツール"),
        "long_form": ("詳しく", "比較", "長め"),
    }

    def __init__(self, data_dir: Path | str | None = None, *, verify_integrity: bool = True) -> None:
        self.data_dir = (
            Path(data_dir)
            if data_dir is not None
            else Path(__file__).with_name("data") / "fap_v78"
        )
        self.provenance = self._load("provenance.json")
        if verify_integrity:
            self._verify()

        raw_circuits = self._load("teacher_consolidated_circuits.json")
        self.memory_rows = self._load("fap_memory.json")
        self.concepts = self._load("fap_concepts.json")

        self.circuits: dict[str, TeacherCircuit] = {}
        for name, spec in raw_circuits.items():
            if spec.get("stage") != "consolidated":
                raise TeacherPriorError(f"teacher circuit is not consolidated: {name}")
            self.circuits[name] = TeacherCircuit(
                name=name,
                priority=float(spec.get("priority", 1.0)),
                detect=tuple(str(x) for x in spec.get("detect", [])),
                plan=tuple(str(x) for x in spec.get("plan", [])),
                principles=tuple(str(x) for x in spec.get("principles", [])),
                confidence=float(spec.get("teacher_confidence", 0.5)),
            )

        self._validate()
        self._sensory = SensoryHash(128)
        self._kc = KenyonLayer(input_channels=128, kcs=256, fan_in=6, winners=16)
        self._prototype_patterns = {
            name: self._prototype_pattern(circuit)
            for name, circuit in self.circuits.items()
        }

    def _load(self, name: str):
        path = self.data_dir / name
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TeacherPriorError(f"teacher prior data unreadable: {name}") from exc

    def _verify(self) -> None:
        files = self.provenance.get("files")
        if not isinstance(files, dict):
            raise TeacherPriorError("teacher prior provenance missing hashes")
        for name, meta in files.items():
            expected = str(meta.get("canonical_sha256", ""))
            if not expected:
                raise TeacherPriorError(f"teacher prior hash missing: {name}")
            actual = _canonical_digest(self.data_dir / name)
            if actual != expected:
                raise TeacherPriorError(f"teacher prior digest mismatch: {name}")

    def _validate(self) -> None:
        counts = self.provenance.get("counts", {})
        if int(counts.get("circuits", -1)) != len(self.circuits):
            raise TeacherPriorError("teacher circuit count mismatch")
        if not isinstance(self.memory_rows, list):
            raise TeacherPriorError("teacher memory schema invalid")
        if int(counts.get("memory_items", -1)) != len(self.memory_rows):
            raise TeacherPriorError("teacher memory count mismatch")
        for item in self.memory_rows:
            if item.get("source") != "teacher_shadow":
                raise TeacherPriorError("teacher memory must remain shadow-labelled")
            weight = float(item.get("weight", -1))
            if not 0.0 <= weight <= 1.0:
                raise TeacherPriorError("teacher memory weight invalid")

        nodes = self.concepts.get("nodes")
        edges = self.concepts.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise TeacherPriorError("teacher concept graph schema invalid")
        if int(counts.get("concept_nodes", -1)) != len(nodes):
            raise TeacherPriorError("teacher concept node count mismatch")
        if int(counts.get("concept_edges", -1)) != len(edges):
            raise TeacherPriorError("teacher concept edge count mismatch")

    def _prototype_pattern(self, circuit: TeacherCircuit) -> SparsePattern:
        text = " ".join(
            list(circuit.detect)
            + list(self.SUPPLEMENTAL_CUES.get(circuit.name, ()))
            + list(circuit.plan[:3])
            + list(circuit.principles[:2])
        )
        return self._kc.activate(self._sensory.encode_text(text))

    @staticmethod
    def _pattern_overlap(a: SparsePattern, b: SparsePattern) -> float:
        left = set(a.active)
        right = set(b.active)
        if not left or not right:
            return 0.0
        return len(left & right) / max(1, min(len(left), len(right)))

    def activations(
        self,
        observation: str,
        pattern: SparsePattern,
        *,
        limit: int = 4,
    ) -> list[TeacherActivation]:
        normalized = _norm(observation)
        out: list[TeacherActivation] = []
        for name, circuit in self.circuits.items():
            cues = circuit.detect + tuple(self.SUPPLEMENTAL_CUES.get(name, ()))
            hits = tuple(cue for cue in cues if _norm(cue) and _norm(cue) in normalized)
            overlap = self._pattern_overlap(pattern, self._prototype_patterns[name])

            if not hits and overlap < 0.20:
                continue

            lexical = min(1.0, len(hits) / 2.0)
            signal = 0.65 * overlap + 0.35 * lexical
            confidence_gain = 0.65 + 0.35 * max(0.0, min(1.0, circuit.confidence))
            score = circuit.priority * confidence_gain * signal
            out.append(
                TeacherActivation(
                    name=name,
                    score=round(score, 6),
                    overlap=round(overlap, 6),
                    cue_hits=hits[:8],
                )
            )

        out.sort(key=lambda x: (-x.score, x.name))
        return out[: max(1, int(limit))]

    def action_bias(
        self,
        observation: str,
        pattern: SparsePattern,
        actions: Iterable[str],
        *,
        gain: float = 0.45,
    ) -> tuple[dict[str, float], tuple[TeacherActivation, ...]]:
        if gain < 0.0 or gain > 2.0:
            raise ValueError("teacher prior gain out of range")
        action_tuple = tuple(actions)
        action_set = set(action_tuple)
        biases = {action: 0.0 for action in action_tuple}
        activations = tuple(self.activations(observation, pattern))

        for activation in activations:
            candidates = self.DEFAULT_ACTION_MAP.get(activation.name, ())
            selected = next((name for name in candidates if name in action_set), None)
            if selected is None:
                continue
            biases[selected] += min(1.0, gain * activation.score)

        return {name: min(1.0, value) for name, value in biases.items()}, activations

    def seed_memory(self, memory: HotColdMemory) -> int:
        inserted = 0
        for index, item in enumerate(self.memory_rows):
            text = str(item["text"]).strip()
            weight = float(item["weight"])
            memory.remember(
                f"fap-v78-shadow-{index:02d}",
                text,
                utility=0.15 * weight,
                confidence=min(0.69, weight),
            )
            inserted += 1
        return inserted

    def seed_concepts(self, graph: ConceptGraph) -> int:
        inserted = 0
        for edge in self.concepts["edges"]:
            graph.add(
                Fact(
                    subject=str(edge["subject"]),
                    relation=str(edge["relation"]),
                    object=str(edge["object"]),
                    confidence=min(0.79, float(edge.get("confidence", 0.5))),
                    verified=False,
                    source="FAP:v78:teacher_shadow",
                )
            )
            inserted += 1
        return inserted


class TeacherAwareFCAAgent(FCAAgent):
    """FCAAgent with compact FAP V78 priors attached to MBON competition."""

    def __init__(
        self,
        actions: tuple[str, ...] = ("respond", "inspect", "wait"),
        *,
        priors: FAPV78CircuitPriors | None = None,
        prior_gain: float = 0.45,
    ) -> None:
        super().__init__(actions=actions)
        if prior_gain < 0.0 or prior_gain > 2.0:
            raise ValueError("prior_gain out of range")
        self.priors = priors or FAPV78CircuitPriors()
        self.prior_gain = float(prior_gain)
        self.last_teacher_activations: tuple[TeacherActivation, ...] = ()

    def score_bias(self, observation: str, pattern: SparsePattern) -> dict[str, float]:
        biases, activations = self.priors.action_bias(
            observation,
            pattern,
            self.policy.actions,
            gain=self.prior_gain,
        )
        self.last_teacher_activations = activations
        return biases
