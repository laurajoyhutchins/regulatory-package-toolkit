"""User journey: local package -> representation review -> coordinate lookup.

Synthetic public inputs only. No provider APIs, AI, private corpora or remote services.
"""

from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bcast import BcastPackage, build_package_v2
from bcast.cli import main as cli_main
from bcast.server import make_server


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "synthetic" / "valid"


def run_cli(*arguments: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        exit_code = cli_main(list(arguments))
    return exit_code, out.getvalue(), err.getvalue()


@contextmanager
def reference_server(package: BcastPackage):
    server = make_server(
        [package], host="127.0.0.1", port=0, package_contract=package.schema_version
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@contextmanager
def hostile_json_server(payload):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class LocalReviewJourneyTests(unittest.TestCase):
    def test_explicit_resolved_gate_preserves_legacy_success_for_complete_packages(self):
        for version in ("0.1.0", "0.2.0"):
            with self.subTest(version=version):
                path = FIXTURES / f"package-{version}.json"
                code, report, err = run_cli("review", str(path), "--require-resolved")
                self.assertEqual((0, ""), (code, err))
                self.assertIn("unresolved: 0 | unsupported: 0", report)

    def test_opt_in_gate_exits_attention_on_real_validated_representation_gaps(self):
        for gap in ("unresolved", "unsupported"):
            with self.subTest(gap=gap):
                package = BcastPackage.from_mapping(
                    build_package_v2(
                        publication={
                            "namespace": "codes.example",
                            "family": "gap-attention-test",
                            "edition": "2026",
                        },
                        package_version="synthetic.1",
                        objects=[
                            {"kind": "document", "locator": "root", "status": "resolved"},
                            {
                                "kind": "section",
                                "locator": "1.1",
                                "parent": {"kind": "document", "locator": "root"},
                                "status": gap,
                            },
                        ],
                    )
                )
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "package.json"
                    path.write_text(json.dumps(package.as_dict()), encoding="utf-8")
                    ordinary, ordinary_report, err = run_cli("review", str(path))
                    gated, gated_report, gated_err = run_cli(
                        "review", str(path), "--require-resolved"
                    )
                self.assertEqual((0, ""), (ordinary, err))
                self.assertEqual((2, ""), (gated, gated_err))
                self.assertEqual(ordinary_report, gated_report)
                self.assertIn(f"[{gap}] section 1.1", gated_report)
                self.assertIn("not source fidelity", gated_report)
                with reference_server(package) as base_url:
                    remote, output, err = run_cli(
                        "api",
                        base_url,
                        "--package-contract",
                        package.schema_version,
                        "review",
                        package.package_id,
                        "--require-resolved",
                    )
                self.assertEqual((2, ""), (remote, err))
                self.assertIn(f"[{gap}] section 1.1", output)

    def test_remote_reference_api_preserves_local_report_under_both_contracts(self):
        for version in ("0.1.0", "0.2.0"):
            with self.subTest(version=version):
                path = FIXTURES / f"package-{version}.json"
                package = BcastPackage.load(path)
                code, local, err = run_cli("review", str(path))
                self.assertEqual((0, ""), (code, err))
                with reference_server(package) as base_url:
                    code, remote, err = run_cli(
                        "api",
                        base_url,
                        "--package-contract",
                        package.schema_version,
                        "review",
                        package.package_id,
                    )
                self.assertEqual((0, ""), (code, err))
                self.assertIn(f"Package ID: {package.package_id}", remote)
                self.assertEqual(
                    local.replace("BCAST local package review", "BCAST remote package review"),
                    remote,
                )

    def test_remote_coordinate_lookup_reuses_full_validation_for_both_contracts(self):
        for version in ("0.1.0", "0.2.0"):
            with self.subTest(version=version):
                package = BcastPackage.load(FIXTURES / f"package-{version}.json")
                with reference_server(package) as base_url:
                    code, response, err = run_cli(
                        "api",
                        base_url,
                        "--package-contract",
                        package.schema_version,
                        "find",
                        package.package_id,
                        "section",
                        "1.1",
                    )
                self.assertEqual((0, ""), (code, err))
                self.assertEqual(package.find("section", "1.1"), json.loads(response))

    def test_remote_coordinate_lookup_fails_closed_on_missing_and_corrupt_data(self):
        package = BcastPackage.load(FIXTURES / "package-0.2.0.json")
        with reference_server(package) as base_url:
            code, response, err = run_cli(
                "api",
                base_url,
                "--package-contract",
                package.schema_version,
                "find",
                package.package_id,
                "section",
                "not-a-section",
            )
            self.assertEqual(1, code)
            self.assertEqual("", response)
            self.assertIn("kind=section locator=not-a-section", err)

        corrupted = package.as_dict()
        corrupted["objects"][1]["status"] = "unsupported"
        with hostile_json_server(corrupted) as base_url:
            code, response, err = run_cli(
                "api",
                base_url,
                "--package-contract",
                package.schema_version,
                "find",
                package.package_id,
                "section",
                "1.1",
            )
        self.assertEqual(1, code)
        self.assertEqual("", response)
        self.assertIn("public BCAST contract", err)

    def test_remote_corrupt_full_materialization_fails_before_printing_review(self):
        original = BcastPackage.load(FIXTURES / "package-0.2.0.json")
        forged = original.as_dict()
        forged["objects"][1]["content"]["text"] = "Tampered by source"
        with hostile_json_server(forged) as base_url:
            code, out, err = run_cli(
                "api",
                base_url,
                "--package-contract",
                original.schema_version,
                "review",
                original.package_id,
            )
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("public BCAST contract", err)

    def test_remote_wrong_version_fails_without_report(self):
        original = BcastPackage.load(FIXTURES / "package-0.2.0.json")
        with reference_server(original) as base_url:
            code, out, err = run_cli("api", base_url, "review", original.package_id)
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("incompatible contract version", err)

    def test_untrusted_control_characters_cannot_forge_review_rows(self):
        package = build_package_v2(
            publication={
                "namespace": "codes.example",
                "family": "fictional-terminal-test",
                "edition": "2026",
                "title": "Example\n[resolved] forged\x1b[2J",
            },
            package_version="synthetic.1",
            objects=[
                {"kind": "document", "locator": "root", "status": "resolved"},
                {
                    "kind": "section",
                    "locator": "A\n[verified] forged",
                    "parent": {"kind": "document", "locator": "root"},
                    "status": "unresolved",
                    "label": "Needs review\rObjects: 0\x1b[0m",
                },
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            path.write_text(json.dumps(package), encoding="utf-8")
            code, report, err = run_cli("review", str(path))
        self.assertEqual((0, ""), (code, err))
        self.assertNotIn(chr(27), report)
        self.assertNotIn("\n[resolved] forged", report)
        self.assertNotIn("\nObjects: 0", report)
        self.assertEqual(1, report.count("Objects: 2 | resolved: 1"))
        self.assertIn(r"\n[verified] forged", report)
        self.assertIn(r"\rObjects: 0", report)
        self.assertIn("[unresolved] section", report)

    def test_untrusted_validated_package_cannot_forge_tree_or_review_lines(self):
        locator = "A\n[resolved] forged\x1b[2J"
        label = "Needs review\rObjects: 0\u202e[resolved] forged"
        title = "Fictional\u0085[resolved] forged\u2066"
        package = BcastPackage.from_mapping(
            build_package_v2(
                publication={
                    "namespace": "codes.example",
                    "family": "display-safety-test",
                    "edition": "2026",
                    "title": title,
                },
                package_version="synthetic.1",
                objects=[
                    {"kind": "document", "locator": "root", "status": "resolved"},
                    {
                        "kind": "section",
                        "locator": locator,
                        "parent": {"kind": "document", "locator": "root"},
                        "status": "unresolved",
                        "label": label,
                    },
                ],
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.json"
            path.write_text(json.dumps(package.as_dict()), encoding="utf-8")
            tree_code, tree, tree_err = run_cli("tree", str(path))
            review_code, review, review_err = run_cli("review", str(path))
            find_code, found, find_err = run_cli("find", str(path), "section", locator)

        self.assertEqual(
            (0, "", 0, "", 0, ""),
            (tree_code, tree_err, review_code, review_err, find_code, find_err),
        )
        self.assertEqual(2, len(tree.splitlines()))
        self.assertEqual(1, sum("section " in line for line in tree.splitlines()))
        self.assertIn(r"\n[resolved] forged\u001b[2J", tree)
        self.assertIn(r"\rObjects: 0\u202e[resolved] forged", tree)
        self.assertIn(r"\u0085[resolved] forged\u2066", review)
        self.assertEqual(1, review.count("Objects: 2 | resolved: 1 | unresolved: 1"))
        for output in (tree, review):
            for control in ("\r", "\x1b", "\u0085", "\u202e", "\u2066"):
                self.assertNotIn(control, output)
        self.assertEqual(locator, json.loads(found)["locator"])
        self.assertEqual(label, json.loads(found)["label"])

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
