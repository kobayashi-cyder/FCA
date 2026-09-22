from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .connectome import KenyonLayer


@dataclass(frozen=True)
class WiringUnit:
    unit_id: str
    inputs: tuple[int, ...]
    neuron_class: str = "KC"
    regions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectomeManifest:
    schema: str
    version: str
    source_name: str
    source_sha256: str
    input_channels: int
    input_labels: tuple[str, ...]
    units: tuple[WiringUnit, ...]
    manifest_sha256: str

    @classmethod
    def from_json(cls, text: str) -> "ConnectomeManifest":
        try:
            raw: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid manifest JSON") from exc

        if raw.get("schema") != "fca.connectome.v1":
            raise ValueError("unsupported manifest schema")
        version = str(raw.get("version", "")).strip()
        source = raw.get("source") or {}
        source_name = str(source.get("name", "")).strip()
        source_sha = str(source.get("sha256", "")).lower().strip()
        channels = int(raw.get("input_channels", 0))
        rows = raw.get("units")
        labels_raw = raw.get("input_labels")
        if labels_raw is None:
            input_labels = tuple(str(i) for i in range(channels))
        elif isinstance(labels_raw, list) and len(labels_raw) == channels:
            input_labels = tuple(str(x) for x in labels_raw)
            if len(set(input_labels)) != len(input_labels):
                raise ValueError("input_labels must be unique")
        else:
            raise ValueError("input_labels must match input_channels")

        if not version or not source_name or channels < 1 or not isinstance(rows, list) or not rows:
            raise ValueError("manifest is missing required fields")
        if source_sha and (len(source_sha) != 64 or any(c not in "0123456789abcdef" for c in source_sha)):
            raise ValueError("source sha256 must be empty or 64 lowercase hex characters")

        units: list[WiringUnit] = []
        seen_ids: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("unit must be an object")
            uid = str(row.get("id", "")).strip()
            neuron_class = str(row.get("class", "KC")).strip() or "KC"
            inputs_raw = row.get("inputs")
            regions_raw = row.get("regions", [])
            if not uid or uid in seen_ids or not isinstance(inputs_raw, list) or not inputs_raw:
                raise ValueError("invalid or duplicate unit")
            if not isinstance(regions_raw, list):
                raise ValueError("unit regions must be a list")
            inputs = tuple(dict.fromkeys(int(i) for i in inputs_raw))
            if any(i < 0 or i >= channels for i in inputs):
                raise ValueError("unit input is outside input_channels")
            regions = tuple(dict.fromkeys(str(x).strip() for x in regions_raw))
            if any(not region or len(region) > 256 for region in regions):
                raise ValueError("unit region is empty or oversized")
            if len(regions) > 512:
                raise ValueError("unit has too many regions")
            seen_ids.add(uid)
            units.append(WiringUnit(uid, inputs, neuron_class, regions))

        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        digest = sha256(canonical).hexdigest()
        return cls(
            schema="fca.connectome.v1",
            version=version,
            source_name=source_name,
            source_sha256=source_sha,
            input_channels=channels,
            input_labels=input_labels,
            units=tuple(units),
            manifest_sha256=digest,
        )

    def wiring(self, neuron_class: str = "KC") -> tuple[tuple[int, ...], ...]:
        rows = tuple(unit.inputs for unit in self.units if unit.neuron_class == neuron_class)
        if not rows:
            raise ValueError(f"manifest has no units for class {neuron_class}")
        return rows

    def to_kenyon_layer(self, *, winners: int = 16, neuron_class: str = "KC") -> KenyonLayer:
        rows = self.wiring(neuron_class)
        return KenyonLayer(
            input_channels=self.input_channels,
            winners=min(winners, len(rows)),
            wiring=rows,
        )
