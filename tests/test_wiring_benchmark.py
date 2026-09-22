from __future__ import annotations

import json
import unittest

from fca.wiring_benchmark import (
    benchmark_manifest_runtime,
    compare_wiring_benchmarks,
)
from fca.wiring_manifest import ConnectomeManifest


class WiringBenchmarkTests(unittest.TestCase):
    def _manifest(self, name: str, rows):
        raw = {
            "schema": "fca.connectome.v1",
            "version": "test",
            "source": {"name": name, "sha256": ""},
            "input_channels": 4,
            "input_labels": ["i0", "i1", "i2", "i3"],
            "units": [
                {"id": f"k{i}", "class": "KC", "inputs": list(inputs)}
                for i, inputs in enumerate(rows)
            ],
        }
        return ConnectomeManifest.from_json(json.dumps(raw))

    def test_behavioral_summary_is_deterministic_for_same_seed(self):
        manifest = self._manifest("fixture", [(0, 1), (2, 3), (0, 2)])
        first = benchmark_manifest_runtime(
            manifest,
            probes=12,
            winners=2,
            input_activity=0.5,
            seed=7,
        )
        second = benchmark_manifest_runtime(
            manifest,
            probes=12,
            winners=2,
            input_activity=0.5,
            seed=7,
        )

        self.assertEqual(first.unique_winner_patterns, second.unique_winner_patterns)
        self.assertEqual(first.participating_units, second.participating_units)
        self.assertEqual(first.participation_ratio, second.participation_ratio)
        self.assertEqual(first.mean_abs_winner_value, second.mean_abs_winner_value)
        self.assertGreaterEqual(first.median_activation_ms, 0.0)
        self.assertGreaterEqual(first.p95_activation_ms, 0.0)
        self.assertGreaterEqual(first.tracemalloc_peak_bytes, 0)

    def test_winner_count_is_bounded_by_manifest_units(self):
        manifest = self._manifest("small", [(0, 1), (2, 3)])
        report = benchmark_manifest_runtime(
            manifest,
            probes=4,
            winners=16,
            input_activity=0.5,
        )
        self.assertEqual(report.winners, 2)
        self.assertLessEqual(report.participating_units, 2)
        self.assertLessEqual(report.participation_ratio, 1.0)

    def test_comparison_returns_descriptive_ratios(self):
        reference = benchmark_manifest_runtime(
            self._manifest("reference", [(0, 1), (2, 3)]),
            probes=6,
            winners=1,
            seed=3,
        )
        candidate = benchmark_manifest_runtime(
            self._manifest("candidate", [(0, 1, 2), (1, 2, 3)]),
            probes=6,
            winners=1,
            seed=3,
        )
        comparison = compare_wiring_benchmarks(reference, candidate)
        self.assertGreaterEqual(comparison.latency_median_ratio, 0.0)
        self.assertGreaterEqual(comparison.latency_p95_ratio, 0.0)
        self.assertGreaterEqual(comparison.peak_memory_ratio, 0.0)
        self.assertIsInstance(comparison.unique_pattern_delta, int)

    def test_invalid_probe_configuration_fails_closed(self):
        manifest = self._manifest("fixture", [(0, 1), (2, 3)])
        with self.assertRaises(ValueError):
            benchmark_manifest_runtime(manifest, probes=0)
        with self.assertRaises(ValueError):
            benchmark_manifest_runtime(manifest, input_activity=0.0)


if __name__ == "__main__":
    unittest.main()
