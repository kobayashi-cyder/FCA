from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil
from random import Random
from statistics import median
from time import perf_counter_ns
import tracemalloc

from .wiring_manifest import ConnectomeManifest


@dataclass(frozen=True)
class WiringBenchmark:
    source_name: str
    version: str
    neuron_class: str
    probes: int
    winners: int
    input_activity: float
    median_activation_ms: float
    p95_activation_ms: float
    tracemalloc_peak_bytes: int
    unique_winner_patterns: int
    participating_units: int
    participation_ratio: float
    mean_abs_winner_value: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WiringBenchmarkComparison:
    reference: WiringBenchmark
    candidate: WiringBenchmark
    latency_median_ratio: float
    latency_p95_ratio: float
    peak_memory_ratio: float
    participation_ratio_delta: float
    unique_pattern_delta: int

    def to_dict(self) -> dict:
        return asdict(self)


def benchmark_manifest_runtime(
    manifest: ConnectomeManifest,
    *,
    neuron_class: str = "KC",
    winners: int = 16,
    probes: int = 32,
    input_activity: float = 0.10,
    seed: int = 1,
) -> WiringBenchmark:
    """Measure one manifest with deterministic probes and local runtime metrics.

    Wall-clock and tracemalloc measurements are environment-specific observations,
    not performance guarantees. Behavioral summary fields are deterministic for a
    fixed manifest, seed and configuration.
    """
    if not isinstance(manifest, ConnectomeManifest):
        raise TypeError("manifest must be ConnectomeManifest")
    if not 1 <= int(probes) <= 512:
        raise ValueError("probes must be in [1, 512]")
    if not 1 <= int(winners) <= 4096:
        raise ValueError("winners must be in [1, 4096]")
    activity = float(input_activity)
    if not 0.0 < activity <= 1.0:
        raise ValueError("input_activity must be in (0, 1]")

    rows = manifest.wiring(neuron_class)
    actual_winners = min(int(winners), len(rows))
    layer = manifest.to_kenyon_layer(
        winners=actual_winners,
        neuron_class=neuron_class,
    )

    rng = Random(int(seed))
    active_inputs = max(
        1,
        min(
            manifest.input_channels,
            4096,
            int(round(manifest.input_channels * activity)),
        ),
    )

    durations_ns: list[int] = []
    patterns: set[tuple[int, ...]] = set()
    participating: set[int] = set()
    abs_value_sum = 0.0
    value_count = 0

    tracemalloc.start()
    try:
        for _ in range(int(probes)):
            sensory = [0.0] * manifest.input_channels
            indices = rng.sample(range(manifest.input_channels), active_inputs)
            for idx in indices:
                sensory[idx] = 1.0 if rng.getrandbits(1) else -1.0

            start = perf_counter_ns()
            pattern = layer.activate(sensory)
            durations_ns.append(perf_counter_ns() - start)

            patterns.add(pattern.active)
            participating.update(pattern.active)
            abs_value_sum += sum(abs(value) for value in pattern.values)
            value_count += len(pattern.values)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    ordered = sorted(durations_ns)
    p95_index = min(
        len(ordered) - 1,
        max(0, ceil(0.95 * len(ordered)) - 1),
    )
    return WiringBenchmark(
        source_name=manifest.source_name,
        version=manifest.version,
        neuron_class=neuron_class,
        probes=int(probes),
        winners=actual_winners,
        input_activity=activity,
        median_activation_ms=median(ordered) / 1_000_000.0,
        p95_activation_ms=ordered[p95_index] / 1_000_000.0,
        tracemalloc_peak_bytes=int(peak_bytes),
        unique_winner_patterns=len(patterns),
        participating_units=len(participating),
        participation_ratio=len(participating) / len(rows),
        mean_abs_winner_value=(
            abs_value_sum / value_count if value_count else 0.0
        ),
    )


def compare_wiring_benchmarks(
    reference: WiringBenchmark,
    candidate: WiringBenchmark,
) -> WiringBenchmarkComparison:
    """Return descriptive ratios/deltas without declaring a winner."""
    if not isinstance(reference, WiringBenchmark) or not isinstance(candidate, WiringBenchmark):
        raise TypeError("reference and candidate must be WiringBenchmark")
    return WiringBenchmarkComparison(
        reference=reference,
        candidate=candidate,
        latency_median_ratio=_ratio(
            candidate.median_activation_ms,
            reference.median_activation_ms,
        ),
        latency_p95_ratio=_ratio(
            candidate.p95_activation_ms,
            reference.p95_activation_ms,
        ),
        peak_memory_ratio=_ratio(
            float(candidate.tracemalloc_peak_bytes),
            float(reference.tracemalloc_peak_bytes),
        ),
        participation_ratio_delta=(
            candidate.participation_ratio - reference.participation_ratio
        ),
        unique_pattern_delta=(
            candidate.unique_winner_patterns - reference.unique_winner_patterns
        ),
    )


def _ratio(candidate: float, reference: float) -> float:
    if reference <= 0.0:
        return float("inf") if candidate > 0.0 else 1.0
    return candidate / reference
