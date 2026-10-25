from __future__ import annotations

import json
from pathlib import Path
import unittest

from conformance.check_public_boundary import boundary_violations

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "spec" / "contract-index.json"


class PublicBoundaryTests(unittest.TestCase):
    def test_current_public_shapes_are_allowed(self):
        self.assertEqual(
            [],
            boundary_violations(
                [
                    ".github/workflows/conformance.yml",
                    "README.md",
                    "conformance/check_public_boundary.py",
                    "docs/product-boundary.md",
                    "examples/synthetic/README.md",
                    "examples/synthetic/valid/package-0.1.0.json",
                    "pyproject.toml",
                    "spec/package-0.1.0.md",
                    "src/bcast/package.py",
                    "tests/test_client.py",
                    "tools/check.py",
                ]
            ),
        )

    def test_private_implementation_and_data_shapes_are_rejected(self):
        paths = [
            "compiler/build.py",
            "providers/icc.py",
            "corpus/raw.pdf",
            "data/corpus.parquet",
            "examples/production/package.json",
            "artifacts/source.sqlite3",
        ]
        violations = boundary_violations(paths)
        for path in paths:
            self.assertTrue(any(path in violation for violation in violations), path)

    def test_contract_index_is_non_normative_and_references_public_files(self):
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        self.assertEqual("bcast-public-contract-index/1", index["format"])
        self.assertIs(False, index["normative"])
        self.assertIn("exact Git revision", index["pinning"])
        contracts = index["contracts"]
        self.assertEqual(
            ["bcast.api/0.1.0", "bcast.api/0.2.0", "bcast.package/0.1.0", "bcast.package/0.2.0"],
            sorted(item["coordinate"] for item in contracts),
        )
        self.assertEqual(len(contracts), len({item["coordinate"] for item in contracts}))
        for item in contracts:
            self.assertTrue((ROOT / item["normative_path"]).is_file())
            self.assertTrue(item["normative_path"].startswith("spec/"))
            for path in item.get("companions", []):
                self.assertTrue((ROOT / path).is_file())
                self.assertTrue(path.startswith("spec/"))
        api = next(item for item in contracts if item["coordinate"] == "bcast.api/0.1.0")
        self.assertEqual(["bcast.package/0.1.0"], api["compatible_package_contracts"])
        new_api = next(item for item in contracts if item["coordinate"] == "bcast.api/0.2.0")
        self.assertEqual(["bcast.package/0.2.0"], new_api["compatible_package_contracts"])


if __name__ == "__main__":
    unittest.main()
