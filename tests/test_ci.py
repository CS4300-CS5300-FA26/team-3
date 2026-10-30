"""Exercise CI's lint command on intentional violations without external services."""
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def lint_source(source, filename="example.py"):
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    step = re.search(r"      - name: Lint Python\n(?:        .*\n)*?        run: (.+)", workflow)
    if step is None:
        raise AssertionError("CI does not run a Python lint check")
    command = shlex.split(step[1])
    if command[:3] != ["python", "-m", "flake8"]:
        raise AssertionError("Sprint 3 CI must run Flake8 with lint reports")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = ROOT / ".flake8"
        (root / config.name).write_text(config.read_text())
        sample = root / filename
        sample.parent.mkdir(parents=True, exist_ok=True)
        sample.write_text(source)
        return subprocess.run(
            [sys.executable, *command[1:]], cwd=root,
            capture_output=True, text=True, check=False,
        )


class CIChecksTests(unittest.TestCase):
    def test_every_branch_push_is_eligible_and_pr_checks_remain(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        # No path filter or development-branch naming convention may skip tests.
        self.assertRegex(workflow, r'  push:\n    branches: \["\*\*"\]\n')
        self.assertRegex(workflow, r"  pull_request:\n    branches: \[main\]\n")

    def test_lint_accepts_valid_python(self):
        result = lint_source("value = 1\nprint(value)\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "0")

    def test_lint_rejects_errors_and_basic_style_violations(self):
        for source, diagnostic in (
            ("print(missing_value)\n", "F821"),
            ("value = 1; print(value)\n", "E702"),
            ("def broken(:\n", "E999"),
        ):
            with self.subTest(diagnostic=diagnostic):
                result = lint_source(source)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(diagnostic, result.stdout)

    def test_late_import_exception_is_limited_to_lambda_bootstrap(self):
        source = "print('configure Django first')\nimport os\nprint(os.name)\n"
        allowed = lint_source(source, "src/lambda_entry.py")
        rejected = lint_source(source, "src/other.py")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        self.assertEqual(rejected.returncode, 1, rejected.stdout + rejected.stderr)
        self.assertIn("E402", rejected.stdout)
