"""Fixed UTF-8/NFC conformance vectors for BCAST 0.2 publication identities.

The independent Go consumer currently supports an ASCII-only identity profile.
These tests establish the public contract behavior without claiming that
consumer passes this wider Unicode profile or that source content is reviewed.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
import unicodedata
import unittest

from bcast import BcastApiClient, BcastPackage, build_package_v2, validate_package
from bcast.server import make_server
from bcast.validation import PackageValidationError


FIXTURE = (
    Path(__file__).resolve().parents[1] / "examples/synthetic/valid/package-0.2.0-unicode.json"
)


def independently_hashed(prefix: str, value: dict) -> str:
    """Rehash the normative canonical UTF-8 JSON without BCAST's hash helper."""
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"{prefix}:sha256:{hashlib.sha256(encoded).hexdigest()}"


class UnicodeIdentityInteroperabilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def normalized_objects(self):
        return [
            {
                "kind": "document",
                "locator": "root",
                "status": "resolved",
                "label": "Synthetic Unicode publication",
            },
            {
                "kind": "section",
                "locator": "1",
                "parent": {"kind": "document", "locator": "root"},
                "status": "resolved",
                "content": {
                    "media_type": "text/plain",
                    "text": "Public synthetic interoperability data; no regulatory claim.",
                },
            },
        ]

    def test_fixed_nfc_fixture_has_independently_recomputable_utf8_identities(self):
        package = self.fixture
        publication = package["publication"]
        self.assertEqual("Édition 2026", publication["edition"])
        self.assertEqual("Révision 1", publication["revision"])
        self.assertEqual(
            "bcastpub:sha256:d1531202dfc19b6b3c980008b8cc9af60197019ab1ad48492b7dfff440747cc0",
            publication["publication_id"],
        )
        self.assertEqual(
            "bcastpkg:sha256:77a18560eaf39fe9ef723a0d01961b636e548d96a2d3703056cebdceb342fde5",
            package["package_id"],
        )

        identity = {
            key: publication[key] for key in ("namespace", "family", "edition", "revision")
        }
        self.assertEqual(publication["publication_id"], independently_hashed("bcastpub", identity))
        for obj in package["objects"]:
            coordinates = {
                "publication_id": publication["publication_id"],
                "kind": obj["kind"],
                "locator": obj["locator"],
            }
            self.assertEqual(obj["object_id"], independently_hashed("bcastobj", coordinates))

        materialized = {key: value for key, value in package.items() if key != "package_id"}
        materialized["objects"] = sorted(package["objects"], key=lambda obj: obj["object_id"])
        self.assertEqual(package["package_id"], independently_hashed("bcastpkg", materialized))
        validate_package(package)
        self.assertEqual(package, BcastPackage.from_mapping(package).as_dict())

    def test_public_builder_reproduces_fixed_unicode_fixture_exactly(self):
        publication = {
            key: value
            for key, value in self.fixture["publication"].items()
            if key != "publication_id"
        }
        actual = build_package_v2(
            publication=publication,
            package_version=self.fixture["package_version"],
            objects=self.normalized_objects(),
        )
        self.assertEqual(self.fixture, actual)

    def test_non_nfc_coordinates_are_rejected_not_silently_normalized(self):
        for field in ("edition", "revision"):
            with self.subTest(field=field):
                publication = {
                    key: value
                    for key, value in self.fixture["publication"].items()
                    if key != "publication_id"
                }
                decomposed = unicodedata.normalize("NFD", publication[field])
                self.assertNotEqual(publication[field], decomposed)
                publication[field] = decomposed
                with self.assertRaisesRegex(PackageValidationError, "NFC"):
                    build_package_v2(
                        publication=publication,
                        package_version=self.fixture["package_version"],
                        objects=self.normalized_objects(),
                    )
                tampered = deepcopy(self.fixture)
                tampered["publication"][field] = decomposed
                with self.assertRaisesRegex(PackageValidationError, "NFC"):
                    validate_package(tampered)

    def test_http_reference_server_and_client_preserve_unicode_coordinates(self):
        package = BcastPackage.from_mapping(self.fixture)
        server = make_server(
            [package],
            host="127.0.0.1",
            port=0,
            package_contract="bcast.package/0.2.0",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = BcastApiClient(
                f"http://127.0.0.1:{server.server_port}",
                package_contract="bcast.package/0.2.0",
            )
            self.assertEqual(self.fixture, client.get_package(package.package_id))
            self.assertEqual(
                "Édition 2026",
                client.get_package_metadata(package.package_id)["publication"]["edition"],
            )
            root = package.roots()[0]
            self.assertEqual(root, client.get_object(package.package_id, root["object_id"]))
            self.assertEqual(
                package.children(root["object_id"]),
                client.get_children(package.package_id, root["object_id"]),
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
