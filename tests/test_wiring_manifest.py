import json
import unittest

from fca import ConnectomeManifest


class WiringManifestTests(unittest.TestCase):
    def _manifest(self):
        return {
            "schema": "fca.connectome.v1",
            "version": "test",
            "source": {"name": "fixture", "sha256": ""},
            "input_channels": 4,
            "units": [
                {"id": "a", "class": "KC", "inputs": [0, 1]},
                {"id": "b", "class": "KC", "inputs": [2, 3]},
            ],
        }

    def test_manifest_digest_is_stable_under_key_order(self):
        a = ConnectomeManifest.from_json(json.dumps(self._manifest()))
        b = ConnectomeManifest.from_json(json.dumps(self._manifest(), sort_keys=True))
        self.assertEqual(a.manifest_sha256, b.manifest_sha256)

    def test_manifest_builds_explicit_layer(self):
        m = ConnectomeManifest.from_json(json.dumps(self._manifest()))
        layer = m.to_kenyon_layer(winners=1)
        p = layer.activate([1.0, 1.0, 0.0, 0.0])
        self.assertEqual(p.active, (0,))

    def test_optional_regions_are_preserved(self):
        raw = self._manifest()
        raw["units"][0]["regions"] = ["AL_R", "MB_R", "AL_R"]
        manifest = ConnectomeManifest.from_json(json.dumps(raw))
        self.assertEqual(manifest.units[0].regions, ("AL_R", "MB_R"))
        self.assertEqual(manifest.units[1].regions, ())

    def test_invalid_regions_are_rejected(self):
        raw = self._manifest()
        raw["units"][0]["regions"] = "AL_R"
        with self.assertRaises(ValueError):
            ConnectomeManifest.from_json(json.dumps(raw))

    def test_invalid_input_index_rejected(self):
        raw = self._manifest()
        raw["units"][0]["inputs"] = [99]
        with self.assertRaises(ValueError):
            ConnectomeManifest.from_json(json.dumps(raw))


if __name__ == "__main__":
    unittest.main()
