from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from bcast.validation import PackageValidationError, load_schema, validate_package
from conformance.validate import load_json
from conformance.validate_openapi import _resolve_reference, validate_openapi_document


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "spec" / "schemas" / "package-0.1.0.schema.json"
API_PATH = ROOT / "spec" / "openapi" / "bcast-api-0.1.0.openapi.json"
VALID_PACKAGE_PATH = ROOT / "examples" / "synthetic" / "valid" / "package-0.1.0.json"
INVALID_MISSING_PARENT_PATH = (
    ROOT / "examples" / "synthetic" / "invalid" / "package-0.1.0-missing-parent.json"
)


class PackageConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = load_json(VALID_PACKAGE_PATH)

    def test_synthetic_fixture_conforms(self) -> None:
        schema = load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = sorted(
            validator.iter_errors(self.package),
            key=lambda item: list(item.absolute_path),
        )
        self.assertEqual([], [error.message for error in errors])
        self.assertEqual(load_schema(), schema)
        validate_package(self.package)

    def test_wrong_package_identity_is_rejected(self) -> None:
        candidate = deepcopy(self.package)
        candidate["package_id"] = f"bcastpkg:sha256:{'0' * 64}"
        with self.assertRaises(PackageValidationError) as captured:
            validate_package(candidate)
        self.assertIn(
            "package_id does not match canonical package identity", str(captured.exception)
        )

    def test_missing_parent_fixture_is_rejected(self) -> None:
        candidate = load_json(INVALID_MISSING_PARENT_PATH)
        schema = load_json(SCHEMA_PATH)
        errors = list(Draft202012Validator(schema).iter_errors(candidate))
        self.assertEqual([], [error.message for error in errors])
        with self.assertRaises(PackageValidationError) as captured:
            validate_package(candidate)
        self.assertIn("missing parent object", str(captured.exception))

    def test_structural_parent_cycle_is_rejected(self) -> None:
        candidate = deepcopy(self.package)
        document = candidate["objects"][0]
        section = candidate["objects"][1]
        document["parent_id"] = section["object_id"]
        with self.assertRaises(PackageValidationError) as captured:
            validate_package(candidate)
        self.assertIn("structural parent cycle", str(captured.exception))


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = load_json(API_PATH)

    def test_openapi_32_companion_validates_and_resolves_every_reference(self) -> None:
        validate_openapi_document(self.api, API_PATH)

    def test_local_schema_reference_is_loaded_once_for_pointer_and_validation(self) -> None:
        """The schema checked must be the same bytes used to resolve its pointer."""
        schema_path = ROOT / "spec" / "schemas" / "package-0.1.0.schema.json"
        original_read_text = Path.read_text
        reads = []

        def tracked_read(path, *args, **kwargs):
            if path.resolve() == schema_path.resolve():
                reads.append(path)
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked_read):
            _resolve_reference(
                API_PATH,
                "../schemas/package-0.1.0.schema.json#/properties/objects/items",
                ROOT,
            )
        self.assertEqual(1, len(reads))

    def test_invalid_openapi_structure_is_rejected(self) -> None:
        document = deepcopy(self.api)
        del document["info"]
        with self.assertRaises(Exception):
            validate_openapi_document(document, API_PATH)

    def test_broken_external_schema_reference_is_rejected(self) -> None:
        document = deepcopy(self.api)
        document["paths"]["/packages/{package_id}"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"] = "../schemas/does-not-exist.json"
        with self.assertRaisesRegex(ValueError, "missing or out-of-tree reference target"):
            validate_openapi_document(document, API_PATH)

    def test_out_of_tree_reference_is_rejected(self) -> None:
        document = deepcopy(self.api)
        document["components"]["schemas"]["PackageMetadata"]["properties"]["publication"][
            "$ref"
        ] = "../../../README.md"
        with self.assertRaisesRegex(ValueError, "missing or out-of-tree reference target"):
            validate_openapi_document(document, API_PATH)

    def test_api_contract_is_versioned_and_read_only(self) -> None:
        self.assertEqual("3.2.0", self.api["openapi"])
        self.assertEqual("0.1.0", self.api["info"]["version"])
        self.assertEqual("bcast.api/0.1.0", self.api["x-bcast-contract"])
        self.assertEqual(
            ["bcast.package/0.1.0"],
            self.api["x-bcast-compatible-package-contracts"],
        )

        expected_paths = {
            "/packages/{package_id}/metadata",
            "/packages/{package_id}",
            "/packages/{package_id}/objects/{object_id}",
            "/packages/{package_id}/objects/{object_id}/children",
        }
        self.assertEqual(expected_paths, set(self.api["paths"]))

        http_methods = {
            "get",
            "put",
            "post",
            "delete",
            "patch",
            "options",
            "head",
            "trace",
        }
        for path_item in self.api["paths"].values():
            methods = {key.lower() for key in path_item if key.lower() in http_methods}
            self.assertEqual({"get"}, methods)

    def test_api_contract_reuses_package_shapes(self) -> None:
        package_response = self.api["paths"]["/packages/{package_id}"]["get"]["responses"]["200"]
        self.assertEqual(
            "../schemas/package-0.1.0.schema.json",
            package_response["content"]["application/json"]["schema"]["$ref"],
        )

        object_response = self.api["paths"]["/packages/{package_id}/objects/{object_id}"]["get"][
            "responses"
        ]["200"]
        self.assertEqual(
            "../schemas/package-0.1.0.schema.json#/properties/objects/items",
            object_response["content"]["application/json"]["schema"]["$ref"],
        )

        children_schema = self.api["paths"]["/packages/{package_id}/objects/{object_id}/children"][
            "get"
        ]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("array", children_schema["type"])
        self.assertEqual(
            "../schemas/package-0.1.0.schema.json#/properties/objects/items",
            children_schema["items"]["$ref"],
        )

    def test_api_error_semantics_are_stable(self) -> None:
        semantics = self.api["x-bcast-error-semantics"]
        self.assertEqual(
            {
                "not_found": 404,
                "unresolved": 409,
                "unsupported": 422,
                "incompatible_version": 409,
            },
            {code: details["http_status"] for code, details in semantics.items()},
        )
        problem_codes = self.api["components"]["schemas"]["Problem"]["properties"]["code"]["enum"]
        self.assertEqual(
            ["not_found", "unresolved", "unsupported", "incompatible_version"],
            problem_codes,
        )

    def test_api_surface_excludes_private_operations_and_custom_media_types(self) -> None:
        operation_surface = []
        for path, path_item in self.api["paths"].items():
            operation_surface.append(path)
            operation_surface.append(path_item["get"]["operationId"])
        encoded = " ".join(operation_surface).lower()
        for forbidden in (
            "provider",
            "ingest",
            "normalize",
            "compile",
            "review",
            "entitlement",
            "credential",
            "materialize",
        ):
            self.assertNotIn(forbidden, encoded)

        def collect_content_types(value):
            found = set()
            if isinstance(value, dict):
                content = value.get("content")
                if isinstance(content, dict):
                    found.update(content)
                for child in value.values():
                    found.update(collect_content_types(child))
            elif isinstance(value, list):
                for child in value:
                    found.update(collect_content_types(child))
            return found

        self.assertEqual({"application/json"}, collect_content_types(self.api))


if __name__ == "__main__":
    unittest.main()
