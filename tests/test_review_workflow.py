"""User journey: local package -> representation review -> coordinate lookup.

Synthetic public inputs only. No provider APIs, AI, private corpora or remote services.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from bcast import build_package_v2
from bcast.cli import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "synthetic" / "valid"


def run_cli(*arguments: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        exit_code = cli_main(list(arguments))
    return exit_code, out.getvalue(), err.getvalue()


class LocalReviewJourneyTests(unittest.TestCase):
    def test_both_real_package_contracts_work_without_specifying_version(self):
        for version in ("0.1.0", "0.2.0"):
            with self.subTest(version=version):
                path = FIXTURES / f"package-{version}.json"
                package = json.loads(path.read_text(encoding="utf-8"))
                code, report, err = run_cli("review", str(path))
                self.assertEqual((0, ""), (code, err))
                self.assertIn(f"Contract: bcast.package/{version}", report)
                self.assertIn(f"Package ID: {package['package_id']}", report)
                self.assertIn("Objects: 2 | resolved: 2 | unresolved: 0 | unsupported: 0", report)
                self.assertIn("[resolved] document root Example Safety Code", report)
                self.assertIn("  [resolved] section 1.1 Clearances", report)
                self.assertNotIn("[verified]", report)
                self.assertIn("not source fidelity", report)
                self.assertNotIn("source-provider", report)

                # The user can select the visible coordinate, not copy a hash.
                code, record, err = run_cli("find", str(path), "section", "1.1")
                self.assertEqual((0, ""), (code, err))
                self.assertEqual(package["objects"][1], json.loads(record))

    def test_status_gaps_survive_review_and_do_not_become_legal_certification(self):
        package = build_package_v2(
            publication={
                "namespace": "codes.example",
                "family": "illustrative-regulations",
                "edition": "2026",
                "title": "Fictional Regulation",
            },
            package_version="synthetic.1",
            objects=[
                {"kind": "document", "locator": "root", "status": "resolved"},
                {
                    "kind": "section",
                    "locator": "A",
                    "parent": {"kind": "document", "locator": "root"},
                    "status": "unresolved",
                    "label": "Requires source review",
                },
                {
                    "kind": "section",
                    "locator": "B",
                    "parent": {"kind": "document", "locator": "root"},
                    "status": "unsupported",
                    "label": "Outside represented scope",
                },
            ],
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package.json"
            path.write_text(json.dumps(package), encoding="utf-8")
            code, report, err = run_cli("review", str(path))
            self.assertEqual((0, ""), (code, err))
            self.assertIn("Objects: 3 | resolved: 1 | unresolved: 1 | unsupported: 1", report)
            self.assertIn("[unresolved] section A Requires source review", report)
            self.assertIn("[unsupported] section B Outside represented scope", report)
            self.assertIn("not source fidelity", report)
            self.assertIn("engineering approval", report)
            code, record, err = run_cli("find", str(path), "section", "B")
            self.assertEqual((0, ""), (code, err))
            self.assertEqual("unsupported", json.loads(record)["status"])
            expected = next(
                item["object_id"] for item in package["objects"] if item["locator"] == "B"
            )
            self.assertEqual(expected, json.loads(record)["object_id"])

    def test_broken_materialization_fails_closed_without_review_output(self):
        package = json.loads((FIXTURES / "package-0.2.0.json").read_text(encoding="utf-8"))
        package["objects"][1]["status"] = "unresolved"  # Digest is now invalid.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "modified.json"
            path.write_text(json.dumps(package), encoding="utf-8")
            code, out, err = run_cli("review", str(path))
            self.assertEqual(1, code)
            self.assertEqual("", out)
            self.assertIn("package_id", err)

    def test_missing_coordinate_has_actionable_nonzero_exit(self):
        path = FIXTURES / "package-0.2.0.json"
        code, out, err = run_cli("find", str(path), "section", "not-there")
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("kind=section locator=not-there", err)

    def test_existing_tree_command_remains_unchanged(self):
        path = FIXTURES / "package-0.1.0.json"
        code, out, err = run_cli("tree", str(path))
        self.assertEqual((0, ""), (code, err))
        self.assertEqual(
            ["document root Example Safety Code", "  section 1.1 Clearances"],
            out.splitlines(),
        )


if __name__ == "__main__":
    unittest.main()
