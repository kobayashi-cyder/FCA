import json
from pathlib import Path
import unittest

from fca import ExchangeCapsule


class ExchangeFilesTests(unittest.TestCase):
    def test_all_exchange_capsules_parse(self):
        root = Path(__file__).resolve().parents[1] / "exchange"
        files = sorted(root.glob("*.json"))
        self.assertTrue(files)
        for path in files:
            cap = ExchangeCapsule.from_json(path.read_text(encoding="utf-8"))
            self.assertEqual(len(cap.digest), 64)
            self.assertIn(cap.source_project, {"FAP", "FCA"})


if __name__ == "__main__":
    unittest.main()
