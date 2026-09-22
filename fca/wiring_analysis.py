from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil

from .wiring_manifest import ConnectomeManifest


@dataclass(frozen=True)
class WiringStats:
    source_name: str
    version: str
    neuron_class: str
    input_channels: int
    units: int
    edges: int
    used_input_channels: int
    input_utilization: float
    mean_fan_in: float
    median_fan_in: float
    p95_fan_in: int
    max_fan_in: int
    density: float
    region_count: int
    units_with_regions: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WiringComparison:
    reference: WiringStats
    candidate: WiringStats
    input_channels_ratio: float
    unit_ratio: float
    edge_ratio: float
    mean_fan_in_ratio: float
    density_ratio: float
    input_utilization_delta: float

    def to_dict(self) -> dict:
        return asdict(self)


def manifest_wiring_stats(
    manifest: ConnectomeManifest,
    *,
    neuron_class: str = "KC",
) -> WiringStats:
    if not isinstance(manifest, ConnectomeManifest):
        raise TypeError("manifest must be ConnectomeManifest")
    neuron_class = str(neuron_class or "").strip()
    if not neuron_class:
        raise ValueError("neuron_class is required")

    units = tuple(
        unit for unit in manifest.units
        if unit.neuron_class == neuron_class
    )
    if not units:
        raise ValueError(f"manifest has no units for class {neuron_class}")

    fan_in = sorted(len(unit.inputs) for unit in units)
    edges = sum(fan_in)
    used_inputs = {
        input_index
        for unit in units
        for input_index in unit.inputs
    }
    region_names = {
        region
        for unit in units
        for region in unit.regions
    }
    units_with_regions = sum(1 for unit in units if unit.regions)

    n = len(fan_in)
    if n % 2:
        median = float(fan_in[n // 2])
    else:
        median = (fan_in[n // 2 - 1] + fan_in[n // 2]) / 2.0
    p95_index = min(n - 1, max(0, ceil(0.95 * n) - 1))

    return WiringStats(
        source_name=manifest.source_name,
        version=manifest.version,
        neuron_class=neuron_class,
        input_channels=manifest.input_channels,
        units=n,
        edges=edges,
        used_input_channels=len(used_inputs),
        input_utilization=len(used_inputs) / manifest.input_channels,
        mean_fan_in=edges / n,
        median_fan_in=median,
        p95_fan_in=fan_in[p95_index],
        max_fan_in=fan_in[-1],
        density=edges / (n * manifest.input_channels),
        region_count=len(region_names),
        units_with_regions=units_with_regions,
    )


def compare_manifest_wiring(
    reference: ConnectomeManifest,
    candidate: ConnectomeManifest,
    *,
    neuron_class: str = "KC",
) -> WiringComparison:
    """Compare structural wiring metrics without declaring either wiring better."""
    left = manifest_wiring_stats(reference, neuron_class=neuron_class)
    right = manifest_wiring_stats(candidate, neuron_class=neuron_class)
    return WiringComparison(
        reference=left,
        candidate=right,
        input_channels_ratio=right.input_channels / left.input_channels,
        unit_ratio=right.units / left.units,
        edge_ratio=right.edges / left.edges,
        mean_fan_in_ratio=right.mean_fan_in / left.mean_fan_in,
        density_ratio=right.density / left.density,
        input_utilization_delta=(
            right.input_utilization - left.input_utilization
        ),
    )
