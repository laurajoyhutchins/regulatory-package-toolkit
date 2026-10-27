from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .api import BcastApiClient, BcastApiError
from .package import BcastPackage, ObjectCoordinateNotFoundError, ObjectNotFoundError
from .server import serve_paths
from .validation import PACKAGE_CONTRACTS, PackageValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bcast", description="Read and validate public BCAST packages."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a local BCAST package")
    validate.add_argument("package")

    get = subparsers.add_parser("get", help="Retrieve one canonical object record")
    get.add_argument("package")
    get.add_argument("object_id")

    children = subparsers.add_parser("children", help="List direct structural children")
    children.add_argument("package")
    children.add_argument("object_id")

    tree = subparsers.add_parser("tree", help="Print the local public structural tree")
    tree.add_argument("package")

    review = subparsers.add_parser(
        "review", help="Review publication structure and representation gaps in one command"
    )
    review.add_argument("package")
    review.add_argument(
        "--require-resolved",
        action="store_true",
        help="Exit 2 for representation gaps, not regulatory or engineering approval",
    )

    find = subparsers.add_parser("find", help="Retrieve an object by kind and locator")
    find.add_argument("package")
    find.add_argument("kind")
    find.add_argument("locator")

    serve = subparsers.add_parser(
        "serve", help="Serve validated local packages through bcast.api/0.1.0"
    )
    serve.add_argument("packages", nargs="+")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--package-contract", choices=PACKAGE_CONTRACTS, default=PACKAGE_CONTRACTS[0]
    )

    api = subparsers.add_parser("api", help="Call a bcast.api/0.1.0 endpoint")
    api.add_argument("base_url")
    api.add_argument("--package-contract", choices=PACKAGE_CONTRACTS, default=PACKAGE_CONTRACTS[0])
    api_subparsers = api.add_subparsers(dest="api_command", required=True)

    metadata = api_subparsers.add_parser("metadata", help="Retrieve package metadata")
    metadata.add_argument("package_id")

    package = api_subparsers.add_parser("package", help="Retrieve a complete package")
    package.add_argument("package_id")

    api_get = api_subparsers.add_parser("get", help="Retrieve one canonical object record")
    api_get.add_argument("package_id")
    api_get.add_argument("object_id")

    api_children = api_subparsers.add_parser("children", help="List direct structural children")
    api_children.add_argument("package_id")
    api_children.add_argument("object_id")

    api_review = api_subparsers.add_parser(
        "review", help="Review a full remotely served package after identity validation"
    )
    api_review.add_argument("package_id")
    api_review.add_argument(
        "--require-resolved",
        action="store_true",
        help="Exit 2 for representation gaps, not regulatory or engineering approval",
    )

    api_find = api_subparsers.add_parser(
        "find", help="Retrieve a served object by kind and locator after package validation"
    )
    api_find.add_argument("package_id")
    api_find.add_argument("kind")
    api_find.add_argument("locator")
    return parser


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _safe_label(value: str) -> str:
    """Keep untrusted publication text on one terminal line, never execute controls."""
    encoded = json.dumps(value, ensure_ascii=False)[1:-1]
    return "".join(
        f"\\u{ord(character):04x}"
        if 0x7F <= ord(character) <= 0x9F or character in ("\u2028", "\u2029")
        else character
        for character in encoded
    )


def _print_tree(package: BcastPackage, *, show_status: bool = False) -> None:
    # Explicit stack avoids RecursionError on valid deeply nested publications.
    pending = [(root, 0) for root in reversed(package.roots())]
    while pending:
        record, depth = pending.pop()
        label = record.get("label")
        suffix = f" {_safe_label(label)}" if label else ""
        status = f"[{record['status']}] " if show_status else ""
        locator = _safe_label(record["locator"])
        print(f"{'  ' * depth}{status}{record['kind']} {locator}{suffix}")
        pending.extend(
            (child, depth + 1) for child in reversed(package.children(record["object_id"]))
        )


def _print_review(package: BcastPackage, *, source: str = "local") -> bool:
    metadata = package.metadata()
    publication = metadata["publication"]
    records = package.as_dict()["objects"]
    counts = {status: 0 for status in ("resolved", "unresolved", "unsupported")}
    for record in records:
        counts[record["status"]] += 1

    print(f"BCAST {source} package review (representation only)")
    print(f"Publication: {_safe_label(publication.get('title') or publication['family'])}")
    print(f"Edition: {_safe_label(publication['edition'])}")
    print(f"Contract: {package.schema_version}")
    print(f"Package ID: {package.package_id}")
    print(
        f"Objects: {len(records)} | resolved: {counts['resolved']}"
        f" | unresolved: {counts['unresolved']}"
        f" | unsupported: {counts['unsupported']}"
    )
    print("Hierarchy (status / kind / locator / label):")
    _print_tree(package, show_status=True)
    print("Status describes representation availability, not source fidelity, legal")
    print("applicability, professional verification, or engineering approval.")
    return bool(counts["unresolved"] or counts["unsupported"])


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "serve":
            serve_paths(
                args.packages,
                host=args.host,
                port=args.port,
                package_contract=args.package_contract,
            )
            return 0
        if args.command == "api":
            client = BcastApiClient(args.base_url, package_contract=args.package_contract)
            if args.api_command == "metadata":
                _print_json(client.get_package_metadata(args.package_id))
            elif args.api_command == "package":
                _print_json(client.get_package(args.package_id))
            elif args.api_command == "get":
                _print_json(client.get_object(args.package_id, args.object_id))
            elif args.api_command == "children":
                _print_json(client.get_children(args.package_id, args.object_id))
            elif args.api_command == "review":
                gaps = _print_review(
                    BcastPackage.from_mapping(client.get_package(args.package_id)), source="remote"
                )
                if args.require_resolved and gaps:
                    return 2
            elif args.api_command == "find":
                package = BcastPackage.from_mapping(client.get_package(args.package_id))
                _print_json(package.find(args.kind, args.locator))
            return 0

        package = BcastPackage.load(args.package)
        if args.command == "validate":
            print(f"OK {args.package}")
        elif args.command == "get":
            _print_json(package.get_object(args.object_id))
        elif args.command == "children":
            _print_json(package.children(args.object_id))
        elif args.command == "tree":
            _print_tree(package)
        elif args.command == "review":
            gaps = _print_review(package)
            if args.require_resolved and gaps:
                return 2
        elif args.command == "find":
            _print_json(package.find(args.kind, args.locator))
        return 0
    except (
        PackageValidationError,
        ObjectNotFoundError,
        ObjectCoordinateNotFoundError,
        BcastApiError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
