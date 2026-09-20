from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable, Any


@dataclass(frozen=True)
class SafeBinding:
    binding_id: str
    fn: Callable[[Any], Any]
    verified: bool = False
    deterministic: bool = False
    side_effect_free: bool = False

    @property
    def eligible(self) -> bool:
        return self.verified and self.deterministic and self.side_effect_free


@dataclass(frozen=True)
class SkillNode:
    node_id: str
    binding_id: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeclarativeSkill:
    name: str
    nodes: tuple[SkillNode, ...]
    output_node: str

    @property
    def skill_id(self) -> str:
        payload = {
            "name": self.name,
            "nodes": [
                {"node_id": n.node_id, "binding_id": n.binding_id, "depends_on": list(n.depends_on)}
                for n in self.nodes
            ],
            "output_node": self.output_node,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class VerifiedSkillComposer:
    """Bounded declarative skill composition outside FCA's connectome controller.

    It grants no execution rights: every referenced host binding must already be
    verified, deterministic and side-effect-free. Skills are DAGs, not source code.
    """

    def __init__(self, bindings: tuple[SafeBinding, ...], *, max_nodes: int = 12) -> None:
        if not 1 <= max_nodes <= 12:
            raise ValueError("max_nodes must be in [1, 12]")
        self.max_nodes = max_nodes
        self._bindings = {b.binding_id: b for b in bindings}
        if len(self._bindings) != len(bindings):
            raise ValueError("duplicate binding_id")

    def validate(self, skill: DeclarativeSkill) -> None:
        if not skill.name.strip() or not skill.nodes:
            raise ValueError("skill name and nodes are required")
        if len(skill.nodes) > self.max_nodes:
            raise ValueError("skill exceeds node bound")
        ids = [n.node_id for n in skill.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate node_id")
        if skill.output_node not in ids:
            raise ValueError("output node is missing")
        known = set(ids)
        for node in skill.nodes:
            binding = self._bindings.get(node.binding_id)
            if binding is None or not binding.eligible:
                raise ValueError("ineligible binding")
            if any(dep not in known for dep in node.depends_on):
                raise ValueError("unknown dependency")

        visiting: set[str] = set()
        visited: set[str] = set()
        by_id = {n.node_id: n for n in skill.nodes}
        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("cycle detected")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dep in by_id[node_id].depends_on:
                visit(dep)
            visiting.remove(node_id)
            visited.add(node_id)
        for node_id in ids:
            visit(node_id)

        reachable: set[str] = set()
        def mark(node_id: str) -> None:
            if node_id in reachable:
                return
            reachable.add(node_id)
            for dep in by_id[node_id].depends_on:
                mark(dep)
        mark(skill.output_node)
        if reachable != known:
            raise ValueError("dead node outside output dependency chain")

    def execute(self, skill: DeclarativeSkill, payload: Any) -> Any:
        self.validate(skill)
        by_id = {n.node_id: n for n in skill.nodes}
        results: dict[str, Any] = {}
        def run(node_id: str) -> Any:
            if node_id in results:
                return results[node_id]
            node = by_id[node_id]
            inputs = [run(dep) for dep in node.depends_on]
            value = payload if not inputs else (inputs[0] if len(inputs) == 1 else tuple(inputs))
            results[node_id] = self._bindings[node.binding_id].fn(value)
            return results[node_id]
        return run(skill.output_node)
