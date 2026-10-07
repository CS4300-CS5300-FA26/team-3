"""Check host validation with real settings, isolated from the test runner."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class HostTests(unittest.TestCase):
    def test_development_and_production_hosts(self):
        for production in (False, True):
            with self.subTest(production=production):
                env = dict(os.environ, DJANGO_SETTINGS_MODULE="budgetwise.settings",
                           DJANGO_SECRET_KEY="local-test-only-" * 5, DB_HOST="",
                           DJANGO_DEVELOPMENT_HOSTS=" budget-wise.dev, preview.example.test, ",
                           PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
                code = "import lambda_entry\n" if production else "import django; django.setup()\n"
                code += "production = " + repr(production) + "\n"
                code += """
from django.core.exceptions import DisallowedHost
from django.test import RequestFactory
from django.conf import settings
if production:
    assert settings.ALLOWED_HOSTS == ["budget-wise.dev"]
for host in ("budget-wise.dev", "preview.example.test:3000", "localhost:3000",
             "127.0.0.1:3000", "[::1]:3000", "unrelated.example",
             "preview.example.test.evil.example", "budget-wise.dev.evil.example"):
    accepted = host == "budget-wise.dev" or (not production and host in (
        "preview.example.test:3000", "localhost:3000", "127.0.0.1:3000", "[::1]:3000"))
    request = RequestFactory().get("/", HTTP_HOST=host)
    try:
        request.get_host()
    except DisallowedHost:
        assert not accepted, host
    else:
        assert accepted, host
"""
                result = subprocess.run([sys.executable, "-c", code], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
