from __future__ import annotations

import gzip
import json
from pathlib import Path
import tempfile
import unittest

from fca.importers import flywire_codex_files_to_manifest
from fca.wiring_manifest import ConnectomeManifest


class FlyWireCodexImporterTests(unittest.TestCase):
    def _write_fixture(self, root: Path, *, gz: bool):
        ann_name = "consolidated_cell_types.csv.gz" if gz else "consolidated_cell_types.csv"
        conn_name = "connections_princeton.csv.gz" if gz else "connections_princeton.csv"
        ann = root / ann_name
        conn = root / conn_name

        ann_text = (
            "root_id,primary_type\n"
            "p1,PN\n"
            "p2,PN\n"
            "k1,KC\n"
            "k2,KC\n"
            "x1,OTHER\n"
        )
        conn_text = (
            "pre_root_id,post_root_id,neuropil,syn_count,nt_type\n"
            "p1,k1,AL_R,3,ACH\n"
            "p1,k1,MB_R,3,ACH\n"
            "p2,k1,MB_R,4,ACH\n"
            "p2,k2,MB_R,5,ACH\n"
            "x1,k1,MB_R,99,GABA\n"
        )
        if gz:
            with gzip.open(ann, "wt", encoding="utf-8", newline="") as fh:
                fh.write(ann_text)
            with gzip.open(conn, "wt", encoding="utf-8", newline="") as fh:
                fh.write(conn_text)
        else:
            ann.write_text(ann_text, encoding="utf-8")
            conn.write_text(conn_text, encoding="utf-8")
        return conn, ann

    def test_streams_gzip_and_aggregates_pair_counts_across_neuropils(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conn, ann = self._write_fixture(root, gz=True)
            text = flywire_codex_files_to_manifest(
                conn,
                ann,
                version="fafb-v783-test",
                source_name="FlyWire Codex test fixture",
                annotation_column="primary_type",
                pre_labels={"PN"},
                post_labels={"KC"},
                min_synapses=5,
            )
            raw = json.loads(text)
            manifest = ConnectomeManifest.from_json(text)

            self.assertEqual(manifest.input_labels, ("p1", "p2"))
            self.assertEqual(manifest.wiring("KC"), ((0,), (1,)))
            self.assertEqual([u.unit_id for u in manifest.units], ["k1", "k2"])
            self.assertEqual(manifest.units[0].regions, ("AL_R", "MB_R"))
            self.assertEqual(manifest.units[1].regions, ("MB_R",))
            self.assertEqual(len(raw["source"]["connections_sha256"]), 64)
            self.assertEqual(len(raw["source"]["annotations_sha256"]), 64)
            self.assertEqual(len(raw["source"]["sha256"]), 64)
            self.assertEqual(raw["source"]["min_synapses"], 5.0)

    def test_plain_csv_and_documented_column_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ann = root / "annotations.csv"
            conn = root / "connections.csv"
            ann.write_text(
                "pt_root_id,class\n"
                "p1,PN\n"
                "k1,KC\n",
                encoding="utf-8",
            )
            conn.write_text(
                "pre_pt_root_id,post_pt_root_id,weight\n"
                "p1,k1,7\n",
                encoding="utf-8",
            )
            text = flywire_codex_files_to_manifest(
                conn,
                ann,
                version="alias-test",
                source_name="alias fixture",
                annotation_column="class",
                pre_labels={"PN"},
                post_labels={"KC"},
                min_synapses=5,
            )
            manifest = ConnectomeManifest.from_json(text)
            self.assertEqual(manifest.input_labels, ("p1",))
            self.assertEqual(manifest.wiring("KC"), ((0,),))

    def test_pair_limit_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conn, ann = self._write_fixture(root, gz=False)
            with self.assertRaises(ValueError):
                flywire_codex_files_to_manifest(
                    conn,
                    ann,
                    version="limit-test",
                    source_name="limit fixture",
                    annotation_column="primary_type",
                    pre_labels={"PN"},
                    post_labels={"KC"},
                    min_synapses=1,
                    max_candidate_pairs=1,
                )

    def test_missing_annotation_selection_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conn, ann = self._write_fixture(root, gz=False)
            with self.assertRaises(ValueError):
                flywire_codex_files_to_manifest(
                    conn,
                    ann,
                    version="selection-test",
                    source_name="selection fixture",
                    annotation_column="primary_type",
                    pre_labels={"DOES_NOT_EXIST"},
                    post_labels={"KC"},
                )

    def test_non_finite_synapse_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ann = root / "annotations.csv"
            conn = root / "connections.csv"
            ann.write_text(
                "root_id,primary_type\np1,PN\nk1,KC\n",
                encoding="utf-8",
            )
            conn.write_text(
                "pre_root_id,post_root_id,syn_count\np1,k1,nan\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                flywire_codex_files_to_manifest(
                    conn,
                    ann,
                    version="nan-test",
                    source_name="nan fixture",
                    annotation_column="primary_type",
                    pre_labels={"PN"},
                    post_labels={"KC"},
                )


if __name__ == "__main__":
    unittest.main()
