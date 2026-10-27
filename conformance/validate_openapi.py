"""Validate the public OpenAPI 3.2 companion and all of its local references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator
from openapi_spec_validator import OpenAPIV32SpecValidator, validate


def _references(value: Any):
    if isinstance(value, dict):
        for name, child in value.items():
            if name == "$ref":
                yield child
            else:
                yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _resolve_reference(source: Path, reference: str, root: Path) -> None:
    if not isinstance(reference, str):
        raise ValueError("OpenAPI $ref must be a string")
    parts = urlsplit(reference)
    if parts.scheme or parts.netloc or parts.query:
        raise ValueError(f"non-local OpenAPI reference: {reference}")
    source = source.resolve()
    target = (source.parent / unquote(parts.path)).resolve() if parts.path else source
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError(f"missing or out-of-tree reference target: {reference}")
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable reference target: {reference}") from exc

    value = document
    pointer = unquote(parts.fragment)
    if pointer and not pointer.startswith("/"):
        raise ValueError(f"unsupported JSON reference fragment: {reference}")
    for component in pointer[1:].split("/") if pointer else ():
        key = component.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and key.isdecimal() and int(key) < len(value):
            value = value[int(key)]
        else:
            raise ValueError(f"unresolved JSON pointer: {reference}")

    # The external documents are ordinary JSON Schemas, not arbitrary files.
    if target != source:
        Draft202012Validator.check_schema(document)


def validate_openapi_document(document: dict[str, Any], source: Path) -> None:
    # Resolve every reference, not just the subset a generic validator visits.
    root = source.resolve().parents[2]
    for reference in _references(document):
        _resolve_reference(source, reference, root)
    validate(document, base_uri=source.resolve().as_uri(), cls=OpenAPIV32SpecValidator)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("openapi", type=Path)
    path = parser.parse_args().openapi
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        validate_openapi_document(document, path)
    except Exception as exc:
        print(f"ERROR {path}: {exc}", file=sys.stderr)
        return 1
    print(f"OK {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
