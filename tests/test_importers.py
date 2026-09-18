import json
import unittest

from fca import ConnectomeManifest, edge_csv_to_manifest


CSV = """pre_id,post_id,pre_class,post_class,weight
pn2,kc1,PN,KC,5
pn1,kc1,PN,KC,3
pn2,kc2,PN,KC,4
x,kc2,OTHER,KC,9
pn3,m1,PN,MBON,8
"""


class ImporterTests(unittest.TestCase):
    def test_edge_csv_converts_deterministically(self):
        text = edge_csv_to_manifest(CSV, version="v1", source_name="fixture")
        raw = json.loads(text)
        self.assertEqual(raw["input_labels"], ["pn1", "pn2"])
        self.assertEqual(raw["units"][0]["id"], "kc1")
        self.assertEqual(raw["units"][0]["inputs"], [0, 1])
        m = ConnectomeManifest.from_json(text)
        self.assertEqual(m.input_labels, ("pn1", "pn2"))
        self.assertEqual(len(m.units), 2)

    def test_min_weight_filters_edges(self):
        text = edge_csv_to_manifest(CSV, version="v1", source_name="fixture", min_weight=4)
        raw = json.loads(text)
        kc1 = next(u for u in raw["units"] if u["id"] == "kc1")
        self.assertEqual(kc1["inputs"], [0])

    def test_wrong_schema_rejected(self):
        with self.assertRaises(ValueError):
            edge_csv_to_manifest("a,b\n1,2\n", version="v1", source_name="fixture")


if __name__ == "__main__":
    unittest.main()
