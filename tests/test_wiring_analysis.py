from __future__ import annotations

import json
import unittest

from fca.wiring_analysis import compare_manifest_wiring, manifest_wiring_stats
from fca.wiring_manifest import ConnectomeManifest


class WiringAnalysisTests(unittest.TestCase):
    def _manifest(self, *, name, units, channels=4):
        raw = {
            "schema": "fca.connectome.v1",
            "version": "test",
            "source": {"name": name, "sha256": ""},
            "input_channels": channels,
            "input_labels": [f"i{i}" for i in range(channels)],
            "units": units,
        }
        return ConnectomeManifest.from_json(json.dumps(raw))

    def test_stats_are_deterministic_and_region_aware(self):
        manifest = self._manifest(
            name="data-backed",
            units=[
                {"id": "a", "class": "KC", "inputs": [0, 1], "regions": ["AL_R"]},
                {"id": "b", "class": "KC", "inputs": [1, 2, 3], "regions": ["MB_R", "AL_R"]},
                {"id": "c", "class": "OTHER", "inputs": [0]},
            ],
        )
        stats = manifest_wiring_stats(manifest)
        self.assertEqual(stats.units, 2)
        self.assertEqual(stats.edges, 5)
        self.assertEqual(stats.used_input_channels, 4)
        self.assertEqual(stats.input_utilization, 1.0)
        self.assertEqual(stats.mean_fan_in, 2.5)
        self.assertEqual(stats.median_fan_in, 2.5)
        self.assertEqual(stats.p95_fan_in, 3)
        self.assertEqual(stats.max_fan_in, 3)
        self.assertEqual(stats.density, 5 / 8)
        self.assertEqual(stats.region_count, 2)
        self.assertEqual(stats.units_with_regions, 2)

    def test_compare_reports_ratios_without_ranking(self):
        reference = self._manifest(
            name="synthetic",
            units=[
                {"id": "s1", "class": "KC", "inputs": [0, 1]},
                {"id": "s2", "class": "KC", "inputs": [2, 3]},
            ],
        )
        candidate = self._manifest(
            name="data-backed",
            units=[
                {"id": "d1", "class": "KC", "inputs": [0, 1, 2]},
                {"id": "d2", "class": "KC", "inputs": [1, 2, 3]},
            ],
        )
        comparison = compare_manifest_wiring(reference, candidate)
        self.assertEqual(comparison.input_channels_ratio, 1.0)
        self.assertEqual(comparison.unit_ratio, 1.0)
        self.assertEqual(comparison.edge_ratio, 1.5)
        self.assertEqual(comparison.mean_fan_in_ratio, 1.5)
        self.assertEqual(comparison.density_ratio, 1.5)
        self.assertEqual(comparison.input_utilization_delta, 0.0)

    def test_missing_requested_class_fails_closed(self):
        manifest = self._manifest(
            name="fixture",
            units=[{"id": "x", "class": "OTHER", "inputs": [0]}],
        )
        with self.assertRaises(ValueError):
            manifest_wiring_stats(manifest, neuron_class="KC")


if __name__ == "__main__":
    unittest.main()
