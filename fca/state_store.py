from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JSONGoalCheckpointStore:
    """Atomic JSON checkpoints for bounded FCA goal runs.

    Only data is stored; no executable callables are serialized.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, goal_id: str) -> Path:
        safe = "".join(ch for ch in goal_id if ch.isalnum() or ch in "-_")
        if not safe or safe != goal_id:
            raise ValueError("goal_id contains unsupported characters")
        return self.root / f"{safe}.json"

    def save(self, goal_id: str, payload: dict[str, Any]) -> Path:
        if not isinstance(payload, dict):
            raise ValueError("checkpoint payload must be an object")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(goal_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path

    def load(self, goal_id: str) -> dict[str, Any] | None:
        path = self._path(goal_id)
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("checkpoint root must be an object")
        return raw

    def clear(self, goal_id: str) -> None:
        path = self._path(goal_id)
        if path.exists():
            path.unlink()
