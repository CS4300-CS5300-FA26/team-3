"""Local manage.py configuration must preserve explicitly supplied environment values."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class ManagementEnvironmentTests(unittest.TestCase):
    def test_local_dotenv_is_loaded_without_overriding_environment(self):
        source = Path(__file__).resolve().parents[1] / "src/manage.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            script = root / "src/manage.py"
            shutil.copyfile(source, script)
            (root / ".env").write_text("BUDGETWISE_ENV_TEST=from-file\n")
            code = (
                "import os, runpy, sys; from unittest.mock import patch\n"
                "main = runpy.run_path(sys.argv[1])['main']\n"
                "with patch('django.core.management.execute_from_command_line', "
                "side_effect=lambda args: print(os.environ.get('BUDGETWISE_ENV_TEST'))): main()\n"
            )
            for configured, expected in ((None, "from-file"), ("explicit-value", "explicit-value")):
                with self.subTest(configured=configured):
                    env = dict(os.environ)
                    env.pop("BUDGETWISE_ENV_TEST", None)
                    if configured is not None:
                        env["BUDGETWISE_ENV_TEST"] = configured
                    result = subprocess.run([sys.executable, "-c", code, str(script)],
                                            env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), expected)
