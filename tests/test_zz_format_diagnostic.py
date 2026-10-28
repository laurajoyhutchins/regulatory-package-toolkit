"""Temporary formatter diagnostic; removed after capturing the exact CI diff."""

from pathlib import Path
import subprocess
import sys
import unittest


class FormatterDiagnostic(unittest.TestCase):
    def test_print_ruff_diff(self):
        target = Path(__file__).with_name("test_unicode_compatibility.py")
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--diff", str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        print("RUFF_FORMAT_DIFF_BEGIN", flush=True)
        print(result.stdout, flush=True)
        print(result.stderr, flush=True)
        print("RUFF_FORMAT_DIFF_END", flush=True)
        self.assertIn(result.returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()
