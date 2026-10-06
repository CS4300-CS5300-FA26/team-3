"""Check the private deployment event without AWS or a real database."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class LambdaTests(unittest.TestCase):
    def test_database_probe_and_public_request_separation(self):
        # Import the production entry point in isolation so its settings
        # overrides cannot change settings for other Django tests.
        env = dict(os.environ, DJANGO_SETTINGS_MODULE="budgetwise.settings",
                   DJANGO_SECRET_KEY="local-test-only-" * 5, DB_HOST="",
                   PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        result = subprocess.run([sys.executable, "-c", '''
from unittest.mock import MagicMock, patch
import lambda_entry

db = MagicMock()
db.vendor = "postgresql"
db.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
with patch.object(lambda_entry, "connection", db):
    assert lambda_entry.handler({"operation": "check_database"}, None) == {"database": "ok"}
    db.close.assert_called_once()

    db.reset_mock()
    event = {"version": "2.0", "body": '{"operation":"check_database"}'}
    with patch.object(lambda_entry, "http_handler", return_value={"statusCode": 200}) as http:
        assert lambda_entry.handler(event, None) == {"statusCode": 200}
        http.assert_called_once_with(event, None)
    db.cursor.assert_not_called()

    db.vendor = "sqlite"
    try:
        lambda_entry.handler({"operation": "check_database"}, None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Deployment check accepted SQLite")
    db.close.assert_called_once()
'''], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
