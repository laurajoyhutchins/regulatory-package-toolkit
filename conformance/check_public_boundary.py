from __future__ import annotations

from pathlib import PurePosixPath
import subprocess
import sys
from typing import Iterable

_ALLOWED_TOP_LEVEL_DIRECTORIES = frozenset(
    {
        ".github",
        "conformance",
        "docs",
        "examples",
        "spec",
        "src",
        "tests",
        "tools",
    }
)
_FORBIDDEN_ARTIFACT_SUFFIXES = (
    ".pdf",
    ".zip",
    ".tar",
    ".tgz",
    ".7z",
    ".gz",
    ".bz2",
    ".xz",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".duckdb",
    ".parquet",
    ".pkl",
    ".pickle",
)


def boundary_violations(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    normalized = {str(path).replace("\\", "/").strip("/") for path in paths if str(path).strip()}
    for raw in sorted(normalized):
        parts = PurePosixPath(raw).parts
        if len(parts) > 1 and parts[0] not in _ALLOWED_TOP_LEVEL_DIRECTORIES:
            violations.append(f"{raw}: unexpected top-level directory {parts[0]!r}")
        if parts and parts[0] == "examples" and (len(parts) < 2 or parts[1] != "synthetic"):
            violations.append(f"{raw}: public examples must live under examples/synthetic/")
        if raw.lower().endswith(_FORBIDDEN_ARTIFACT_SUFFIXES):
            violations.append(
                f"{raw}: tracked source/corpus artifact format is forbidden in the public repository"
            )
    return violations


def tracked_paths() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [entry for entry in output.decode("utf-8").split("\0") if entry]


def main() -> int:
    violations = boundary_violations(tracked_paths())
    if violations:
        print("Public/private repository boundary violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("OK public repository path boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
